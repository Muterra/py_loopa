'''
LICENSING
-------------------------------------------------

loopa: Arduino-esque event loop app framework, and other utilities.
    Copyright (C) 2016 Muterra, Inc.
    
    Contributors
    ------------
    Nick Badger
        badg@muterra.io | badg@nickbadger.com | nickbadger.com

    This library is free software; you can redistribute it and/or
    modify it under the terms of the GNU Lesser General Public
    License as published by the Free Software Foundation; either
    version 2.1 of the License, or (at your option) any later version.

    This library is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
    Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public
    License along with this library; if not, write to the
    Free Software Foundation, Inc.,
    51 Franklin Street,
    Fifth Floor,
    Boston, MA  02110-1301 USA

------------------------------------------------------
'''

# External deps
import logging
import asyncio
import threading
import weakref
import traceback
import collections
import inspect

# In-package deps
# from .utils import complete_coroutine_threadsafe
# from .exceptions import LoopaException


# ###############################################
# Boilerplate
# ###############################################

# Control * imports.
__all__ = [
    'ManagedTask',
    'TaskLooper',
    'TaskCommander',
    'Aengel'
]


logger = logging.getLogger(__name__)


# ###############################################
# Lib
# ###############################################


class _ThreadHelper(threading.Thread):
    ''' Helper class to allow us to pass args and kwargs to the thread
    later than otherwise intended.
    '''
    ARGSIG = inspect.Signature.from_callable(threading.Thread)
    
    def __init__(self, *args, **kwargs):
        ''' Warn for any args or kwargs that will be ignored.
        '''
        super().__init__(*args, **kwargs)
        
        self.__args = None
        self.__kwargs = None
        self.__target = None
        
    def set_target(self, target, args, kwargs):
        ''' Do this so that ManagedTask's start() method can pass args
        and kwargs to the target.
        '''
        self.__target = target
        self.__args = args
        self.__kwargs = kwargs
    
    def run(self):
        ''' Call to self.__target, passing self.__args and self.__kwargs
        '''
        self.__target(self.__args, self.__kwargs)


