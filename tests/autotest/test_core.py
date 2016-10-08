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

from loopa.core import _ThreadHelper


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
        

if __name__ == "__main__":
    unittest.main()
