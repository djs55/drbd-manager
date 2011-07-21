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

def proc_drbd(lines):
    """Parse [lines] (from /proc/drbd) and return a dictionary"""
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

# Example header from /proc/drbd
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
    """Given [config] (a dictionary representing a proposed drbd configuration)
    return the corresponding drbd.conf"""
    # XXX: later version of drbd support 'floating' arguments: this
    # matches on IP rather than hostname (probably better for us)
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

def make_simple_config(minor, port):
    """Generate a valid-looking drbd.conf given a device [minor] and network [port]"""
    host = {
        "name": "name",
        "device": "/dev/drbd%d" % minor,
        "disk": "/dev/tap",
        "address": "127.0.0.1:%d" % port,
        "md": "/dev/loop0"
        }
    return {
        "uuid": "%d.%d" % (minor, port),
        "hosts": [ host, host ]
        }

def get_this_host(config):
    """Return the localhost element from a drbd config"""
    return config["hosts"][0]

def minor_of_config(config):
    """Return the device minor in use on localhost from a drbd config"""
    prefix = "/dev/drbd"
    return int(get_this_host(config)["device"][len(prefix):])

def port_of_config(config):
    """Return the port in use on localhost from a drbd config"""
    return int(get_this_host(config)["address"].split(":")[1])

class Drbd_conf_test(unittest.TestCase):
    def testConfigPrint(self):
        """test the drbd.conf printer"""
        x = drbd_conf(make_simple_config(1, 8080))

import math
def size_needed_for_md(bytes_per_sector, sectors):
    """Given a particular size of disk which needs replication, compute
    the minimum size of flex-meta-disk"""
    # From http://www.drbd.org/users-guide/ch-internals.html
    ms = long(math.ceil(float(sectors) / (2.0 ** 18)) * 8L) + 72L
    return ms * bytes_per_sector

class Size_needed_for_md_test(unittest.TestCase):
    def testSmall(self):
        """Test the metadata disk size calculation"""
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

# Where we will store our drbd.conf fragments
conf_dir = "/var/run/sm/drbd"

class TransientException(Exception):
    """An exception which should be handled by retrying"""
    pass

class MinorInUse(TransientException):
    """DRBD reports that the requested minor number is in use"""
    def __init__(self, minor):
        self.minor = minor
    def __str__(self):
        return "The DRBD device minor number %d is in use" % self.minor

class PortInUse(TransientException):
    """DRBD reports that the requested port number is in use"""
    def __init__(self, port):
        self.port = port
    def __str__(self):
        return "The port number %d is in use" % self.port

class Drbd:
    """Represents the real drbd system"""
    def _read_proc_drbd():
        return proc_drbd(util.read_file("/proc/drbd"))
    def _get_drbdadm_conf(self, config):
        return conf_dir + "/" + config["uuid"]
    def _run_drbdadm(self, config, args):
        util.run(["/sbin/drbdadm", "-c", self._get_drbdadm_conf(config)] + args + [self.config["uuid"]])
    
    def __init__(self):
        self.configs = []
        self.connected = {}
        self.allocated_minors = {}
    def version(self):
        drbd = self._read_proc_drbd()
        return drbd["version"]
    def get_free_minor_number(self):
        return free_minor_number(self.read_proc_drbd())
    def get_replication_ip(self):
        return util.get_replication_ip()
    def get_replication_port(self, ip):
        return util.get_replication_port(ip)
    def stop(self, config):
        if config in self.connected:
            self._run_drbdadm(config, ["disconnect"])
            self.connected.remove(config)
        if config in self.allocated_minors:
            self._run_drbdadm(config, ["detach"])
            self.allocated_minors.remove(config)
        self.configs.remove(config)
        os.unlink(self._get_drbdadm_conf(config))

    def _start(self, config):
        self.configs.append(config)
        os.makedirs(conf_dir)
        f = open(self._get_drbdadm_conf(config), "w")
        try:
            f.write(drbd_conf(config))
        finally:
            f.close()
        try:
            # Since we expect to occasionally clash over minor numbers we
            # mustn't use "up" and "down": "up" would fail and then "down"
            # would bring down someone else's device
            if config in self.allocated_minors:
                self.allocated_minors.remove(config)
            if config in self.connected:
                self.connected.remove(config)
            self._run_drbdadm(config, ["create-dm"])
            self._run_drbdadm(config, ["attach"])
            self.allocated_minors.append(config)
            self._run_drbdadm(config, ["syncer"])
            self._run_drbdadm(config, ["connect"])
            self.connected.add(config)
        except CommandError, e:
            # Device '/dev/drbdN' is configured!
            if e.code <> 0 and e.output[0].endswith("is configured!\n"):
                raise MinorInUse(minor_of_config(config))
            # /dev/drbd2: Failure: (102) Local address(port) already in use.
            elif e.code <> 0 and e.output[0].endswith("Local address(port) already in use.\n"):
                raise PortInUse(port_of_config(config))
            else:
                raise
    def start(self, config):
        try:
            self._start(config)
        except e:
            self.stop(config)
            raise

