#!/usr/bin/python
# Copyright (C) Citrix
#
# This program is free software; you can redistribute it and/or modify 
# it under the terms of the GNU Lesser General Public License as published 
# by the Free Software Foundation; version 2.1 only.
#
# This program is distributed in the hope that it will be useful, 
# but WITHOUT ANY WARRANTY; without even the implied warranty of 
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the 
# GNU Lesser General Public License for more details.
#

from util import run

import re

# Use Linux "losetup" to create block devices from files
class Loop:
    # [list] returns the currently-assigned loop devices
    def list(self):
        results = {}
        for line in run(["losetup", "-a"]):
            m = re.match('^(\S+):.+\((\S+)\)', line)
            if m:
                loop = m.group(1)
                this_path = m.group(2)
                results[loop] = this_path
        return results
    # [add task path] creates a new loop device for [path] and returns it
    def add(self, path):
        run(["losetup", "-f", path])
        all = self.list()
        for loop in all:
            if all[loop] == path:
                return loop
        return None
    # [remove task path] removes the loop device associated with [path]
    def remove(self, loop):
        run(["losetup", "-d", str(loop)])

import unittest, os, util
class LoopTest(unittest.TestCase):
    def setUp(self):
        self.filename1 = util.make_sparse_file(16L * 1024L * 1024L)
        self.filename2 = util.make_sparse_file(16L * 1024L * 1024L)
    def tearDown(self):
        os.unlink(self.filename1)
        os.unlink(self.filename2)
    def testLoop(self):
        l = Loop()
        x = l.add(self.filename1)
        y = l.add(self.filename2)
        self.failUnless(x <> y)
        l.remove(x)
        l.remove(y)

if __name__ == "__main__":
    unittest.main()
