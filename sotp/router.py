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
from queue import Queue
from random import randint
from utils.messaging import Message, MessageType, SignalType
from utils.bitstring import BitArray
from sotp.packet import Packet
from sotp.serverworker import ServerWorker
from sotp.core import Header, OptionalHeader, Sizes, Offsets, Status, Flags, Sync
from sotp.core import Core
from sotp.route import Route
from sys import stderr


class Router(Thread):

    def __init__(self, key, logger):
        Thread.__init__(self)
        self.inbox = Queue()
        self.wrapModules = []
        self.wrapServers = []
        self.overlayModules = []
        self.workers = []
        self.routes = []
        self.pendingInit = []
        self.workerID = 1
        self.rc4 = key
        self.id = 0
        self.name = "router"
        self.exit = False
        # Logger parameters
        self.logger = logger
        self._LOGGING_ = False if logger is None else True

    def errorMessage(self, destination, destination_id):
        return Message(self.name, self.id, destination, destination_id,
                       MessageType.SIGNAL, SignalType.ERROR)

    def addRoute(self, session_id, worker, wrap_module, overlay):
        self.routes.append(Route(session_id, worker, wrap_module, overlay))

    def routeMessage(self, msg, sessionID):
        if (msg.sender == "serverworker"):  # Outgoing
            for route in self.routes:
                if (route.session_id == sessionID):
                    route.wrap_module.inbox.put(msg)
                    break

        else:  # incoming from wrapper
            for route in self.routes:
                if (route.session_id == sessionID):
                    route.worker.inbox.put(msg)
                    break
            else:  # worker not found
                # Place error reply to unlock the server.
                for route in self.routes:
                    if (route.wrap_module.id == msg.sender_id):
                        route.wrap_module.inbox.put(self.errorMessage(route.wrap_module.name,
                                                                  route.wrap_module.id))
                        break

    def craftTerminateMessage(self, receiver, receiver_id):
        return Message(self.name, self.id, receiver, receiver_id,
                       MessageType.SIGNAL, SignalType.TERMINATE)

    def handleSignal(self, msg):
        self._LOGGING_ and self.logger.debug("[Router] Terminating all threads")
        if msg.isTerminateMessage():
            # shutdown everything
            for wm in self.wrapModules:
                wm.inbox.put(self.craftTerminateMessage(wm.name, wm.id))
            for wm in self.wrapServers:
                wm.inbox.put(self.craftTerminateMessage(wm.name, wm.id))
            for wm in self.workers:
                wm.inbox.put(self.craftTerminateMessage(wm.name, wm.id))
            for wm in self.overlayModules:
                wm.inbox.put(self.craftTerminateMessage(wm.name, wm.id))
            self.exit = True

    def sessionAlreadyExists(self, sessionID):
        for route in self.routes:
            if (route.session_id == sessionID):
                return True
        return False

    def newSessionID(self):
        while True:
            sessionID = BitArray(uint=randint(1, ((2**Header.SESSION_ID)-1)), length=Header.SESSION_ID)
            if not self.sessionAlreadyExists(sessionID):
                break
        return sessionID

    def generateAuthResponsePacket(self, req, sessionID):
        p = Packet()
        p.session_id = sessionID
        p.seq_number = BitArray(uint=1, length=Header.SEQ_NUMBER)
        p.ack = req.seq_number
        p.data_len = BitArray(bin='0' * Header.DATA_LEN)
        p.flags = BitArray(uint=Flags.SYNC, length=Header.FLAGS)
        p.optional_headers = True
        p.sync_type = BitArray(uint=Sync.RESPONSE_AUTH, length=OptionalHeader.SYNC_TYPE)
        p.content = BitArray()
        return p

    def validOverlayTag(self, tag):
        for overlay in self.overlayModules:
            if overlay.tag == tag:
                return True
        return False

    def initializeSOTPSession(self, msg):
        # Get sender:
        sender = None
        for wrapper in self.wrapModules:
            if wrapper.id == msg.sender_id:
                sender = wrapper
                self._LOGGING_ and self.logger.debug(f"[Router] Found {msg.sender} with id {msg.sender_id} in the WrapModule list")
                break
        else:  # not a valid wrapper?
            self._LOGGING_ and self.logger.error(f"[Router] Error: Wrapper does not exist")
            return

        # Check if valid packet
        try:
            pkt = Core.transformToPacket(msg.content)
        except Exception as e:
            sender.inbox.put(self.errorMessage(sender.name, sender.id))
            self._LOGGING_ and self.logger.exception(f"[Router] Exception on transformToPacket()  {e}")
            return

        # Check if valid overlay tag
        if not self.validOverlayTag(pkt.content):
            sender.inbox.put(self.errorMessage(sender.name, sender.id))
            self._LOGGING_ and self.logger.error(f"[Router] Error: Not a valid Overlay tag")
            return

        # Generate new random ID
        try:
            sessionID = self.newSessionID()
        except Exception as e:
            self._LOGGING_ and self.logger.exception(f"[Router] Exception on newSessionID()  {e}")
            sender.inbox.put(self.errorMessage(sender.name, sender.id))
            return

        # Add Session ID and overlay tag to pending and send response to wrapper
        authpkt = self.generateAuthResponsePacket(pkt, sessionID)
        self.pendingInit.append({
            "sessionID": sessionID,
            "tag": pkt.content,
            "lastpkt": authpkt
        })

        # Avoid DoS by rejecting old pendings:
        if len(self.pendingInit) > (Header.SESSION_ID / 2):
            self.pendingInit.pop(0)
        self._LOGGING_ and self.logger.debug(f"[Router] Passing Session Response back to {msg.sender}")
        sender.inbox.put(Message(self.name, self.id,
                                 sender.name, sender.id, MessageType.STREAM,
                                 authpkt.toBytes(),msg.wrapServerQ))

    def spawnRoute(self, msg, sessionID, tag, lastpkt):
        overlay = None
        wrapper = None
        # Get overlay MisticaThread
        for available in self.overlayModules:
            if available.tag == tag:
                overlay = available
                break
        else:
            self._LOGGING_ and self.logger.error(f"[Router] Error: Overlay module no longer available")
            return

        # Get wrapper MisticaThread
        for available in self.wrapModules:
            if available.id == msg.sender_id:
                wrapper = available
                break
        else:
            self._LOGGING_ and self.logger.error(f"[Router] Error: Wrapper module no longer available")
            return

        self._LOGGING_ and self.logger.debug(f"[Router] Creating route for session 0x{sessionID.hex} from {wrapper.name} to {overlay.name}. Spawning worker...")
        worker = ServerWorker(overlay, self.workerID, self.inbox, wrapper.max_retries,
                            wrapper.max_size, self.logger, self.rc4, sessionID, lastpkt)
        self.workers.append(worker)
        self.workerID += 1
        self.routes.append(Route(sessionID, worker, wrapper, overlay))
        self.pendingInit.remove({
            "sessionID": sessionID,
            "tag": tag,
            "lastpkt": lastpkt
        })
        worker.start()

    # ONLY gets the first N bytes where N is the size of the session_id field
    def getSessionID(self, binarypacket):
        return Core.fromBytesToBitArray(binarypacket)[0:Offsets.SESSION_ID]

    def run(self):
        self._LOGGING_ and self.logger.info(f"[Router] Staring up and waiting for messages...")

        while (not self.exit):
            msg = self.inbox.get()
            # inbox contains signal?
            if msg.isSignalMessage():
                self._LOGGING_ and self.logger.debug(f"[Router] Signal received from {msg.sender} with content {msg.content}")
                self.handleSignal(msg)
                continue
            # This inbox contains a sotp packet from a worker or a wrapper
            try:
                sessionID = self.getSessionID(msg.content)
            except Exception as e:
                print(e)
                continue
            # New session? create pending init
            if (sessionID.hex == '00'):
                self._LOGGING_ and self.logger.info(f"[Router] New Session Request. Initializing...")
                self.initializeSOTPSession(msg)
                continue
            # Session init confirmed?
            for elem in self.pendingInit:
                if sessionID == elem['sessionID']:
                    self.spawnRoute(msg, sessionID, elem['tag'], elem['lastpkt'])
                    break

            # Established session! Route message
            self.routeMessage(msg, sessionID)
        self._LOGGING_ and self.logger.debug("[Router] Terminated")
