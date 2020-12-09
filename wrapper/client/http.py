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
from http.client import HTTPConnection, HTTPSConnection
from base64 import urlsafe_b64encode,urlsafe_b64decode
from ssl import _create_unverified_context

class http(ClientWrapper):

    NAME = "http"
    CONFIG = {
        "prog": NAME,
        "description": "Encodes/Decodes data in HTTP requests/responses using different methods",
        "args": [
            {
                "--hostname": {
                    "help": "Hostname or IP address. Default is localhost",
                    "nargs": 1,
                    "default": ["localhost"],
                    "type": str
                },
                "--port": {
                    "help": "Server Port",
                    "nargs": 1,
                    "default": [8080],
                    "type":  int
                },
                "--timeout": {
                    "help": "HTTPConnection Timeout",
                    "nargs": 1,
                    "default": [5],
                    "type":  int
                },
                "--method": {
                    "help": "HTTP Method to use",
                    "nargs": 1,
                    "default": ["GET"],
                    "choices": ["GET","POST"],
                    "type": str
                },
                "--uri": {
                    "help": "URI Path before embedded message. Default is '/'",
                    "nargs": 1,
                    "default": ["/"],
                    "type": str
                },
                "--header": {
                    "help": "Header field to embed the packets",
                    "nargs": 1,
                    "type": str
                },
                "--post-field": {
                    "help": "Post param to embed the packet",
                    "nargs": 1,
                    "type": str
                },
                "--success-code": {
                    "help": "HTTP Code for Success Connections. Default is 200",
                    "nargs": 1,
                    "default": [200],
                    "choices": [100,101,102,200,201,202,203,204,205,206,207,
                                208,226,300,301,302,303,304,305,306,307,308,
                                400,401,402,403,404,405,406,407,408,409,410,
                                411,412,413,414,415,416,417,418,421,422,423,
                                424,426,428,429,431,500,501,502,503,504,505,
                                506,507,508,510,511],
                    "type":  int
                },
                "--proxy": {
                    "help": "Proxy Address for tunneling communication format 'ip:port'",
                    "nargs": 1,
                    "type": str
                },
                "--max-size": {
                    "help": "Maximum size in bytes of the SOTP packet. You can change it depending http method used (see rfc2616 page 69)",
                    "nargs": 1,
                    "default": [4096],
                    "type":  int
                },
                "--poll-delay": {
                    "help": "Time in seconds between pollings",
                    "nargs": 1,
                    "default": [5],
                    "type":  int
                },
                "--response-timeout": {
                    "help": "Waiting time in seconds for wrapper data.",
                    "nargs": 1,
                    "default": [3],
                    "type":  int
                },
                "--max-retries": {
                    "help": "Maximum number of re-synchronization retries.",
                    "nargs": 1,
                    "default": [20],
                    "type":  int
                },
                "--ssl": {
                    "help": "Flag to indicate that SSL will be used.",
                    "action": "store_true"
                }
            }
        ]
    }

    def __init__(self, qsotp, args, logger):
        ClientWrapper.__init__(self,type(self).__name__,qsotp,logger)
        self.args = args
        self.name = type(self).__name__
        self.exit = False
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
        self.proxy = args.proxy[0] if args.proxy is not None else None
        self.max_size = args.max_size[0]
        self.poll_delay = args.poll_delay[0]
        self.response_timeout = args.response_timeout[0]
        self.max_retries = args.max_retries[0]
        self.ssl = args.ssl

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

        if self.proxy:
            proxy_ip, proxy_port = self.proxy.split(":")

            if self.ssl:
                conn = HTTPSConnection(self.hostname, self.port, timeout=self.timeout, context=_create_unverified_context())
            else:
                conn = HTTPConnection(proxy_ip, proxy_port, self.timeout)
            
            conn.set_tunnel(self.hostname, self.port)
        else:
            if self.ssl:
                conn = HTTPSConnection(self.hostname, self.port, timeout=self.timeout, context=_create_unverified_context())
            else:
                conn = HTTPConnection(self.hostname, self.port, self.timeout)

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