class ManagedTask:
    ''' Manages thread shutdown (etc) for a thread whose sole purpose is
    running an event loop.
    '''
    
    def __init__(self, threaded=False, debug=False, aengel=None,
                 reusable_loop=False, start_timeout=None, *args, **kwargs):
        ''' Creates a ManagedTask.
        
        *args and **kwargs will be passed to the threading.Thread
        constructor iff threaded=True. Otherwise, they will be ignored.
        
        Loop init arguments should be passed through the start() method.
        
        if executor is None, defaults to the normal executor.
        
        if reusable_loop=True, the ManagedTask can be run more than
        once, but you're responsible for manually calling finalize() to
        clean up the loop. Except this doesn't work at the moment,
        because the internal thread is not reusable.
        '''
        if aengel is not None:
            aengel.prepend_guardling(self)
            
        self._debug = bool(debug)
        self.reusable_loop = bool(reusable_loop)
        self._start_timeout = start_timeout
        
        # This is our actual asyncio.Task
        self._task = None
        
        # These flags control blocking when threaded
        self._startup_complete_flag = threading.Event()
        self._shutdown_complete_flag = threading.Event()
        
        # And deal with threading
        if threaded:
            self._threaded = True
            self._loop = asyncio.new_event_loop()
            
            # Save args and kwargs for the thread creation
            self._thread_args = args
            self._thread_kwargs = kwargs
            
            # Do this here so we can fail fast, instead of when calling start
            # Set up a thread for the loop
            try:
                _ThreadHelper.ARGSIG.bind(
                    daemon = False,
                    target = None,
                    args = tuple(),
                    kwargs = {},
                    *args,
                    **kwargs
                )
            
            except TypeError as exc:
                raise TypeError(
                    'Improper *args and/or **kwargs for threaded ' +
                    'ManagedTask: ' + str(exc)
                ) from None
            
        else:
            self._threaded = False
            self._loop = asyncio.get_event_loop()
            # Declare the thread as nothing.
            self._thread = None
            
    def start(self, *args, **kwargs):
        ''' Dispatches start() to self._start() or self._thread.start(),
        as appropriate. Passes *args and **kwargs along to the task_run
        method.
        '''
        if self._threaded:
            # Delay thread generation until starting.
            self._thread = _ThreadHelper(
                daemon = False,
                target = None,
                args = tuple(),
                kwargs = {},
                *self._thread_args,
                **self._thread_kwargs
            )
            # Update the thread's target and stuff and then run it
            self._thread.set_target(self._run, args, kwargs)
            self._thread.start()
            self._startup_complete_flag.wait(timeout=self._start_timeout)
        
        else:
            # This is redundant, but do it anyways in case other code changes
            self._thread = None
            self._run(args, kwargs)
        
    def _run(self, args, kwargs):
        ''' Handles everything needed to start the loop within the
        current context/thread/whatever. May be extended, but MUST be
        called via super().
        '''
        self._loop.set_debug(self._debug)
        self._shutdown_complete_flag.clear()
        
        try:
            try:
                # If we're running in a thread, we MUST explicitly set up the
                # event loop
                if self._threaded:
                    asyncio.set_event_loop(self._loop)
                
                # Start the task.
                self._looper_future = asyncio.ensure_future(
                    self._execute_task(args, kwargs)
                )
                # Note that this will automatically return the future's result
                # (or raise its exception). We don't use the result, so...
                self._loop.run_until_complete(self._looper_future)
                
            finally:
                # Just in case we're reusable, reset the _thread so start()
                # generates a new one on next call.
                self._thread = None
                if not self.reusable_loop:
                    self.finalize()
        
        # Careful: stop_threadsafe could be waiting on shutdown_complete.
        # Give these an extra layer of protection so that the close() caller
        # can always return, even if closing the loop errored for some reason
        finally:
            self._startup_complete_flag.clear()
            self._shutdown_complete_flag.set()
        
    def stop(self):
        ''' ONLY TO BE CALLED FROM WITHIN OUR RUNNING TASKS! Do NOT call
        this wrapped in a call_coroutine_threadsafe or
        run_coroutine_loopsafe; instead use the direct methods.
        
        Always returns immediately and cannot wait for closure of the
        loop (chicken vs egg).
        '''
        if not self._startup_complete_flag.is_set():
            raise RuntimeError('Cannot stop before startup is complete.')
            
        self._task.cancel()
        
    def stop_threadsafe_nowait(self):
        ''' Stops us from within a different thread without waiting for
        closure.
        '''
        self._loop.call_soon_threadsafe(self.stop)
        
    def stop_threadsafe(self, timeout=None):
        ''' Stops us from within a different thread.
        '''
        self.stop_threadsafe_nowait()
        self._shutdown_complete_flag.wait(timeout=timeout)
        
    async def task_run(self):
        ''' Serves as a landing point for coop multi-inheritance.
        Override this to actually do something.
        '''
        pass
        
    async def _execute_task(self, args, kwargs):
        ''' Actually executes the task at hand.
        '''
        try:
            self._task = asyncio.ensure_future(self.task_run(*args, **kwargs))
            
            # Don't wait to set the startup flag until we return control to the
            # loop, because we already "started" the tasks.
            self._startup_complete_flag.set()
            
            # Raise the task's exception or return its result. More likely
            # than not, this will only happen if the worker finishes first.
            # asyncio handles raising the exception for us here.
            try:
                result = await asyncio.wait_for(self._task, timeout=None)
            
            except asyncio.CancelledError:
                result = None
                
            return result
            
        # Reset the termination flag on the way out, just in case.
        finally:
            self._task = None
            
    def _abort(self):
        ''' Performs any needed cancellation propagation (etc).
        Must only be called from within the event loop.
        '''
        pass
            
    def finalize(self):
        ''' Close the event loop and perform any other necessary
        ManagedTask cleanup. Task cleanup should be handled within the
        task.
        '''
        self._loop.close()
    
    
