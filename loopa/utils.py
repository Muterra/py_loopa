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
import threading
import traceback
import concurrent.futures


# ###############################################
# Boilerplate
# ###############################################

# Control * imports.
__all__ = [
]


logger = logging.getLogger(__name__)


# ###############################################
# Misc
# ###############################################


def default_to(check, default, comparator=None):
    ''' If check is None, apply default; else, return check.
    '''
    if comparator is None:
        if check is None:
            return default
        else:
            return check
    else:
        if check == comparator:
            return default
        else:
            return check


# ###############################################
# Lib
# ###############################################


def harvest_background_task(task):
    ''' Looks at a completed background task. If it has a result, logs
    it to debug. If it has an error, logs the error.
    '''
    exc = task.exception()
    
    if exc is None:
        result = task.result()
        
        # If there was no result, then debug the completion.
        if result is None:
            logger.debug(
                'Background task completed successfully with no result: ' +
                repr(task)
            )
        
        # There was a result, so upgrade it to info.
        else:
            logger.info(''.join((
                'Background task completed successfully. Result: ',
                repr(result),
                ' (background results are always ignored). Task: ',
                repr(task)
            )))
    
    # The task did not complete successfully. Log the error.
    else:
        logger.error(''.join((
            'Background task DID NOT COMPLETE. Traceback:\n',
            *traceback.format_exception(type(exc), exc, exc.__traceback__)
        )))
        
        
def make_background_future(*args, **kwargs):
    ''' Runs asyncio's ensure_future, and then adds a callback to
    harvest_background_task, and returns the task. Argspec is identical
    to ensure_future.
    '''
    task = asyncio.ensure_future(*args, **kwargs)
    task.add_done_callback(harvest_background_task)
    return task


class _WrappedEvent(asyncio.Event):
    ''' Adds an internal future to the event and gives it any expected
    methods.
    '''
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__result = None
        self.__exc = None
        
    def set(self, result, exc):
        ''' Sets us up with a result and an exception.
        '''
        self.__result = result
        self.__exc = exc
        super().set()
        
    async def wait(self):
        ''' Waits for self, and then returns our result, or raises our
        exception.
        '''
        await super().wait()
        
        if self.__exc is not None:
            raise self.__exc
        else:
            return self.__result


def wrap_threaded_future(fut, loop=None):
    ''' Wraps a threaded future in an async future.
    '''
    # Create an event on our source loop.
    if loop is None:
        loop = asyncio.get_event_loop()
    source_event = _WrappedEvent()
    
    # Create a callback to set the source event's infos
    def callback(fut, loop=loop, source_event=source_event):
        exc = None
        result = None
        
        try:
            exc = fut.exception()
            
            # Only get the result if there was no exception, or this will raise
            # the exception.
            if exc is None:
                result = fut.result()
            
        except concurrent.futures.CancelledError as cancelled:
            exc = cancelled
            
        finally:
            # This is what actually passes the values on
            loop.call_soon_threadsafe(source_event.set, result, exc)
        
    # This will also be called if the fut is cancelled.
    fut.add_done_callback(callback)
    
    # Now wrap the event's wait into a future and return it
    return asyncio.ensure_future(source_event.wait())
            

def wait_threadsafe(fut):
    ''' Wait for the result of an asyncio future from synchronous code.
    Returns it as soon as available.
    '''
    event = threading.Event()
    results = []
    
    # Create a callback to set the event and extract the results
    def callback(fut, event=event):
        exc = None
        result = None
        
        try:
            exc = fut.exception()
            
            # Only get the result if there was no exception, or this will raise
            # the exception.
            if exc is None:
                result = exc.result()
            
        except concurrent.futures.CancelledError as cancelled:
            exc = cancelled
            
        finally:
            results.append(result)
            results.append(exc)
            event.set()
        
    # Add the callback to the future (it will always be run from within the
    # event loop). But make sure to do so in a threadsafe way. Hot damn this is
    # messy.
    fut._loop.call_soon_threadsafe(
        fut.add_done_callback,
        callback
    )
    
    # Now wait for completion and return the exception or result.
    event.wait()
    result, exc = results
    if exc:
        raise exc
    else:
        return result

        
