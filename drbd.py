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

import SimpleXMLRPCServer, xmlrpclib

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

# keep a table of URIs -> Peer instances
#  so we can use xmlrpclib.Server(URI) as a Peer proxy
# time out and delete Peers (therefore freeing loops, files)

class DRBD(BaseHTTPRequestHandler):

    def do_POST(self):
        print self.path
        l = int(self.headers["Content-Length"])
        request_txt = self.rfile.read(l)
        request = xmlrpclib.loads(request_txt)
        print repr(request)
        self.send_response(200)
        self.end_headers()
        response = xmlrpclib.dumps(("there",))
        self.wfile.write(response)

def main():
    try:
        server = HTTPServer(('', 8081), DRBD)
        server.serve_forever()
    except KeyboardInterrupt:
        print '^C received, shutting down server'
        server.socket.close()

if __name__ == '__main__':
    main()