class TaskLooper(ManagedTask):
    ''' Basically, the Arduino of event loops. Can be invoked directly
    for a single-purpose app loop, or can be added to a LoopaCommanda to
    enable multiple simultaneous app loops.
    
    Requires subclasses to define an async loop_init function and a
    loop_run function. Loop_run is handled within a "while running"
    construct.
    
    Optionally, async def loop_stop may be defined for cleanup.
    '''
        
    async def loop_init(self):
        ''' Endpoint for cooperative multiple inheritance.
        '''
        pass
        
    async def loop_run(self):
        ''' Endpoint for cooperative multiple inheritance.
        '''
        pass
        
    async def loop_stop(self):
        ''' Endpoint for cooperative multiple inheritance.
        '''
        pass
        
    async def task_run(self, *args, **kwargs):
        ''' Wraps up all of the loop stuff.
        '''
        try:
            await self.loop_init(*args, **kwargs)
            
            while True:
                # We need to guarantee that we give control back to the event
                # loop at least once (even if running all synchronous code) to
                # catch any cancellations.
                # TODO: is there a better way than this?
                await asyncio.sleep(0)
                await self.loop_run()
            
        finally:
            # Prevent cancellation of the loop stop.
            await asyncio.shield(self.loop_stop())
        
        
class TaskCommander(ManagedTask):
    ''' Sets up a ManagedTask to run tasks instead of just a single
    coro.
    '''
    
    def __init__(self, *args, **kwargs):
        ''' In addition to super(), we also need to add in some variable
        inits.
        '''
        super().__init__(*args, **kwargs)
        
        # Lookup for task -> future
        self._futures_by_task = {}
        # Lookup for future -> task
        self._tasks_by_future = {}
        # Lookup for task -> start args, kwargs
        self._to_start = {}
        # Lookup for task -> result
        self._results = {}
        
    def register_task(self, task, *args, **kwargs):
        ''' Registers a task to start when the LoopaCommanda is run.
        '''
        if not isinstance(task, ManagedTask):
            raise TypeError('Task must be a ManagedTask instance.')
        
        self._to_start[task] = args, kwargs
        
    def deregister_task(self, task):
        ''' Discards an existing task. Raises ValueError if the task is
        unregistered.
        '''
        try:
            del self._to_start[task]
        except KeyError:
            raise ValueError(
                'Task ' + repr(task) + ' is not currently registered.'
            )
        
    async def task_run(self):
        ''' Runs all of the TaskCommander's tasks.
        '''
        try:
            tasks_available = set()
            for taskman, (args, kwargs) in self._to_start.items():
                task = asyncio.ensure_future(
                    taskman._execute_task(args, kwargs)
                )
                self._futures_by_task[taskman] = task
                self._tasks_by_future[task] = taskman
                tasks_available.add(task)

            # Wait for all tasks to complete (unless cancelled), but process
            # any issues as they happen.
            finished = None
                
            # Wait until the first successful task completion
            while tasks_available:
                finished, pending = await asyncio.wait(
                    fs = tasks_available,
                    return_when = asyncio.FIRST_COMPLETED
                )
            
                # It IS possible to return more than one complete task, even
                # though we've used FIRST_COMPLETED
                for finished_task in finished:
                    tasks_available.discard(finished_task)
                    self._handle_completed(finished_task)
        
        # No matter what happens, cancel all tasks at exit.
        finally:
            try:
                for task in self._tasks_by_future:
                    task.cancel()
                    # Also clear all startup flags to ready for reuse.
                    taskman = self._tasks_by_future[task]
                    taskman._startup_complete_flag.clear()
                    
                # And wait for them all to complete (note that this will delay
                # shutdown!)
                await asyncio.wait(
                    fs = self._tasks_by_future,
                    return_when = asyncio.ALL_COMPLETED
                )
            
            # Reset everything so it's possible to run again.
            finally:
                results = self._results
                self._results = {}
                self._futures_by_task = {}
                self._tasks_by_future = {}

        # This may or may not be useful.
        return results
                
    def _handle_completed(self, task):
        ''' Handles a TaskLooper that completes without cancellation.
        '''
        try:
            # Reset the task startup primitive
            taskman = self._tasks_by_future[task]
            taskman._startup_complete_flag.clear()
            
            exc = task.exception()
            
            # If there's been an exception, continue waiting for the rest.
            if exc is not None:
                logger.error(
                    'Exception while running ' + repr(taskman) + 'w/ ' +
                    'traceback:\n' + ''.join(traceback.format_exception(
                        type(exc), exc, exc.__traceback__)
                    )
                )
            
            else:
                self._results[taskman] = task.result()
        
        # Don't really do anything with these?
        except asyncio.CancelledError:
            logger.info('Task cancelled: ' + repr(taskman))
            
    async def _kill_tasks(self):
        ''' Kill all remaining tasks. Call during shutdown. Will log any
        and all remaining tasks.
        '''
        all_tasks = asyncio.Task.all_tasks()
        
        for task in all_tasks:
            if task is not self._looper_future:
                logger.info('Task remains while closing loop: ' + repr(task))
                task.cancel()
        
        if len(all_tasks) > 0:
            await asyncio.wait(all_tasks, timeout=self._death_timeout)
            
            
