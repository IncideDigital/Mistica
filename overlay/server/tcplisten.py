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
from sotp.misticathread import ServerOverlay
from sys import stdout
import socket
from threading import Thread
from utils.messaging import Message, MessageType, SignalType
import select


class tcplisten(ServerOverlay):
    
    NAME = "tcplisten"
    
    def __init__(self, id, qsotp, mode, args, logger):
        ServerOverlay.__init__(self, type(self).__name__, id, qsotp, mode, args, logger)
        self.name = type(self).__name__
        self.buffer = []
        self.buffer2 = []
        self.conn = None
        self.timeout = 1
        # Setting input capture
        self.hasInput = False
        # Logger parameters
        self.logger = logger
        self._LOGGING_ = False if logger is None else True
        self.tcpthread = Thread(target=self.captureTcpStream)
        self.tcpthread.start()

    # Overriden
    def parseArguments(self, args):
        self.port = int(args.port[0])
        self.address = args.address[0]
        self.persist = args.persist

    def captureTcpStream(self):
    	# Create socket and listen
        while self.conn is None and not self.exit:

            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            try:
                self.socket.bind((self.address, self.port))
                self.socket.listen(0)
                self.conn, self.remoteaddr = self.socket.accept()

            except socket.timeout as te:
                continue  # Allows to check if the application has exited to finish the thread
            except Exception as e:
                print(e)
                self.inbox.put(Message('input',
                                          0,
                                          self.name,
                                          self.id,
                                          MessageType.SIGNAL,
                                          SignalType.TERMINATE))
                return
            # Empty buffered data, if any
            while self.buffer2 and not self.exit:
                self.conn.send(self.buffer2.pop(0))
            # socket loop
            while not self.exit:
                try:
                    # Block on socket
                    result = select.select([self.conn], [], [], self.timeout)
                    if result[0]:
                        rawdata = self.conn.recv(4096)
                        if rawdata and len(rawdata) > 0:
                            self.inbox.put(Message('input',
                                                      0,
                                                      'overlay',
                                                      self.id,
                                                      MessageType.STREAM,
                                                      rawdata))
                        elif not self.persist:
                            self._LOGGING_ and self.logger.debug(f"[{self.name}] TCP communication broken. Sending Terminate signal to overlay")
                            self.inbox.put(Message('input',
                                                      0,
                                                      self.name,
                                                      self.id,
                                                      MessageType.SIGNAL,
                                                      SignalType.TERMINATE))
                            return
                        else:
                            self.conn.close()
                            self.conn = None
                            break
                except Exception as e:
                    self._LOGGING_ and self.logger.debug(f"[{self.name}] Exception: {e}. Sending Terminate signal to overlay")
                    self.inbox.put(Message('input',
                                              0,
                                              self.name,
                                              self.id,
                                              MessageType.SIGNAL,
                                              SignalType.TERMINATE))
                    return
        return

    def processInputStream(self, content):
        self._LOGGING_ and self.logger.debug(f"[{self.name}] Read from socket: {len(content)}")
        return content

    def processSOTPStream(self, content):
        self._LOGGING_ and self.logger.debug(f"[{self.name}] Write to socket: {len(content)}")
        if self.conn is None:
            self.buffer2.append(content) # wait until a connection happens
        else:
            self.conn.send(content)

    # overriden for pipe scenarios
    def handleInputStream(self, msg):
        content = self.processInputStream(msg.content)
        # By default, only one worker. Must be overriden for more
        # In a multi-worker scenario inputs must be mapped to workers
        if self.workers:
            return self.streamToSOTPWorker(content, self.workers[0].id)

        self.buffer.append(content)

    # overriden for pipe scenarios
    def addWorker(self, worker):
        if not self.workers:  # empty
            self.workers.append(worker)
            # check if there's some buffered data and pass it
            while self.buffer:
                self.workers[0].datainbox.put(self.streamToSOTPWorker(self.buffer.pop(0),
                                                                      self.workers[0].id))
        else:
            raise(f"Cannot Register worker on overlay module. Module {self.name} only accepts one worker")
