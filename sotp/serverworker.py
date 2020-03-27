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
from sotp.core import Header, OptionalHeader, Sizes, Offsets, Status, Flags, Sync
from sotp.core import Core, BYTE
from sotp.packet import Packet
from threading import Thread
from queue import Queue
from utils.messaging import Message, MessageType, SignalType
from utils.bitstring import BitArray


class ServerWorker(Core, Thread):

    def __init__(self, overlay, id, SotpServerInbox, retries, maxsize, logger, key, sid, lastpkt):
        Core.__init__(self, key, retries, maxsize)
        Thread.__init__(self)
        self.overlay = overlay
        self.st = Status.WORKING  # Server establishes session before a route is created
        self.inbox = Queue()
        self.datainbox = Queue()
        self.id = id
        self.sid = sid
        self.outbox = SotpServerInbox
        self.lastPacketSent = lastpkt
        self.lastPacketRecv = None
        self.seqnumber = lastpkt.seq_number.uint
        self.overlay.addWorker(self)
        self.exit = False
        # Logger parameters
        self.logger = logger
        self._LOGGING_ = False if logger is None else True

    # Method that checks if a packet is a Polling request
    def seemsPollingRequest(self,packet):
        if packet.isFlagActive(Flags.SYNC) == False:
            return False
        if packet.isSyncType(Sync.POLLING_REQUEST) == False:
            return False
        if any(packet.data_len) or any(packet.content):
            return False
        return True

    # Method that checks if a packet is a Data Transfer Packet
    def seemsPollingChunk(self,packet):
        if any(packet.flags):
            return False
        if any(packet.data_len) == False:
            return False
        if packet.data_len.uint != int(packet.content.length/BYTE):
            return False
        return True

    # Method that checks if a packet is a Data Transfer Packet with PUSH Flag
    def seemsPollingDataPush(self,packet):
        if packet.isFlagActive(Flags.PUSH) == False:
            return False
        if packet.optional_headers:
            return False
        if any(packet.data_len) == False:
            return False
        if packet.data_len.uint != int(packet.content.length/BYTE):
            return False
        return True

    # Method that checks if a packet is a confirmation.
    def seemsConfirmation(self,packet):
        if any(packet.flags):
            return False
        if any(packet.data_len) or any(packet.content):
            return False
        return True

    # Method that checks if a packet is a session reinitialization request.
    def seemsReinitRequest(self, packet):
        if not packet.isFlagActive(Flags.SYNC):
            return False
        if not packet.isSyncType(Sync.REINITIALIZING):
            return False
        if any(packet.data_len) or any(packet.content):
            return False
        return True

    # Method to check if the packet is a valid request from mistica client.
    # first it checks that the package has the sotp structure and then 
    # if it fits any of the expected package types
    def checkWorkRequest(self,packet):
        if self.checkMainFields(packet) == False:
            return False
        if self.seemsPollingRequest(packet):
            return True
        if self.seemsConfirmation(packet):
            return True
        if self.seemsPollingChunk(packet):
            return True
        if self.seemsPollingDataPush(packet):
            return True
        return False

    # Method to check if the packet is valid reinitialization request
    def checkReinitialization(self, packet):
        if self.seemsReinitRequest(packet):
            return True
        return False

    # Method for generating a response to a Polling request
    def generatePollResponse(self,packet):
        p = Packet()
        p.session_id = self.sid
        self.seqnumber+=1
        p.seq_number = BitArray(uint=self.seqnumber,length=Header.SEQ_NUMBER)
        p.ack = packet.seq_number
        p.data_len = BitArray(bin='0'*Header.DATA_LEN)
        p.flags = BitArray(bin='0'*Header.FLAGS)
        p.content = BitArray()
        return p

    # Method for generating a session reinitialization response
    def generateReinitResponse(self,packet):
        p = Packet()
        p.session_id = self.sid
        self.seqnumber=1
        p.seq_number = BitArray(uint=self.seqnumber,length=Header.SEQ_NUMBER)
        p.ack = packet.seq_number
        p.data_len = BitArray(bin='0'*Header.DATA_LEN)
        p.flags = BitArray(bin='0'*Header.FLAGS)
        p.content = BitArray()
        return p

    # Method to generate a transfer packet (with data from the overlay)
    def generateTransferPacket(self,packt,content,push):
        p = Packet()
        p.session_id = self.sid
        self.seqnumber+=1
        p.seq_number = BitArray(uint=self.seqnumber,length=Header.SEQ_NUMBER)
        p.ack = packt.seq_number
        p.data_len = BitArray(uint=len(content),length=Header.DATA_LEN)
        if push:
            p.flags = BitArray(uint=Flags.PUSH,length=Header.FLAGS)
        else:
            p.flags = BitArray(bin='0'*Header.FLAGS)
        p.sync_type = BitArray()
        p.content = BitArray(bytes=content)
        return p

    # Method that updates the reference to the last packet sent and/or received
    def storePackets(self,packetrecv,packetsent):
        if packetsent is not None:
            self._LOGGING_ and self.logger.debug(f"[ServerWorker {self.id}] Storing Sent Packet {packetsent.seq_number}")
            self.lastPacketSent = packetsent
        if packetrecv is not None:
            self._LOGGING_ and self.logger.debug(f"[ServerWorker {self.id}] Storing Recv Packet {packetrecv.seq_number}")
            self.lastPacketRecv = packetrecv

    # Method of starting a data transfer
    def makeTransferPacket(self,packet):
        response = None
        chunk, push = self.bufOverlay.getChunk()
        transpacket = self.generateTransferPacket(packet,chunk,push)
        response = transpacket
        if push and not self.bufOverlay.anyIndex():
            self._LOGGING_ and self.logger.debug(f"[ServerWorker {self.id}] makeTransferPacket with PUSH")
        return response

    # Method that extracts data (if any) from a packet received from the client (by full-duplex).
    def extractIncomingData(self,packet):
        if any(packet.data_len) == False or any(packet.content) == False:
            return
        self.bufWrapper.addChunk(packet)
        return

    # Method that manages Polling Requests, Confirmations and Data Transfer packets
    # Data transfers can be full duplex
    def doWork(self,packet,wsrvinbox):
        response = None
        packettosend = None
        if packet.anyContentAvailable():
            self.extractIncomingData(packet)
            if packet.isFlagActive(Flags.PUSH):
                data_decrypt = self.decryptWrapperData()
                self.overlay.inbox.put(Message("serverworker",self.id,'overlay',0,MessageType.STREAM,data_decrypt))
                if self.someOverlayData():
                    packettosend = self.makeTransferPacket(packet)
                    response = Message("serverworker",self.id,"router",0,MessageType.STREAM,packettosend.toBytes(),wsrvinbox)
                else:
                    packettosend = self.generatePollResponse(packet)
                    response = Message("serverworker",self.id,"router",0,MessageType.STREAM,packettosend.toBytes(),wsrvinbox)
            else:
                if self.someOverlayData():
                    packettosend = self.makeTransferPacket(packet)
                    response = Message("serverworker",self.id,"router",0,MessageType.STREAM,packettosend.toBytes(),wsrvinbox)
                else:
                    packettosend = self.generatePollResponse(packet)
                    response = Message("serverworker",self.id,"router",0,MessageType.STREAM,packettosend.toBytes(),wsrvinbox)
        else:
            if self.someOverlayData():
                packettosend = self.makeTransferPacket(packet)
                response = Message("serverworker",self.id,"router",0,MessageType.STREAM,packettosend.toBytes(),wsrvinbox)
            else:
                packettosend = self.generatePollResponse(packet)
                response = Message("serverworker",self.id,"router",0,MessageType.STREAM,packettosend.toBytes(),wsrvinbox)
        self.storePackets(packet,packettosend)
        self._LOGGING_ and self.logger.debug(f"[{self.name}] Header Sent: {response.printHeader()}")
        return response

    # Method that responds to a client termination request
    def doTermination(self,packet,wsrvinbox):
        self._LOGGING_ and self.logger.debug(f"[ServerWorker {self.id}] initializing Termination process")
        pollpacket = self.generatePollResponse(packet)
        self.st = Status.TERMINATING
        self.storePackets(packet,pollpacket)
        self.overlay.inbox.put(Message("serverworker",self.id,'overlay',0,MessageType.SIGNAL,SignalType.COMMS_FINISHED))
        return Message("serverworker",self.id,"router",0,MessageType.STREAM,pollpacket.toBytes(),wsrvinbox)

    # Method that performs the session reinitialization process
    def doReinitialization(self, packet):
        reinitpacket = self.generateReinitResponse(packet)
        self.storePackets(packet, reinitpacket)
        return reinitpacket.toBytes()

    # Trigger method that performs the checks associated with each function and then invokes it
    # by returning a response.
    def initialChecks(self, msg, checkerFunc, nextFunc):
        self._LOGGING_ and self.logger.debug(f"[{self.name}] Header Recv: {msg.printHeader()}")
        p = self.transformToPacket(msg.content)
        if p is None:
            self._LOGGING_ and self.logger.error(f"[ServerWorker {self.id}] cannot convert data to sotp packet, re-sending...")
            return Message("serverworker",self.id,"router",0,MessageType.STREAM,self.lostPacket().toBytes(),msg.wrapServerQ)
        if self.checkReinitialization(p):
            return Message("serverworker",self.id,"router",0,MessageType.STREAM,self.doReinitialization(p),msg.wrapServerQ)
        if self.checkTermination(p):
            self._LOGGING_ and self.logger.info(f"[ServerWorker {self.id}] termination packet detection")
            return self.doTermination(p,msg.wrapServerQ)
        if checkerFunc(p) is False:
            self._LOGGING_ and self.logger.error(f"[ServerWorker {self.id}] {checkerFunc} has failed, re-sending...")
            return Message("serverworker",self.id,"router",0,MessageType.STREAM,self.lostPacket().toBytes(),msg.wrapServerQ)
        if self.checkConfirmation(p) is False:
            self._LOGGING_ and self.logger.error(f"[ServerWorker {self.id}] cannot confirm our last sent packet, re-sending...")
            return Message("serverworker",self.id,"router",0,MessageType.STREAM,self.lostPacket().toBytes(),msg.wrapServerQ)
        return nextFunc(p,msg.wrapServerQ)

    # Method that processes the data from the overlay and stores it in its buffer.
    def overlayProcessing(self, data):
        self._LOGGING_ and self.logger.debug(f"[DataThread] {data.sender} sent {len(data.content)} bytes of data, storing...")
        self.storeOverlayContent(data.content)

    # A method (running on a thread) that receives the data from the overlay, encrypts it, 
    # chunks it and saves it parallel to the mistica server thread.
    def dataEntry(self):
        while True:
            data = self.datainbox.get()
            if data.isTerminateMessage():
                break
            self.overlayProcessing(data)
        self._LOGGING_ and self.logger.debug(f"[DataThread] Terminated")

    # Handler for STREAM (data) type messages
    def handleStream(self, msg):
        if self.st == Status.WORKING:
            self.outbox.put(self.initialChecks(msg, self.checkWorkRequest, self.doWork))
        elif self.st == Status.TERMINATING:
            self.overlay.inbox.put(Message("serverworker",self.id,'overlay', self.overlay.id, MessageType.SIGNAL,SignalType.COMMS_FINISHED))

    # Handler for SIGNAL type messages.
    def handleSignal(self, msg):
        if msg.isTerminateMessage():
            self.datainbox.put(Message("serverworker", self.id, "datathread", 0, MessageType.SIGNAL, SignalType.TERMINATE))
            self.exit = True

    # Entry point of the associated Worker when creating a new session with a client.
    def run(self):
        self._LOGGING_ and self.logger.info(f"[ServerWorker {self.id}] associated with {self.overlay.name} started!")
        dataThread = Thread(target=self.dataEntry)
        dataThread.start()
        while (not self.exit):
            msg = self.inbox.get()
            if (msg.isSignalMessage()):
                self.handleSignal(msg)
                continue
            self.handleStream(msg)
        self._LOGGING_ and self.logger.debug(f"[ServerWorker {self.id}] Terminated")