class Aengel:
    ''' Watches for completion of the main thread and then automatically
    closes any other threaded objects (that have been registered with
    the Aengel) by calling their close methods.
    
    TODO: redo this as a subclass of threading.Thread.
    '''
    
    def __init__(self, threadname='aengel', guardlings=None):
        ''' Creates an aengel.
        
        Uses threadname as the thread name.
        
        guardlings is an iterable of threaded objects to watch. Each
        must have a stop_threadsafe() method, which will be invoked upon
        completion of the main thread, from the aengel's own thread. The
        aengel WILL NOT prevent garbage collection of the guardling
        objects; they are internally referenced weakly.
        
        They will be called **in the order that they were added.**
        '''
        # I would really prefer this to be an orderedset, but oh well.
        # That would actually break weakref proxies anyways.
        self._guardlings = collections.deque()
        self._dead = False
        self._stoplock = threading.Lock()
        
        if guardlings is not None:
            for guardling in guardlings:
                self.append_guardling(guardling)
            
        self._thread = threading.Thread(
            target = self._watcher,
            daemon = True,
            name = threadname,
        )
        self._thread.start()
        
    def append_guardling(self, guardling):
        if not isinstance(guardling, weakref.ProxyTypes):
            guardling = weakref.proxy(guardling)
            
        self._guardlings.append(guardling)
        
    def prepend_guardling(self, guardling):
        if not isinstance(guardling, weakref.ProxyTypes):
            guardling = weakref.proxy(guardling)
            
        self._guardlings.appendleft(guardling)
        
    def remove_guardling(self, guardling):
        ''' Attempts to remove the first occurrence of the guardling.
        Raises ValueError if guardling is unknown.
        '''
        try:
            self._guardlings.remove(guardling)
        except ValueError:
            logger.error('Missing guardling ' + repr(guardling))
            logger.error('State: ' + repr(self._guardlings))
            raise
    
    def _watcher(self):
        ''' Automatically watches for termination of the main thread and
        then closes the autoresponder and server gracefully.
        '''
        main = threading.main_thread()
        main.join()
        self.stop()
        
    def stop(self, *args, **kwargs):
        ''' Call stop_threadsafe on all guardlings.
        '''
        with self._stoplock:
            if not self._dead:
                for guardling in self._guardlings:
                    try:
                        guardling.stop_threadsafe_nowait()
                    except Exception:
                        # This is very precarious. Swallow all exceptions.
                        logger.error(
                            'Swallowed exception while closing ' +
                            repr(guardling) + '.\n' +
                            ''.join(traceback.format_exc())
                        )
                self._dead = True
