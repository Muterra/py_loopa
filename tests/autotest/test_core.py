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
from loopa.core import TaskManager
from loopa.core import LoopaTroopa


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
    
    
class TaskManagerTester1(TaskManager):
    # Create a default
    output = None
    flag = threading.Event()
    
    async def task_run(self, *args, **kwargs):
        self.output = (args, kwargs)
        self.flag.set()
    
    
class TaskManagerTester2(TaskManager):
    # Create a default
    output = None
    flag1 = threading.Event()
    flag2 = threading.Event()
    
    async def task_run(self, *args, **kwargs):
        try:
            self.output = (args, kwargs)
            self.flag1.set()
            await asyncio.sleep(30)
        finally:
            self.flag2.set()
        
        
class LoopaTroopaTester1(LoopaTroopa):
    initter = None
    runner = None
    stopper = None
    
    async def loop_init(self, *args, limit=10, **kwargs):
        self.limit = int(limit)
        self.initter = (args, kwargs)
        self.runner = 0
        
    async def loop_run(self):
        self.runner += 1
        # We want to make sure it runs exactly the correct number of times.
        # Save exactly one change for the last one, to ensure that we don't
        # re-enter the while loop after calling stop.
        if self.runner >= self.limit:
            await self.stop()
            
    async def loop_stop(self):
        self.stopper = self.initter
        
        
class LoopaTroopaTester2(LoopaTroopa):
    ''' Similar to above, but also tests cancellation of long-running
    loops.
    '''
    initter = None
    runner = None
    stopper = None
    
    async def loop_init(self, *args, limit=10, **kwargs):
        self.limit = int(limit)
        self.initter = (args, kwargs)
        self.runner = 0
        
    async def loop_run(self):
        # We want to make sure it runs exactly the correct number of times.
        # Save exactly one change for the last one, to ensure that we don't
        # re-enter the while loop after calling stop.
        if self.runner < (self.limit - 1):
            self.runner += 1
            print(self.runner)
        else:
            self.runner += 1
            print('STOPPING!')
            await self.stop()
            
    async def loop_stop(self):
        self.stopper = self.initter


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
        
        
class TaskManagerTest(unittest.TestCase):
    def test_foreground(self):
        # Keep the loop open in case we do any other tests in the foreground
        lm = TaskManagerTester1(threaded=False, reusable_loop=True, debug=True)
        
        args = (1, 2, 3)
        kwargs = {'foo': 'bar'}
        
        lm.start(*args, **kwargs)
        args2, kwargs2 = lm.output
        self.assertEqual(args2, args)
        self.assertEqual(kwargs2, kwargs)
        
    def test_background(self):
        lm = TaskManagerTester1(threaded=True, reusable_loop=False, debug=True)
        
        args = (1, 2, 3)
        kwargs = {'foo': 'bar'}
        
        lm.start(*args, **kwargs)
        lm.flag.wait(timeout=30)
        
        args2, kwargs2 = lm.output
        self.assertEqual(args2, args)
        self.assertEqual(kwargs2, kwargs)
        
        # Don't call stop, because we want to make sure the loop closes itself
        # appropriately. Instead, wait for the shutdown flag.
        lm._shutdown_complete_flag.wait(timeout=30)
        
        self.assertTrue(lm._loop.is_closed())
        
    def test_background_stop(self):
        lm = TaskManagerTester2(threaded=True, reusable_loop=False, debug=True)
        
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
        
        
class LoopaTroopaTest(unittest.TestCase):
    ''' Test the loopatroopa.
    '''
    
    def test_simple(self):
        # Keep the loop open in case we do any other tests in the foreground
        lm = LoopaTroopaTester1(threaded=False, reusable_loop=True, debug=True)
        
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
        

if __name__ == "__main__":
    unittest.main()
