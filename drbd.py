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

import SimpleXMLRPCServer, xmlrpclib, json, sys, drbdadm

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

# keep a table of URIs -> Peer instances
#  so we can use xmlrpclib.Server(URI) as a Peer proxy
# time out and delete Peers (therefore freeing loops, files)

class Drbd_factory:
    def __init__(self):
        self.x = 0
    def make(self):
        peer = drbdadm.Peer(drbdadm.Drbd_simulator(), "/dev/xvda", "uuid")
        uri = "/%d" % self.x
        self.x = self.x + 1
        peers[uri] = peer
        return uri

peers = {"/": Drbd_factory() }

class DRBD(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps(peers))

    def do_POST(self):
        # Simplified version of SimpleXMLRPCRequestHandler.do_POST
        l = int(self.headers["Content-Length"])
        request_txt = self.rfile.read(l)
        params, func = xmlrpclib.loads(request_txt)
        if self.path not in peers:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.end_headers()

        peer = peers[self.path]
        try:
            if not hasattr(peer, func):
                raise "No such method"
            result = getattr(peer, func)(*params)
            response = xmlrpclib.dumps((result,))
        except:
            exc_type, exc_value, exc_tb = sys.exc_info()
            response = xmlrpclib.dumps(
                xmlrpclib.Fault(1, "%s:%s" % (exc_type, exc_value)),
                )
        # need to call a function with (*params)
        self.wfile.write(response)

from threading import Thread
class Server(Thread):
    def __init__(self, host, port):
        Thread.__init__(self)
        self.host = host
        self.port = port
    def run(self):
        try:
            server = HTTPServer((self.host, self.port), DRBD)
            server.serve_forever()
        except KeyboardInterrupt:
            print '^C received, shutting down server'
            server.socket.close()


if __name__ == '__main__':
    s = Server('', 8081)
    s.start()
    s.join()


