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

from loopa.core import _ThreadHelper
from loopa.core import TaskManager


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
    flag = threading.Event()
    
    async def task_run(self, *args, **kwargs):
        self.output = (args, kwargs)
        self.flag.set()
        await asyncio.sleep(30)


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
        lm = TaskManagerTester1(threaded=False, reusable_loop=True)
        
        args = (1, 2, 3)
        kwargs = {'foo': 'bar'}
        
        lm.start(*args, **kwargs)
        args2, kwargs2 = lm.output
        self.assertEqual(args2, args)
        self.assertEqual(kwargs2, kwargs)
        
    def test_background(self):
        lm = TaskManagerTester1(threaded=True, reusable_loop=False)
        
        args = (1, 2, 3)
        kwargs = {'foo': 'bar'}
        
        lm.start(*args, **kwargs)
        lm.flag.wait(timeout=30)
        
        args2, kwargs2 = lm.output
        self.assertEqual(args2, args)
        self.assertEqual(kwargs2, kwargs)
        
    def test_background_stop(self):
        lm = TaskManagerTester2(threaded=True, reusable_loop=False)
        
        args = (1, 2, 3)
        kwargs = {'foo': 'bar'}
        
        lm.start(*args, **kwargs)
        lm.flag.wait(timeout=30)
        
        lm.stop_threadsafe(timeout=30)
        
        args2, kwargs2 = lm.output
        self.assertEqual(args2, args)
        self.assertEqual(kwargs2, kwargs)
        self.assertTrue(lm._loop.is_closed())
        
    @classmethod
    def tearDownClass(cls):
        myloop = asyncio.get_event_loop()
        myloop.close()
        

if __name__ == "__main__":
    unittest.main()
