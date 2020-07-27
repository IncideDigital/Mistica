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
from argparse import ArgumentParser
from json import load
from utils.prompt import Prompt

import socket, select
from utils.icmp import Packet

class icmpserver(Thread):
    
    NAME = "icmpserver"
    CONFIG = {
                "prog": "icmpserver",
                "description": "Simple ICMP Server",
                "args": [
                    {
                        "--iface": {
                            "help": "Network interface to bind (Ex: eth0, wlp2s0, etc)",
                            "nargs": 1,
                            "type": str,
                            "required": 1
                        },
                        "--timeout": {
                            "help": "Max time, in seconds, that the server will wait for the SOTP layer to reply, before returning an error. Default is 5",
                            "nargs": 1,
                            "default": [5],
                            "type" :  int
                        },
                        "--request-timeout": {
                            "help": "Max time, in seconds, that the server will wait blocked on raw socket",
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
        self.shutdown = False
        # Server parameters
        self.iface = None
        self.timeout = None
        self.request_timeout = None
        # Argparsing
        self.argparser = self.generateArgParser()
        self.parseArguments(args)
        # Logger parameters
        self.logger = logger
        self._LOGGING_ = False if logger is None else True
        # Open Raw Socket and binding to a Network Interface
        self.mysocket = socket.socket(socket.AF_INET,socket.SOCK_RAW,socket.IPPROTO_ICMP)
        self.mysocket.setsockopt(socket.SOL_SOCKET,25,str(self.iface+'\0').encode('utf-8'))

    def parseArguments(self, args):
        parsed = self.argparser.parse_args(args.split())
        self.iface = parsed.iface[0]
        self.timeout = parsed.timeout[0]
        self.request_timeout = parsed.request_timeout[0]

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
                self.shutdown = True
                break

    def addWrapModule(self, encWrapper):
        self.wrappers.append(encWrapper)

    def removeWrapModule(self, encWrapper):
        self.wrappers.remove(encWrapper)

    def doMulticast(self,q,data):
        for wrap in self.wrappers:
            msg = Message(self.name, self.id, wrap.name, wrap.id,
                MessageType.STREAM, data, q)
            wrap.inbox.put(msg)

    def waitForResponse(self, q, request):
        response = None
        try:
            r = q.get(True,self.timeout)
            response = r.content
        except (Empty,Exception):
            response = request.data
            self._LOGGING_ and self.logger.error(f"[{self.name}] queue timeout expired answering: {response}")
        finally:
            return response

    def returnResponse(self, request, data, addr):
        response = Packet()
        response.pack_response(request, data)
        raw_response = response.toBytes()
        self.mysocket.sendto(raw_response, (addr[0], 1))
        self.mysocket.setblocking(0)

    def processRequest(self, raw_data, addr):
        try:
            request = Packet()
            request.unpack(raw_data)
            q = Queue()
            self._LOGGING_ and self.logger.debug_all(f"[{self.name}] icmp request data: {request.data}")

            self.doMulticast(q,request.data)
            response = self.waitForResponse(q, request)
            self._LOGGING_ and self.logger.debug_all(f"[{self.name}] icmp response data: {response}")

            if not response:
                return
            
            self.returnResponse(request,response,addr)
        except Exception as e:
            self._LOGGING_ and self.logger.exception(f"[{self.name}] exception in processRequest: {e}")
            return

    def run(self):
        self._LOGGING_ and self.logger.info(f"[{self.name}] Server started. Passing messages...")
        st = Thread(target=self.SignalThread)
        st.start()

        while not self.shutdown:
            ready = select.select([self.mysocket], [], [], self.request_timeout)
            if ready[0]:
                rec_packet, addr = self.mysocket.recvfrom(65535)
                self._LOGGING_ and self.logger.debug_all(f"[{self.name}] recv raw data: {rec_packet}")
            
                # Handle every request in separate thread
                it = Thread(target=self.processRequest, args=(rec_packet,addr,))
                it.start()
        
        self._LOGGING_ and self.logger.debug_all(f"[{self.name}] Terminated")

