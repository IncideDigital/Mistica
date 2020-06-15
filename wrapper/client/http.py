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
from utils.messaging import Message, MessageType, SignalType
from sotp.misticathread import ClientWrapper
from http.client import HTTPConnection
from base64 import urlsafe_b64encode,urlsafe_b64decode

def getInstance(qsotp, args, logger):
    return http(qsotp, args, logger)

class http(ClientWrapper):

    NAME = "http"

    def __init__(self, qsotp, args, logger):
        ClientWrapper.__init__(self,type(self).__name__,qsotp,logger)
        self.name = type(self).__name__
        self.exit = False
        # Generate argparse
        self.argparser = self.generateArgParse(type(self).__name__)
        # Parse arguments
        self.hostname = None
        self.port = None
        self.uri = None
        self.method = None
        self.header = None
        self.post_field = None
        self.success_code = None
        # Base arguments
        self.max_size = None
        self.poll_delay = None
        self.response_timeout = None
        self.max_retries = None
        self.parseArguments(args)
        # Logger parameters
        self.logger = logger
        self._LOGGING_ = False if logger is None else True

    def parseArguments(self, args):
        args = self.argparser.parse_args(args.split())
        self.hostname = args.hostname[0]
        self.port = args.port[0]
        self.timeout = args.timeout[0]
        self.uri = args.uri[0]
        self.method = args.method[0]
        self.header = args.header[0] if args.header is not None else None
        self.post_field = args.post_field[0] if args.post_field is not None else None
        self.success_code = args.success_code[0]
        self.max_size = args.max_size[0]
        self.poll_delay = args.poll_delay[0]
        self.response_timeout = args.response_timeout[0]
        self.max_retries = args.max_retries[0]

    def doReqInURI(self, conn, content, method):
        data_headers = {"Content-type": "application/x-www-form-urlencoded","Accept": "text/plain"}
        conn.request(method, f"{self.uri}{content}", headers=data_headers)
        r = conn.getresponse()
        return (r.read(),r.status)

    def doReqInHeaders(self, conn, content, method):
        data_headers = {
            "Content-type": "application/x-www-form-urlencoded",
            "Accept": "text/plain",
            f"{self.header}": f"{content}"
        }
        conn.request(method, f"{self.uri}", headers=data_headers)
        r = conn.getresponse()
        return (r.read(),r.status)

    def doGet(self, conn, content):
        if self.header:
            return self.doReqInHeaders(conn, content, "GET")
        else:
            return self.doReqInURI(conn, content, "GET")

    def doPostField(self, conn, content):
        post_data = f"{self.post_field}={content}"
        data_headers = {
            "Content-type": "application/x-www-form-urlencoded",
            "Accept": "text/plain"
        }
        conn.request("POST", f"{self.uri}", post_data, data_headers)
        r = conn.getresponse()
        return (r.read(),r.status)

    def doPost(self, conn, content):
        if self.post_field:
            return self.doPostField(conn, content)
        elif self.header:
            return self.doReqInHeaders(conn, content, "POST")
        else:
            return self.doReqInURI(conn, content, "POST")

    def dispatchByMethod(self, conn, content):
        if self.method == "GET":
            return self.doGet(conn, content)
        elif self.method == "POST":
            return self.doPost(conn, content)
        else:
            raise Exception("None HTTP Method Available")

    def packSotp(self, content):
        # we encode sotp data with urlsafe_b64encode but change 
        # here (and in wrap_server) if you use other encoding.
        urlSafeEncodedBytes = urlsafe_b64encode(content)
        urlSafeEncodedStr = str(urlSafeEncodedBytes, "utf-8")
        return urlSafeEncodedStr

    def wrap(self,content):
        self._LOGGING_ and self.logger.debug(f"[{self.name}] wrap: {len(content)} bytes")
        packedSotp = self.packSotp(content)
        conn = HTTPConnection(self.hostname, self.port,self.timeout)
        data_response, code_response = self.dispatchByMethod(conn, packedSotp)
        conn.close()
        self.inbox.put(self.messageToWrapper((data_response,code_response)))

    def unpackSotp(self, data):
        # we decode sotp data with urlsafe_b64decode but change 
        # here (and in wrap_server) if you use other encoding.
        return urlsafe_b64decode(data)

    def unwrap(self,content):
        data, httpcode = content
        if httpcode != self.success_code:
            self._LOGGING_ and self.logger.error(f"[{self.name}] unwrap: Invalid HTTP Response {httpcode}")
            raise Exception(f"Invalid HTTP Response Code {httpcode} waited: {self.success_code}")
        return self.unpackSotp(data)
