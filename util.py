#!/usr/bin/env python

import os, sys, time, socket, traceback, subprocess

log_f = os.fdopen(os.dup(sys.stdout.fileno()), "aw")
pid = None

def reopenlog(log_file):
    global log_f
    if log_f:
        log_f.close()
    if log_file:
        log_f = open(log_file, "aw")
    else:
        log_f = os.fdopen(os.dup(sys.stdout.fileno()), "aw")

def log(txt):
    global log_f, pid
    if not pid:
        pid = os.getpid()
    t = time.strftime("%Y%m%dT%H:%M:%SZ", time.gmtime())
    print >>log_f, "%s [%d] %s" % (t, pid, txt)
    log_f.flush()

class CommandError(Exception):
    def __init__(self, code, output):
        self.code = code
        self.output = output
    def __str__(self):
        return "CommandError(%s, %s)" % (self.code, self.output)

# [run task cmd] executes [cmd], throwing a CommandError if exits with
# a non-zero exit code.
def run(cmd, task='unknown'):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    result = p.stdout.readlines()
    retval = p.wait ()
    if retval <> 0:
        log("%s: %s exitted with code %d: %s" % (task, repr(cmd), retval, repr(result)))
        raise(CommandError(retval, result))
    log("%s: %s" % (task, " ".join(cmd)))
    return result

import tempfile
def make_sparse_file(size):
    fd, filename = tempfile.mkstemp(suffix='.md')
    os.fdopen(fd).close()
    run(["dd", "if=/dev/zero", "of=%s" % filename, "bs=1", "count=0", "seek=%Ld" % size])
    return filename

def block_device_sector_size(disk):
    return int(run(["blockdev", "--getss", disk])[0].strip())

def block_device_sectors(disk):
    return long(run(["blockdev", "--getsize", disk])[0].strip())

import re
def list_all_ipv4_addresses():
    results = []
    for line in run(["/sbin/ifconfig"]):
        m = re.match('^\s*inet addr:(\S+) ', line)
        if m:
            results.append(m.group(1))
    return results

def replication_ip():
    # XXX we need to define storage, replication IPs officially somehow
    return filter(lambda x:x <> "127.0.0.1", list_all_ipv4_addresses())[0]

def used_ports(ip):
    """Return a list of port numbers currently in-use."""
    used = []
    for line in run(["/bin/netstat", "-an"]):
        m = re.match('^tcp\s+\S+\s+\S+\s+(\S+)\s+', line)
        if m:
            endpoint = m.group(1)
            bits = endpoint.split(':')
            if bits[0] == ip:
                used.append(bits[1])
    return used

def replication_port(ip):
    """Returns a port number which is currently free. Note someone else
    may come along and allocate this one for us, so we have to be prepared
    to retry."""
    free_port = 7789
    used = used_ports(ip)
    while True:
        if free_port not in used:
            return free_port
        free_port = free_port + 1

