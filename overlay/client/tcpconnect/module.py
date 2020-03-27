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
from sotp.misticathread import ClientOverlay
from sys import stdout
import socket
from threading import Thread
from utils.messaging import Message, MessageType, SignalType
import select


def getInstance(qsotp, mode, args, logger):
    return tcpconnect(qsotp, mode, args, logger)


class tcpconnect(ClientOverlay):

    def __init__(self, qsotp, mode, args, logger):
        ClientOverlay.__init__(self, type(self).__name__, qsotp, mode, args, logger)
        self.name = type(self).__name__
        self.buffer = []
        # Setting input capture
        self.hasInput = False
        self.id = 0
        self.timeout = 1
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
    	# Create socket and connect
        while not self.exit:
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.connect((self.address, self.port))
            except Exception as e:
                print(e)
                self.inbox.put(Message('input',
                                          0,
                                          self.name,
                                          self.id,
                                          MessageType.SIGNAL,
                                          SignalType.TERMINATE))
                return
            while not self.exit:
                try:
                    # Block on socket until Timeout
                    result = select.select([self.socket], [], [], self.timeout)
                    if result[0]:
                        rawdata = self.socket.recv(4096)
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
                            self.socket.close()
                            break
                except:
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
        self.socket.send(content)
