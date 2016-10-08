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

import logging
import asyncio
import abc
import threading
import weakref
import traceback
import collections
import inspect


# ###############################################
# Boilerplate
# ###############################################

# Control * imports.
__all__ = [
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
        ''' Do this so that LoopManager's start() method can pass args
        and kwargs to the target.
        '''
        self.__target = target
        self.__args = args
        self.__kwargs = kwargs
    
    def run(self):
        ''' Call to self.__target, passing self.__args and self.__kwargs
        '''
        self.__target(self.__args, self.__kwargs)


class LoopManager:
    ''' Manages thread shutdown (etc) for a thread whose sole purpose is
    running an event loop.
    '''
    
    def __init__(self, threaded, debug=False, aengel=None, reusable_loop=False,
                 start_timeout=None, *args, **kwargs):
        ''' Creates a LoopManager.
        
        *args and **kwargs will be passed to the threading.Thread
        constructor iff threaded=True. Otherwise, they will be ignored.
        
        Loop init arguments should be passed through the start() method.
        
        if executor is None, defaults to the normal executor.
        
        if reusable_loop=True, the LoopManager can be run more than
        once, but you're responsible for manually calling finalize() to
        clean up the loop. Except this doesn't work at the moment,
        because the internal thread is not reusable.
        '''
        if aengel is not None:
            aengel.prepend_guardling(self)
            
        self._debug = bool(debug)
        self.reusable_loop = bool(reusable_loop)
        self._start_timeout = start_timeout
        
        # This flag will be set to initiate termination.
        self._term_flag = None
        
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
                    'LoopManager: ' + str(exc)
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
        
    async def stop(self):
        ''' ONLY TO BE CALLED FROM WITHIN OUR RUNNING TASKS! Do NOT call
        this wrapped in a call_coroutine_threadsafe or
        run_coroutine_loopsafe; instead use the direct methods.
        
        Always returns immediately and cannot wait for closure of the
        loop (chicken vs egg).
        '''
        if not self._startup_complete_flag.is_set():
            raise RuntimeError('Cannot stop before startup is complete.')
            
        self._term_flag.set()
        
    def stop_threadsafe_nowait(self):
        ''' Stops us from within a different thread without waiting for
        closure.
        '''
        if not self._startup_complete_flag.is_set():
            raise RuntimeError('Cannot stop before startup is complete.')
            
        self._loop.call_soon_threadsafe(self._term_flag.set)
        
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
            self._term_flag = asyncio.Event()
            aborter = asyncio.ensure_future(self._term_flag.wait())
            worker = asyncio.ensure_future(self.task_run(*args, **kwargs))
            
            # Wait to set the startup flag until we return control to the loop
            self._loop.call_soon_threadsafe(self._startup_complete_flag.set)
            
            finished, pending = await asyncio.wait(
                fs = {aborter, worker},
                return_when = asyncio.FIRST_COMPLETED
            )
            
            # Unpack both sets, which will be of length 1.
            pending, = pending
            finished, = finished
            
            # Cancel the remaining task (doesn't matter which it is).
            pending.cancel()
            
            # Raise the task's exception or return its result. More likely
            # than not, this will only happen if the worker finishes first.
            # asyncio handles raising the exception for us here.
            return finished.result()
            
        # Reset the termination flag on the way out, just in case.
        finally:
            self._term_flag = None
            
    def finalize(self):
        ''' Close the event loop and perform any other necessary
        LoopManager cleanup. Task cleanup should be handled within the
        task.
        '''
        self._loop.close()
        
        
class LoopaCommanda(LoopManager):
    ''' Sets up a LoopManager to run LoopaTroopas instead of a single
    coro.
    '''
    
    
class LoopaTroopa(LoopManager):
    ''' Basically, the Arduino of event loops. Can be invoked directly
    for a single-purpose app loop, or can be added to a LoopaCommanda to
    enable multiple simultaneous app loops.
    
    Requires subclasses to define an async loop_init function and a
    loop_run function. Loop_run is handled within a "while running"
    construct.
    
    Optionally, async def loop_stop may be defined for cleanup.
    
    LooperTrooper handles threading, graceful loop exiting, etc.
    
    if threaded evaluates to False, must call LooperTrooper().start() to
    get the ball rolling.
    
    If aengel is not None, will immediately attempt to register self
    with the aengel to guard against main thread completion causing an
    indefinite hang.
    
    *args and **kwargs are passed to the required async def loop_init.
    '''
    def __init__(self, threaded, thread_name=None, debug=False, aengel=None, *args, **kwargs):
        if aengel is not None:
            aengel.prepend_guardling(self)
        
        super().__init__(*args, **kwargs)
        
        self._startup_complete_flag = threading.Event()
        self._shutdown_init_flag = None
        self._shutdown_complete_flag = threading.Event()
        self._debug = debug
        self._death_timeout = 1
        
        if threaded:
            self._loop = asyncio.new_event_loop()
            # Set up a thread for the loop
            self._thread = threading.Thread(
                target = self.start,
                args = args,
                kwargs = kwargs,
                # This may result in errors during closing.
                # daemon = True,
                # This isn't currently stable enough to close properly.
                daemon = False,
                name = thread_name
            )
            self._thread.start()
            self._startup_complete_flag.wait()
            
        else:
            self._loop = asyncio.get_event_loop()
            # Declare the thread as nothing.
            self._thread = None
        
    async def loop_init(self):
        ''' This will be passed any *args and **kwargs from self.start,
        either through __init__ if threaded is True, or when calling
        self.start directly.
        '''
        pass
        
    @abc.abstractmethod
    async def loop_run(self):
        pass
        
    async def loop_stop(self):
        pass
        
    def start(self, *args, **kwargs):
        ''' Handles everything needed to start the loop within the
        current context/thread/whatever. May be extended, but MUST be
        called via super().
        '''
        try:
            self._loop.set_debug(self._debug)
            
            if self._thread is not None:
                asyncio.set_event_loop(self._loop)
            
            # Set up a shutdown event and then start the task
            self._shutdown_init_flag = asyncio.Event()
            self._looper_future = asyncio.ensure_future(
                self._execute_looper(*args, **kwargs)
            )
            self._loop.run_until_complete(self._looper_future)
            
        finally:
            self._loop.close()
            # stop_threadsafe could be waiting on this.
            self._shutdown_complete_flag.set()
        
    def stop(self):
        ''' Stops the loop INTERNALLY.
        '''
        self._shutdown_init_flag.set()
    
    def stop_threadsafe(self):
        ''' Stops the loop EXTERNALLY.
        '''
        self.stop_threadsafe_nowait()
        self._shutdown_complete_flag.wait()
    
    def stop_threadsafe_nowait(self):
        ''' Stops the loop EXTERNALLY.
        '''
        if not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._shutdown_init_flag.set)
        
    async def catch_interrupt(self):
        ''' Workaround for Windows not passing signals well for doing
        interrupts.
        
        Standard websockets stuff.
        
        Deprecated? Currently unused anyways.
        '''
        while not self._shutdown_init_flag.is_set():
            await asyncio.sleep(5)
            
    async def _execute_looper(self, *args, **kwargs):
        ''' Called by start(), and actually manages control flow for
        everything.
        '''
        await self.loop_init(*args, **kwargs)
        
        try:
            while not self._shutdown_init_flag.is_set():
                await self._step_looper()
                
        except CancelledError:
            pass
            
        finally:
            # Prevent cancellation of the loop stop.
            await asyncio.shield(self.loop_stop())
            await self._kill_tasks()
            
    async def _step_looper(self):
        ''' Execute a single step of _execute_looper.
        '''
        task = asyncio.ensure_future(self.loop_run())
        interrupt = asyncio.ensure_future(self._shutdown_init_flag.wait())
        
        if not self._startup_complete_flag.is_set():
            self._loop.call_soon(self._startup_complete_flag.set)
            
        finished, pending = await asyncio.wait(
            fs = [task, interrupt],
            return_when = asyncio.FIRST_COMPLETED
        )
        
        # Note that we need to check both of these, or we have a race
        # condition where both may actually be done at the same time.
        if task in finished:
            # Raise any exception, ignore result, rinse, repeat
            self._raise_if_exc(task)
        else:
            task.cancel()
            
        if interrupt in finished:
            self._raise_if_exc(interrupt)
        else:
            interrupt.cancel()
            
    async def _kill_tasks(self):
        ''' Kill all remaining tasks. Call during shutdown. Will log any
        and all remaining tasks.
        '''
        all_tasks = asyncio.Task.all_tasks()
        
        for task in all_tasks:
            if task is not self._looper_future:
                logging.info('Task remains while closing loop: ' + repr(task))
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
