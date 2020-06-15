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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from argparse import ArgumentParser
from json import load
from utils.prompt import Prompt
from cgi import FieldStorage


def getInstance(id, args, logger):
    return httpserver(id, args, logger)


class WrapHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address, RequestHandlerClass, wrappers, sname, sid, timeout, error_file, error_code, logger):
        ThreadingHTTPServer.__init__(self, server_address, RequestHandlerClass)
        self.wrappers = wrappers
        self.sname = sname
        self.sid = sid
        self.timeout = timeout
        self.error_file = error_file
        self.error_code = error_code
        # Logger parameters
        self.logger = logger
        self._LOGGING_ = False if logger is None else True


class httpserverHandler(BaseHTTPRequestHandler):

    # Overide log function to disable verbose outputs.
    def log_message(self, format, *args):
        return

    def getDefaultErrorView(self):
        content = '<html><head><title>408 Request Timeout</title></head><body bgcolor="white"><center><h1>408 Request Timeout</h1></center><hr><center>nginx/1.5.10</center></body></html>'
        return self.packRequest("",{"Server":"nginx 1.5.10"},content,408)

    def readErrorFile(self):
        try:
            with open(self.server.error_file, "r") as errfile:
                content = errfile.read()
            return self.packRequest("",{"Server":"nginx 1.13.1"},content,self.server.error_code)
        except Exception:
            return self.getDefaultErrorView()

    def generateErrorView(self):
        if self.server.error_file and self.server.error_code:
            return self.readErrorFile()
        else:
            return self.getDefaultErrorView()

    # Send the request message to all wrappers (just the right wrapper will process and make an answer).
    def doMulticast(self,q,data):
        for wrap in self.server.wrappers:
            msg = Message(self.server.sname, self.server.sid, wrap.name, wrap.id,
                MessageType.STREAM, data, q)
            wrap.inbox.put(msg)

    def waitForResponse(self,q):
        response = None
        try:
            r = q.get(True,self.server.timeout)
            response = r.content
        except (Empty,Exception):
            response = self.generateErrorView()
        finally:
            return response

    def packRequest(self, requestline, headers, content=None, httpcode=200):
        return {
            "requestline" : requestline,
            "headers" : headers,
            "content" : content,
            "httpcode" : httpcode
        }

    def returnResponse(self,res):
        self.protocol_version = "HTTP/1.1"

        if 'Server' in res['headers']:
            # Server header must be 'werbserver+space+version'
            versions = res['headers']['Server'].split(' ')
            self.server_version = versions[0]
            self.sys_version = versions[1]
            del res['headers']['Server']
        else:
            self.server_version = "nginx"
            self.sys_version = "1.5.10"

        self.send_response(res['httpcode'])

        for key,value in res['headers'].items():
            self.send_header(key,value)

        if res['content'] == "":
            self.end_headers()
        elif 'Content-Length' not in res['headers']:
            self.send_header("Content-Length", len(res['content']))
            self.end_headers()
            self.wfile.write(bytes(res['content'], "utf8"))
        else:
            self.end_headers()
            self.wfile.write(bytes(res['content'], "utf8"))

    # Generate a Queue (for recieve responses *thread), send request to wrappers,
    # and wait for response from only one and return to HTTP Client.
    def processRequest(self,request):
        try:
            q = Queue()
            self.doMulticast(q,request)
            response = self.waitForResponse(q)
            self.returnResponse(response)
        except Exception as e:
            self.server.logger.exception(f"[{self.server.sname}] Exception in handle: {e}")

    def do_GET(self):
        req = self.packRequest(self.requestline,self.headers)
        self.processRequest(req)

    def do_POST(self):
        form = FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={'REQUEST_METHOD':'POST',
                     'CONTENT_TYPE':self.headers['Content-Type'],
                     })
        req = self.packRequest(self.requestline,self.headers, form)
        self.processRequest(req)


class httpserver(Thread,BaseHTTPRequestHandler):
    
    NAME = "httpserver"
    
    def __init__(self, id, args, logger):
        Thread.__init__(self)
        self.wrappers = []
        self.id = id
        self.server = None
        self.name = type(self).__name__
        self.inbox = Queue()
        # Argparsing
        self.argparser = self.generateArgParse(self.name)
        self.parseArguments(args)
        # Logger parameters
        self.logger = logger
        self._LOGGING_ = False if logger is None else True

    def parseArguments(self, args):
        parsed = self.argparser.parse_args(args.split())
        self.hostname = parsed.hostname[0]
        self.port = parsed.port[0]
        self.timeout = parsed.timeout[0]
        self.error_file = parsed.error_file[0] if parsed.error_file else None
        self.error_code = parsed.error_code[0] if parsed.error_code else None

    def generateArgParse(self, name):
        filepath = f"./wrapper/server/wrap_server/{name}/config.json"
        config = ""
        with open(filepath, 'r') as f:
            config = load(f)
        parser = ArgumentParser(prog=config["prog"],description=config["description"])
        for arg in config["args"]:
            for name,field in arg.items():
                opts = {}
                for key,value in field.items():
                    if key == "type":
                        value = Prompt.getType(value)
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
        self.server = WrapHTTPServer((self.hostname, self.port),
                httpserverHandler,self.wrappers,self.name,
                self.id, self.timeout, self.error_file, 
                self.error_code, self.logger)
        st = Thread(target=self.SignalThread)
        st.start()
        self.server.serve_forever()
        self.server.server_close()