async def run_coroutine_loopsafe(coro, loop):
    ''' Threadsafe, asyncsafe (ie non-loop-blocking) call to run a coro
    in a different event loop. Returns a future that can be awaited from
    within the current loop.
    '''
    # This returns a concurrent.futures.Future, so we need to wait for it, but
    # we cannot block our event loop, soooo...
    thread_future = asyncio.run_coroutine_threadsafe(coro, loop)
    return wrap_threaded_future(thread_future)
    
    
async def await_coroutine_loopsafe(coro, loop, timeout=None):
    ''' Wrapper around run_coroutine_loopsafe that actuall returns the
    result of the coro (or raises its exception).
    '''
    async_future = run_coroutine_loopsafe(coro, loop)
    return (await asyncio.wait_for(async_future, timeout=timeout))
            
            
def await_coroutine_threadsafe(coro, loop):
    ''' Wrapper on asyncio.run_coroutine_threadsafe that makes a coro
    behave as if it were called synchronously. In other words, instead
    of returning a future, it raises the exception or returns the coro's
    result.
    
    Leaving loop as default None will result in asyncio inferring the
    loop from the default from the current context (aka usually thread).
    '''
    fut = asyncio.run_coroutine_threadsafe(
        coro = coro,
        loop = loop
    )
    
    # Block on completion of coroutine and then raise any created exception
    exc = fut.exception()
    if exc:
        raise exc
        
    return fut.result()


def triplicated(func):
    ''' Decorator to make a threadsafe and loopsafe copy of the
    decorated function.
    '''
    func.__triplicate__ = True
    return func
    

# Note: if either Triplicate name, or type subclass changes, need to update
# bottom of __new__
class Triplicate(type):
    ''' Metaclass to handle creation of triplicated (async, threadsafe,
    loopsafe) functions. It will not affect subclasses -- ie, subs will
    have no idea that their parent was created through triplication, and
    are therefore free to alter their metaclass as they'd like. BUT, as
    a flipside, subclasses must explicitly re-declare a Triplicate
    metaclass, if they want to.
    '''
    
    def __new__(mcls, clsname, bases, namespace, *args, **kwargs):
        ''' Modify the existing namespace: create a triplicate API for
        every @triplicate function.
        '''
        threadsafe_suffix = '_threadsafe'
        loopsafe_suffix = '_loopsafe'
        
        triplicates = {}
        
        for name, obj in namespace.items():
            # Only do this for triplicate-decorated functions.
            if hasattr(obj, '__triplicate__'):
                # Create a threadsafe version, memoizing the source coro.
                def threadsafe(self, *args, src_coro=obj, **kwargs):
                    ''' Auto-generated threadsafe function for a
                     (async, threadsafe, loopsafe) API.
                    '''
                    # Note that, because the src_coro is unbound, we have to
                    # pass an explicit self.
                    return await_coroutine_threadsafe(
                        coro = src_coro(self, *args, **kwargs),
                        loop = self._loop
                    )
                    
                # Create a loopsafe version, memoizing the source coro.
                async def loopsafe(self, *args, src_coro=obj, **kwargs):
                    ''' Auto-generated loopsafe function for a
                    triplicate (async, threadsafe, loopsafe) API.
                    '''
                    # Note that, because the src_coro is unbound, we have to
                    # pass an explicit self.
                    return (await await_coroutine_loopsafe(
                        coro = src_coro(self, *args, **kwargs),
                        target_loop = self._loop
                    ))
                    
                # We can't update namespace while iterating over it, so put
                # those into a temp dict.
                threadsafe_name = name + threadsafe_suffix
                loopsafe_name = name + loopsafe_suffix
                triplicates[threadsafe_name] = threadsafe
                triplicates[loopsafe_name] = loopsafe
        
        # Now that we're done iterating, add back in the rest of the API.
        namespace.update(triplicates)
        
        # Return the super()ed class.
        return super().__new__(mcls, clsname, bases, namespace,
                               *args, **kwargs)
