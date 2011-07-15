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

import re
import unittest

def read_file(filename):
    f = open("/proc/drbd", "r")
    try:
        return f.readlines()
    finally:
        f.close()

def proc_drbd(lines):
    m = re.match('^version: (\S+)', lines[0])
    if m:
        version = m.group(1)
    minors = {}
    minor = None
    device = {}
    for line in lines[2:]:
        m = re.match('^\s*(\d+):\s+(.*)', line)
        if m:
            # start of a new minor number
            if device <> {}:
                minors[minor] = device
                device = {}            
            minor = int(m.group(1))
            for bit in m.group(2).split():
                # pull the key:value pairs apart
                index = bit.find(":")
                if index <> -1:
                    key = bit[:index]
                    val = bit[index+1:]
                    device[key] = val
        m = re.match(".*sync'ed:\s*(\S+)", line)
        if m:
            device["progress"] = float(m.group(1)[:-1])
        m = re.match("\s*finish: (\S+)", line)
        if m:
            device["finish"] = str(m.group(1))
    if device <> {}:
        minors[minor] = device
    return {
        "version": version,
        "devices": minors
        }

header = [ "version: 8.0.14 (api:86/proto:86)\n",
           "GIT-hash: bb447522fc9a87d0069b7e14f0234911ebdab0f7 build by phil@fat-tyre, 2008-11-12 16:40:33\n" ]

class Proc_drbd_test(unittest.TestCase):
    def testNoDevice(self):
        """Check that zero devices parse correctly"""
        x = proc_drbd(header)
        self.failUnless(x["version"] == "8.0.14")
        self.failUnless(x["devices"] == {})

    def testUnconfigured(self):
        """Check that unconfigured devices parse correctly"""
        x = proc_drbd(header + [
                "\n",
                " 1: cs:Unconfigured\n"])
        self.failUnless(x["version"] == "8.0.14")
        self.failUnless(x["devices"][1] == { "cs": "Unconfigured" })

    def testMultipleDevices(self):
        """Check that multiple devices are parsed correctly"""
        x = proc_drbd(header + [
                "\n",
                " 1: cs:Unconfigured\n",
                " 2: cs:Connected st:Secondary/Secondary ds:UpToDate/UpToDate C r---\n",
                "    ns:0 nr:0 dw:0 dr:0 al:0 bm:0 lo:0 pe:0 ua:0 ap:0\n",
                "	resync: used:0/61 hits:0 misses:0 starving:0 dirty:0 changed:0\n",
                "	act_log: used:0/127 hits:0 misses:0 starving:0 dirty:0 changed:0\n"
                ])
        self.failUnless(len(x["devices"].keys()) == 2)
        
    def testSynchronised(self):
        """Check that a synchronised mirror parses correctly"""
        x = proc_drbd(header + [
                "\n",
                " 1: cs:Connected st:Primary/Secondary ds:UpToDate/UpToDate C r---\n",
                "    ns:8257410 nr:0 dw:0 dr:8257410 al:0 bm:504 lo:0 pe:0 ua:0 ap:0\n",
                "    resync: used:0/61 hits:4128202 misses:504 starving:0 dirty:0 changed:504\n",
                "    act_log: used:0/127 hits:0 misses:0 starving:0 dirty:0 changed:0\n"
                ])
        self.failUnless(x["version"] == "8.0.14")
        self.failUnless(x["devices"][1]["cs"] == "Connected")
        self.failUnless(x["devices"][1]["st"] == "Primary/Secondary")
        self.failUnless(x["devices"][1]["ds"] == "UpToDate/UpToDate")

    def testSynchronising(self):
        """Check that a synchronising mirror parses correctly"""
        x = proc_drbd(header + [
                " 1: cs:SyncSource st:Primary/Secondary ds:UpToDate/Inconsistent C r---\n",
                "    ns:5592 nr:0 dw:0 dr:5592 al:0 bm:0 lo:0 pe:0 ua:0 ap:0\n",
                "	[>....................] sync'ed:  0.1% (8058/8063)M\n",
                "	finish: 8:35:44 speed: 252 (240) K/sec\n",
                "	resync: used:0/61 hits:2795 misses:1 starving:0 dirty:0 changed:1\n",
                "	act_log: used:0/127 hits:0 misses:0 starving:0 dirty:0 changed:0\n"
                ])
        self.failUnless(x["version"] == "8.0.14")
        self.failUnless(x["devices"][1]["progress"] - 0.1 < 0.001)
        self.failUnless(x["devices"][1]["finish"] == "8:35:44")

if __name__ == "__main__":
    unittest.main ()