class Drbd_simulator:
    """A simulation of the real drbd system"""
    def __init__(self):
        self.version_number = "simulator"
        self.configs = {}
    def version(self):
        return self.version_number
    def get_free_minor_number(self):
        return max([0] + (map(lambda x:minor_of_config(x), self.configs.values()))) + 1
    def get_replication_ip(self):
        return "127.0.0.1"
    def get_replication_port(self, ip):
        ports = map(lambda x:port_of_config(x), self.configs.values())
        return max([7788] + ports) + 1
    def start(self, config):
        #print "start self.configs=%s config=%s" % (repr(self.configs), repr(config))
        this_minor = minor_of_config(config)
        this_port = port_of_config(config)
        for other_config in self.configs.values():
            other_minor = minor_of_config(other_config)
            other_port = port_of_config(other_config)
            if other_minor == this_minor:
                raise MinorInUse(this_minor)
            if other_port == this_port:
                raise PortInUse(this_port)
        self.configs[config["uuid"]] = config
    def stop(self, config):
        # drdbadm down is idempotent
        if config["uuid"] in self.configs.keys():
            del self.configs[config["uuid"]]
        
class Drbd_simulator_test(unittest.TestCase):
    def setUp(self):
        self.drbd = Drbd_simulator()
    def testMinorInUse(self):
        """Check the DRBD simulator correctly throws MinorInUse"""
        self.drbd.start(make_simple_config(1, 8080))
        self.assertRaises(MinorInUse, lambda:self.drbd.start(make_simple_config(1, 8081)))
    def testPortInUse(self):
        """Check the DRBD simulator correctly throws PortInUse"""
        self.drbd.start(make_simple_config(1, 8080))
        self.assertRaises(PortInUse, lambda:self.drbd.start(make_simple_config(2, 8080)))
    def testGetReplicationPort(self):
        """Check the DRBD simulator correctly allocates replication ports"""
        ip = self.drbd.get_replication_ip()
        port = self.drbd.get_replication_port(ip)
        self.drbd.start(make_simple_config(1, port))
        self.failUnless(self.drbd.get_replication_port(ip) <> port)
    def testMultiple(self):
        """Check the DRBD simulator allows multiple configurations"""
        for i in range(0, 10):
            self.drbd.start(make_simple_config(i, 8080 + i))
            self.failUnless(len(self.drbd.configs) - 1 == i)
    def testStartStop(self):
        """Check the DRBD simulator allows multiple configurations to be manipulated separately"""
        for j in range(0, 10):
            for i in range(0, 10):
                self.drbd.start(make_simple_config(i, 8080 + i))
                self.failUnless(len(self.drbd.configs) - 1 == i)
            for i in range(0, 10):
                self.drbd.stop(make_simple_config(i, 8080 + i))
                self.failUnless(len(self.drbd.configs) + i + 1 == 10)

import util, losetup, os
from util import run, CommandError, log
class Localdevice:
    """Wrapper around local resource allocation/deallocation"""
    def __init__(self, drbd, disk):
        self.disk = disk
        self.hostname = os.uname()[1]
        self.minor = drbd.get_free_minor_number()
        bytes_per_sector = util.block_device_sector_size(disk)
        sectors = util.block_device_sectors(disk)
        mdsize = size_needed_for_md(bytes_per_sector, sectors)
        self.md_file = util.make_sparse_file(mdsize)
        l = losetup.Loop()
        self.loop = l.add(self.md_file)
        self.address = drbd.get_replication_ip()
        self.port = drbd.get_replication_port(self.address)
    def get_config(self):
        return {
            "name": self.hostname,
            "device": "/dev/drbd%d" % self.minor,
            "disk": self.disk,
            "address": "%s:%d" % (self.address, self.port),
            "md": self.loop
            }
    def __del__(self):
        # Remove loop device
        l = losetup.Loop()
        l.remove(self.loop)
        # Remove the temporary file
        os.unlink(self.md_file)

