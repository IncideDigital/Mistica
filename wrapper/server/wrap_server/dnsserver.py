#
# Copyright (c) 2020 Carlos Fernández Sánchez and Raúl Caro Teixidó.
#
# This file is part of Mística 
# (see https://github.com/IncideDigital/Mistica).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
from threading import Thread
from queue import Queue,Empty
from utils.messaging import Message, MessageType, SignalType
from dnslib import DNSRecord, DNSHeader, QTYPE, CLASS, RR, TXT
from argparse import ArgumentParser
from utils.prompt import Prompt
from socketserver import ThreadingUDPServer
from socketserver import BaseRequestHandler


class CustomBaseRequestHandler(BaseRequestHandler):
     
    def genDefaultError(self, request):
        reply = DNSRecord(DNSHeader(id=request.header.id, qr=1, aa=1, ra=1), q=request.q)
        reply.add_answer(RR(rname=request.q.qname, 
                rtype=QTYPE.TXT, 
                rclass=CLASS.IN, 
                ttl=self.server.ttl, 
                rdata=TXT("google-site-verification=qt5d8b2252742f0bcab14623d9714bee9ba7e82da3")))
        return reply

    def waitForResponse(self,q, request):
        response = None
        try:
            r = q.get(True,self.server.timeout)
            response = r.content
        except (Empty,Exception):
            response = self.genDefaultError(request)
            self.server._LOGGING_ and self.server.logger.error(f"[{self.server.sname}] expired timeout in waitForResponse()")
        finally:
            return response

    def doMulticast(self,q,data):
        for wrap in self.server.wrappers:
            msg = Message(self.server.sname, self.server.sid, wrap.name, wrap.id,
                MessageType.STREAM, data, q)
            wrap.inbox.put(msg)

    def returnResponse(self,reply):
        self.send_data(reply.pack())

    def processRequest(self,request):
        q = Queue()
        self.doMulticast(q,request)
        response = self.waitForResponse(q,request)
        self.returnResponse(response)

    def get_data(self):
        raise NotImplementedError

    def send_data(self, data):
        raise NotImplementedError

    def handle(self):
        try:
            data = self.get_data()
            request = DNSRecord.parse(data)
            self.processRequest(request)
        except Exception as e:
            self.server._LOGGING_ and self.server.logger.exception(f"[{self.server.sname}] Exception on handle: {e}")


class UDPRequestHandler(CustomBaseRequestHandler):
    
    def get_data(self):
        return self.request[0]

    def send_data(self, data):
        return self.request[1].sendto(data, self.client_address)


class WrapDNSServer(ThreadingUDPServer):
    def __init__(self, server_address, RequestHandlerClass, wrappers, sname, sid, ttl, timeout, logger):
        ThreadingUDPServer.__init__(self, server_address, RequestHandlerClass)
        self.wrappers = wrappers
        self.sname = sname
        self.sid = sid
        self.ttl = ttl
        self.timeout = timeout
        # Logger parameters
        self.logger = logger
        self._LOGGING_ = False if logger is None else True


class dnsserver(Thread):

    NAME = "dnsserver"
    CONFIG = {
        "prog": NAME,
        "description": "Simple DNS server",
        "args": [
            {
                "--hostname": {
                    "help": "Hostname or IP address. Default is localhost",
                    "nargs": 1,
                    "default": ["localhost"],
                    "type": str
                },
                "--port": {
                    "help": "Port where the server will listen. Default is 5355",
                    "nargs": 1,
                    "default": [5355],
                    "type" :  int
                },
                "--ttl": {
                    "help": "TTL of DNS Responses",
                    "nargs": 1,
                    "default": [300],
                    "type" :  int
                },
                "--timeout": {
                    "help": "Max time in seconds that the server will wait for the SOTP layer to reply, before returning an error. Default is 3",
                    "nargs": 1,
                    "default": [3],
                    "type" :  int
                }
            }
        ]
    }

    def __init__(self, id, args, logger):
        Thread.__init__(self)
        self.wrappers = []
        self.id = id
        self.server = None
        self.name = type(self).__name__
        self.inbox = Queue()
        # Argparsing
        self.argparser = self.generateArgParser()
        self.parseArguments(args)
        # Logger parameters
        self.logger = logger
        self._LOGGING_ = False if logger is None else True

    def parseArguments(self, args):
        parsed = self.argparser.parse_args(args.split())
        self.hostname = parsed.hostname[0]
        self.port = parsed.port[0]
        self.ttl = parsed.ttl[0]
        self.timeout = parsed.timeout[0]
    
    def generateArgParser(self):
        config = self.CONFIG

        parser = ArgumentParser(prog=config["prog"],description=config["description"])
        for arg in config["args"]:
            for name,field in arg.items():
                opts = {}
                for key,value in field.items():
                    opts[key] = value
                parser.add_argument(name, **opts)
        return parser

    def SignalThread(self):
        while True:
            msg = self.inbox.get()
            if msg.isTerminateMessage():
                self.server.shutdown()
                break

    def addWrapModule(self, encWrapper):
        self.wrappers.append(encWrapper)

    def removeWrapModule(self, encWrapper):
        self.wrappers.remove(encWrapper)

    def run(self):
        self._LOGGING_ and self.logger.info(f"[{self.name}] Server started. Passing messages...")
        self.server = WrapDNSServer(
            (self.hostname, self.port), 
            UDPRequestHandler,
            self.wrappers,
            self.name,
            self.id, 
            self.ttl,
            self.timeout, 
            self.logger)
        st = Thread(target=self.SignalThread)
        st.start()
        self.server.serve_forever()
        self.server.server_close()
