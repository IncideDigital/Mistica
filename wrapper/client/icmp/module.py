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
from sotp.misticathread import ClientWrapper
from base64 import urlsafe_b64encode,urlsafe_b64decode
from sotp.core import BYTE,Header,OptionalHeader,Sizes

import socket, select
from utils.icmp import Packet


def getInstance(qsotp, args, logger):
    return icmp(qsotp, args, logger)


class ICMPClient(object):

    def __init__(self, hostname, request_timeout, name, logger):
        self.name = name
        self.hostname = hostname
        self.request_timeout = request_timeout
        # Logger parameters
        self.logger = logger
        self._LOGGING_ = False if logger is None else True
        # Opening Raw Socket and resolve the hostname
        self.mysocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        self.mysocket.setblocking(0)
        socket.gethostbyname(self.hostname)

    def send_data(self, data):
        request = Packet()
        request.pack_request(data)
        raw_request = request.toBytes()
        self._LOGGING_ and self.logger.debug_all(f"[{self.name}] send_data() will send: {raw_request}")
        self.mysocket.sendto(raw_request, (self.hostname, 1))

    def get_data(self):
        ready = select.select([self.mysocket], [], [], self.request_timeout)
        if ready[0]:
            raw_response = self.mysocket.recv(65535)
            self._LOGGING_ and self.logger.debug_all(f"[{self.name}] get_data() recv: {raw_response}")
            response = Packet()
            response.unpack(raw_response)
            return response.data


class icmp(ClientWrapper):
    
    # 65535 bytes (Max IP Packet) - 20 bytes (IP Header) - 8 bytes (ICMP Header) 
    # = 65507 bytes; see rfc 792 for more info
    MAX_ICMP_DATA_LEN = 65507

    def __init__(self, qsotp, args, logger):
        ClientWrapper.__init__(self,type(self).__name__,qsotp,logger)
        self.name = type(self).__name__
        self.exit = False
        # Generate argparse
        self.argparser = self.generateArgParse(self.name)
        # Parse arguments
        self.hostname = None
        self.request_timeout = None
        # Base arguments
        self.max_size = None
        self.poll_delay = None
        self.response_timeout = None
        self.max_retries = None
        self.parseArguments(args)
        # Logger parameters
        self.logger = logger
        self._LOGGING_ = False if logger is None else True
        # ICMPclient parameters
        self.icmpclient = ICMPClient(self.hostname,
                                     self.request_timeout, 
                                     self.name, 
                                     self.logger)

    def checkMaxProtoSize(self,max_size):
            headerlen = int(Sizes.HEADER/BYTE)
            totalen = len(urlsafe_b64encode(b'A' * (headerlen + max_size)))
            self._LOGGING_ and self.logger.debug_all(f"[{self.name}] checkMaxProtoSize() headerlen:{headerlen},max_size:{max_size},totalen:{totalen}")

            if totalen > self.MAX_ICMP_DATA_LEN:
                raise BaseException(f"Total Length is {totalen} and max available for this module is {self.MAX_ICMP_DATA_LEN}. Please, reduce max_size value")

    def parseArguments(self, args):
        args = self.argparser.parse_args(args.split())
        self.hostname = args.hostname[0]
        self.request_timeout = args.request_timeout[0]
        self.max_size = args.max_size[0]
        self.poll_delay = args.poll_delay[0]
        self.response_timeout = args.response_timeout[0]
        self.max_retries = args.max_retries[0]
        self.checkMaxProtoSize(self.max_size)

    def wrap(self,content):
        # make your own routine to encapsulate sotp content in dns packet (i use b64 in subdomain space)
        sotpDataBytes = urlsafe_b64encode(content)
        self._LOGGING_ and self.logger.debug_all(f"[{self.name}] wrap() data to icmp request: {str(sotpDataBytes,'utf-8')}")
        
        self.icmpclient.send_data(sotpDataBytes)
        raw_reply = self.icmpclient.get_data()
        if not raw_reply:
            self._LOGGING_ and self.logger.error(f"[{self.name}] wrap() get_data return None")
            return
        self._LOGGING_ and self.logger.debug_all(f"[{self.name}] wrap() recv icmp raw response: {raw_reply}")
        self.inbox.put(self.messageToWrapper(raw_reply))

    def unwrap(self,content):
        data = urlsafe_b64decode(content)
        self._LOGGING_ and self.logger.debug_all(f"[{self.name}] unwrap() data icmp response: {data}")
        return data