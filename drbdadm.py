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

def drbd_conf(config):
    return [
        "global {",
        "  usage-count no;",
        "}",
        "common {",
        "  protocol C;",
        "}",
        "resource %s {" % config["uuid"],
        "  on %s {" % config["hosts"][0]["name"],
        "    device %s;" % config["hosts"][0]["device"],
        "    disk %s;" % config["hosts"][0]["disk"],
        "    address %s;" % config["hosts"][0]["address"],
        "    flexible-meta-disk %s;" % config["hosts"][0]["md"],
        "  }",
        "  on %s {" % config["hosts"][1]["name"],
        "    device %s;" % config["hosts"][1]["device"],
        "    disk %s;" % config["hosts"][1]["disk"],
        "    address %s;" % config["hosts"][1]["address"],
        "    flexible-meta-disk %s;" % config["hosts"][1]["md"],
        "  }",
        "}"
        ]

class Drbd_conf_test(unittest.TestCase):
    def testConfigPrint(self):
        """test the drbd.conf printer"""
        # XXX: later version of drbd support 'floating' arguments: this
        # matches on IP rather than hostname (probably better for us)
        host = {
            "name": "name",
            "device": "/dev/drbd1",
            "disk": "/dev/tap",
            "address": "127.0.0.1:8080",
            "md": "/dev/loop0"
            }
        config = {
            "uuid": "theuuid",
            "hosts": [ host, host ]
            }
        x = drbd_conf(config)

import math
def size_needed_for_md(bytes_per_sector, sectors):
    """Given a particular size of disk which needs replication, compute
    the minimum size of flex-meta-disk"""
    # From http://www.drbd.org/users-guide/ch-internals.html
    ms = long(math.ceil(float(sectors) / (2.0 ** 18)) * 8L) + 72L
    return ms * bytes_per_sector

class Size_needed_for_md_test(unittest.TestCase):
    def testSmall(self):
        size = size_needed_for_md(512, 8L * 1024L * 1024L * 2L)
        self.failUnless(size == 299008L)

def free_minor_number(drbd):
    """Returns a DRBD minor number which is currently free. Note someone
    else may come along and allocate this one for us, so we have to be
    prepared to retry"""
    free_minor = 1
    while True:
        if free_minor not in drbd["devices"]:
            # this one is free
            return free_minor
        if drbd["devices"][free_minor]["cs"] == "Unconfigured":
            # we can use a spare unconfigured one
            return free_minor
        free_minor = free_minor + 1

class Free_minor_number_test(unittest.TestCase):
    def testBasecase(self):
        """If no minors are configured, then 1 is free"""
        self.failUnless(free_minor_number({"devices": []}) == 1)
    def testHole(self):
        """If an early minor is set to 'Unconfigured', use it"""
        devices = {
            1: { "cs": "XXX" },
            2: { "cs": "Unconfigured" },
            3: { "cs": "XXX" }
            }
        free = free_minor_number({"devices": devices})
        self.failUnless(free == 2)
    def testLots(self):
        """If the 1, 2, 3 are all allocated (but returned out-of-order)
        then the next one is 4"""
        devices = {
            3: { "cs": "XXX" },
            2: { "cs": "XXX" },
            1: { "cs": "XXX" }
            }
        self.failUnless(free_minor_number({"devices": devices}) == 4
)

# Need to be able to keep retrying since allocation of free minor
# numbers and free port numbers may race with other activities on
# the same host.

class Localdevice:
    def __init__(self, drbd, disk):
        self.hostname = os.uname()[1]
        self.minor = free_minor_number(drbd)
        bytes_per_sector = util.block_device_sector_size(disk)
        sectors = util.block_device_sectors(disk)
        mdsize = size_needed_for_md(bytes_per_sector, sectors)
        self.md_file = util.make_sparse_file(mdsize)
        l = losetup.Loop()
        self.loop = l.add(self.md_file)
        self.address = util.replication_ip()
        self.port = util.replication_port(self.address)
    def __del__(self):
        # Remove loop device
        l = losetup.Loop()
        l.remove(self.loop)
        # Remove the temporary file
        os.unlink(self.md_file)
        
# TEST: need to test Localdevice

def read_proc_drbd():
    return proc_drbd(read_file("/proc/drbd"))



if __name__ == "__main__":
    unittest.main ()

