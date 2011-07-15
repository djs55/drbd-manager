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
    fd, filename = tempfile.mkstemp()
    os.fdopen(fd).close()
    run(["dd", "if=/dev/zero", "of=%s" % filename, "bs=1", "count=0", "seek=%Ld" % size])
    return filename