class Localdevice_test(unittest.TestCase):
    def setUp(self):
        self.size = 16L * 1024L * 1024L * 1024L
        self.file = util.make_sparse_file(self.size)
        self.losetup = losetup.Loop()
        self.disk = self.losetup.add(self.file)
        
        self.nloops = len(self.losetup.list())
    def testCleanup(self):
        """Verify the wrapper will correctly deallocate loop devices"""
        l = Localdevice(Drbd_simulator(), self.disk)
        l.get_config()
        del l
        nloops = len(self.losetup.list())
        self.failUnless(self.nloops == nloops)
    def tearDown(self):
        self.losetup.remove(self.disk)
        os.unlink(self.file)


class VersionMismatchError(Exception):
    def __init__(self, my_version, their_version):
        self.my_version = my_version
        self.their_version = their_version

class Peer:
    """Two Peers negotiate a DRBD connection"""
    def __init__(self, drbd, disk, uuid):
        self.drbd = drbd
        self.disk = disk
        self.uuid = uuid
        self.localdevice = None
    def versionExchange(self, other_version):
        return self.drbd.version()
    def softAllocateResources(self):
        if self.localdevice:
            del self.localdevice
        self.localdevice = Localdevice(self.drbd, self.disk)
        return self.localdevice.get_config()
    def start(self, my_config, other_config):
        drbd_conf = {
            "uuid": self.uuid,
            "hosts": [ my_config, other_config ]
            }
        self.drbd.start(drbd_conf)
        return "OK"
    def stop(self, my_config, other_config):
        drbd_conf = {
            "uuid": self.uuid,
            "hosts": [ my_config, other_config ]
            }
        n = len(self.drbd.configs)
        self.drbd.stop(drbd_conf)
        nn = len(self.drbd.configs)
        assert(n - 1 == nn)
        return "OK"
    def negotiate(self, receiver):
        my_version = self.drbd.version()
        their_version = receiver.versionExchange(my_version)
        if my_version <> their_version:
            log("Versions must match exactly. My version = %s; Their version = %s" % (my_version, their_version))
            raise VersionMismatchError(my_version, their_version)

        other_config = None # must be regenerated if localdevice changes
        local_service_started = False
        while not local_service_started:
            while not local_service_started:
                my_config = self.softAllocateResources()
                if not other_config:
                    other_config = receiver.softAllocateResources()
                # NB my_config and other_config might conflict with other 3rd party
                # configurations, or with each other in the localhost case.
                try:
                    self.start(my_config, other_config)
                    local_service_started = True
                except TransientException, e:
                    # transient failure, retry
                    log("local: %s: retrying" % str(e))
                    raise
            log("Local service started; signalling remote")
            try:
                receiver.start(other_config, my_config)
            except TransientException, e:
                log("remote: %s: reallocating" % str(e))
                # this is either bad luck *or* the receiver just clashed with
                # the transmitter (expected in the localhost case)
                other_config = receiver.softAllocateResources()
                
                # if we just clashed on localhost, then other_config will now
                # be disjoint from my_config
                self.stop(my_config, other_config)
                local_service_started = False
        return "OK"

class Negotiate_test(unittest.TestCase):
    def setUp(self):
        self.size = 16L * 1024L * 1024L * 1024L
        self.file = util.make_sparse_file(self.size)
        self.losetup = losetup.Loop()
        self.disk = self.losetup.add(self.file)
        self.remote = Peer(Drbd_simulator(), self.disk, "uuid")
        self.local = Peer(Drbd_simulator(), self.disk, "uuid")

    def mismatch(self):
        self.remote.drbd.version_number = "a"
        self.local.drbd.version_number = "b"
        self.local.negotiate(self.remote)
    def testVersionMismatch(self):
        """Check VersionMismatch is thrown when expected"""
        self.assertRaises(VersionMismatchError, self.mismatch)
    def testSuccess(self):
        """The negotiation should always succeed eventually"""
        self.local.negotiate(self.remote)
    def testLocalhost(self):
        """The negotiation should always succeed even on localhost"""
        self.local.negotiate(self.local)
    def testRemote(self):
        import drbd, xmlrpclib
        localhost = "127.0.0.1"
        port = util.replication_port(localhost)
        s = drbd.Server(localhost, port)
        s.start()
        prefix = "http://%s:%d" % (localhost, port)
        suffix = xmlrpclib.Server(prefix + "/", allow_none=True).make(self.disk, "uuid")
        remote = xmlrpclib.Server(prefix + suffix, allow_none=True)
        self.local.negotiate(remote)
        s.stop()
        s.join()

    def tearDown(self):
        self.losetup.remove(self.disk)
        os.unlink(self.file)

if __name__ == "__main__":
    unittest.main ()

