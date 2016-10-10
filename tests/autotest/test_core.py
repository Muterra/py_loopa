'''
LICENSING
-------------------------------------------------

Loopa: Arduino-esque event loop app framework.
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

import unittest
import threading
import queue
import asyncio
import atexit

from loopa.core import _ThreadHelper
from loopa.core import ManagedTask
from loopa.core import TaskLooper
from loopa.core import TaskCommander


# ###############################################
# Cleanup stuff
# ###############################################


def cleanup():
    myloop = asyncio.get_event_loop()
    myloop.close()
    

atexit.register(cleanup)


# ###############################################
# "Paragon of adequacy" test fixtures
# ###############################################


def make_target():
    flag = threading.Event()
    q = queue.Queue()
    
    def target(args, kwargs):
        q.put(args)
        q.put(kwargs)
        flag.set()
        
    return flag, q, target
    
    
class ManagedTaskTester1(ManagedTask):
    # Create a default
    reoutput = None
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.flag = threading.Event()
    
    async def task_run(self, *args, **kwargs):
        self.reoutput = (args, kwargs)
        self.flag.set()
    
    
class ManagedTaskTester2(ManagedTask):
    # Create a default
    output = None
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.flag1 = threading.Event()
        self.flag2 = threading.Event()
    
    async def task_run(self, *args, **kwargs):
        try:
            self.output = (args, kwargs)
            self.flag1.set()
            await asyncio.sleep(30)
        finally:
            self.flag2.set()
        
        
class TaskLooperTester1(TaskLooper):
    initter = None
    runner = None
    stopper = None
    
    async def loop_init(self, *args, limit=10, **kwargs):
        self.limit = int(limit)
        self.initter = (args, kwargs)
        self.runner = 0
        
    async def loop_run(self):
        # We want to make sure it runs exactly the correct number of times.
        # Therefore, always increment, even if above limit.
        self.runner += 1
        # Call stop exactly once, at the limit
        if self.runner == self.limit:
            await self.stop()
        # If we exceed it sufficiently, raise to exit.
        elif self.runner >= (2 * self.limit):
            raise asyncio.CancelledError()
            
    async def loop_stop(self):
        self.stopper = self.initter
        
        
class TaskLooperTester2(TaskLooper):
    ''' Same as above, but cancelled from a different thread.
    '''
    initter = None
    runner = None
    stopper = None
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dime = threading.Event()
        self._nickel = threading.Event()
    
    def stop_on_dime(self):
        try:
            self._dime.wait()
            self.stop_threadsafe_nowait()
        finally:
            self._nickel.set()
    
    async def loop_init(self, *args, limit=10, **kwargs):
        self._breakerworker = threading.Thread(
            target=self.stop_on_dime,
            daemon=True
        )
        self._breakerworker.start()
        
        self.limit = int(limit)
        self.initter = (args, kwargs)
        self.runner = 0
        
    async def loop_run(self):
        # We want to make sure it runs exactly the correct number of times.
        # Therefore, always increment, even if above limit.
        self.runner += 1
        # Save exactly one change for the last one, to ensure that we don't
        # re-enter the while loop after calling stop.
        if self.runner == self.limit:
            self._dime.set()
            self._nickel.wait()
        # If we exceed it sufficiently, raise to exit.
        elif self.runner >= (2 * self.limit):
            raise asyncio.CancelledError()
            
    async def loop_stop(self):
        self.stopper = self.initter
        
        
class TaskCommanderTester1(TaskLooper):
    ''' TaskLooper for testing the TaskCommander.
    '''


# ###############################################
# Testing
# ###############################################
        
        
class ThreadhelperTest(unittest.TestCase):
    def test_thelper(self):
        flag, q, target = make_target()
        
        args = [1, 2, 3]
        kwargs = {'foo': 'bar'}
        
        thelper = _ThreadHelper(daemon=True)
        thelper.set_target(target, args, kwargs)
        thelper.start()
        flag.wait(timeout=30)
        
        args2 = q.get()
        kwargs2 = q.get()
        
        self.assertEqual(args, args2)
        self.assertEqual(kwargs, kwargs2)
        
        
class ManagedTaskTest(unittest.TestCase):
    def test_foreground(self):
        # Keep the loop open in case we do any other tests in the foreground
        lm = ManagedTaskTester1(threaded=False, reusable_loop=True, debug=True)
        
        args = (1, 2, 3)
        kwargs = {'foo': 'bar'}
        
        lm.start(*args, **kwargs)
        args2, kwargs2 = lm.reoutput
        self.assertEqual(args2, args)
        self.assertEqual(kwargs2, kwargs)
        
    def test_background(self):
        lm = ManagedTaskTester1(threaded=True, reusable_loop=False, debug=True)
        
        args = (1, 2, 3)
        kwargs = {'foo': 'bar'}
        
        lm.start(*args, **kwargs)
        lm.flag.wait(timeout=30)
        
        args2, kwargs2 = lm.reoutput
        self.assertEqual(args2, args)
        self.assertEqual(kwargs2, kwargs)
        
        # Don't call stop, because we want to make sure the loop closes itself
        # appropriately. Instead, wait for the shutdown flag.
        lm._shutdown_complete_flag.wait(timeout=30)
        
        self.assertTrue(lm._loop.is_closed())
        
    def test_background_stop(self):
        lm = ManagedTaskTester2(threaded=True, reusable_loop=False, debug=True)
        
        args = (1, 2, 3)
        kwargs = {'foo': 'bar'}
        
        lm.start(*args, **kwargs)
        lm.flag1.wait(timeout=30)
        
        # Ensure it stops before the end of the sleep call
        lm.stop_threadsafe(timeout=5)
        lm.flag2.wait(timeout=5)
        
        args2, kwargs2 = lm.output
        self.assertEqual(args2, args)
        self.assertEqual(kwargs2, kwargs)
        self.assertTrue(lm._loop.is_closed())
        
        
class TaskLooperTest(unittest.TestCase):
    ''' Test the TaskLooper.
    '''
    
    def test_self_stop(self):
        # Keep the loop open in case we do any other tests in the foreground
        lm = TaskLooperTester1(threaded=False, reusable_loop=True, debug=True)
        
        limit = 10
        args = (1, 2, 3)
        kwargs = {'foo': 'bar'}
        
        lm.start(limit=limit, *args, **kwargs)
        args2, kwargs2 = lm.initter
        args3, kwargs3 = lm.stopper
        self.assertEqual(args2, args)
        self.assertEqual(args3, args)
        self.assertEqual(kwargs2, kwargs)
        self.assertEqual(kwargs3, kwargs)
        self.assertEqual(lm.runner, limit)
    
    def test_threaded_stop(self):
        # Keep the loop open in case we do any other tests in the foreground
        lm = TaskLooperTester2(threaded=True, reusable_loop=False, debug=True)
        
        limit = 10
        args = (1, 2, 3)
        kwargs = {'foo': 'bar'}
        
        lm.start(limit=limit, *args, **kwargs)
        lm.stop_on_dime()
        lm._shutdown_complete_flag.wait(timeout=10)
        
        args2, kwargs2 = lm.initter
        args3, kwargs3 = lm.stopper
        self.assertEqual(args2, args)
        self.assertEqual(args3, args)
        self.assertEqual(kwargs2, kwargs)
        self.assertEqual(kwargs3, kwargs)
        self.assertEqual(lm.runner, limit)
        
        
class TaskCommanderTest(unittest.TestCase):
    def test_simple_nostop(self):
        tm1 = ManagedTaskTester1()
        tm2 = ManagedTaskTester1()
        
        com = TaskCommander(reusable_loop=True, debug=True)
        
        args = (1, 2, 3)
        kwargs = {'foo': 'bar'}
        
        com.register_task(tm1, *args, **kwargs)
        com.register_task(tm2, *args, **kwargs)
        
        com.start()
        tm1.flag.wait(timeout=30)
        tm2.flag.wait(timeout=30)
        
        args2, kwargs2 = tm1.reoutput
        self.assertEqual(args2, args)
        self.assertEqual(kwargs2, kwargs)
        
        args3, kwargs3 = tm2.reoutput
        self.assertEqual(args3, args)
        self.assertEqual(kwargs3, kwargs)
        
        # Don't call stop, because we want to make sure the loop closes itself
        # appropriately. Instead, wait for the shutdown flag.
        com._shutdown_complete_flag.wait(timeout=30)
        
    def test_simple_stop(self):
        tm1 = ManagedTaskTester2()
        tm2 = ManagedTaskTester2()
        
        com = TaskCommander(threaded=True, reusable_loop=False, debug=True)
        
        args = (1, 2, 3)
        kwargs = {'foo': 'bar'}
        
        com.register_task(tm1, *args, **kwargs)
        com.register_task(tm2, *args, **kwargs)
        
        com.start()
        tm1.flag1.wait(timeout=30)
        tm2.flag1.wait(timeout=30)
        
        # Ensure it stops before the end of the sleep call
        com.stop_threadsafe(timeout=5)
        tm1.flag2.wait(timeout=5)
        tm2.flag2.wait(timeout=5)
        
        args2, kwargs2 = tm1.output
        self.assertEqual(args2, args)
        self.assertEqual(kwargs2, kwargs)
        
        args3, kwargs3 = tm2.output
        self.assertEqual(args3, args)
        self.assertEqual(kwargs3, kwargs)
        
        # Don't call stop, because we want to make sure the loop closes itself
        # appropriately. Instead, wait for the shutdown flag.
        com._shutdown_complete_flag.wait(timeout=30)
        

if __name__ == "__main__":
    unittest.main()
