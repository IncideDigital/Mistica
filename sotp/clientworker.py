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
from sotp.core import Header,OptionalHeader,Sizes,Offsets,Status,Flags,Sync
from sotp.core import Core
from sotp.packet import Packet
from utils.bitstring import BitArray
from utils.rc4 import RC4
from utils.messaging import Message,SignalType,MessageType


class ClientWorker(Core):

    def __init__(self, key, maxretries, maxsize, tag, overlayname, wrappername, qdata, logger=None):
        super().__init__(key, maxretries, maxsize)
        self.name = type(self).__name__
        self.wait_reply = False
        self.sotp_first_push = False
        self.transceiving = False
        self.st = Status.NOT_INITIALIZING
        self.oldst = None
        self.sid = None
        self.tag = tag
        self.overlayname = overlayname
        self.wrappername = wrappername
        self.qdata = qdata
        self.seqnumber = 1
        self.comms_broken = False
        self.exit = False
        # Logger parameters
        self.logger = logger
        self._LOGGING_ = False if logger is None else True

    # Method for checking if a packet is an initialization response.
    def checkInitResponse(self,packet):
        if any(packet.session_id) == False:
            return False
        if any(packet.seq_number) == False:
            return False
        if any(packet.ack) == False:
            return False
        if packet.isFlagActive(Flags.SYNC) == False:
            return False
        if packet.isSyncType(Sync.RESPONSE_AUTH) == False:
            return False
        return True

    # Method to check if a packet is a correct response from the server.
    def checkWorkResponse(self,packet):
        if any(packet.session_id) == False:
            return False
        if any(packet.seq_number) == False:
            return False
        if any(packet.ack) == False:
            return False
        if not any(packet.data_len) and not any(packet.content):
            return True
        if packet.data_len.uint != int(packet.content.length/8):
            return False
        return True

    # Method to check if session reinitialization is needed (because the seq_number is limited to n bytes)
    def checkReinitialization(self,packet):
        if self.lastPacketSent is None:
            raise Exception('Cannot get last sent packet')
        if self.lastPacketSent.seq_number != packet.ack:
            self._LOGGING_ and self.logger.error(f"[{self.name}] on checkReinitialization() ack: {packet.ack} != seq: {self.lastPacketSent.seq_number}")
            return False
        if self.lastPacketSent.seq_number.uint != (Sizes.MAX_MESSAGES-1):
            return False
        self._LOGGING_ and self.logger.info(f"[{self.name}] Reinitialization is needed!")
        return True

    # functionality will be implemented in the future
    def checkForStop(self,packet):
        return True

    # Method for generating an initialization packet
    # The overlay tag to be used is added to the data field
    def generateInitPacket(self):
        p = Packet()
        p.session_id = BitArray(bin='0'*Header.SESSION_ID)
        p.seq_number = BitArray(uint=self.seqnumber,length=Header.SEQ_NUMBER)
        p.ack = BitArray(bin='0'*Header.ACK)
        p.data_len = BitArray(uint=len(self.tag),length=Header.DATA_LEN)
        p.flags = BitArray(uint=Flags.SYNC,length=Header.FLAGS)
        p.optional_headers = True
        p.sync_type = BitArray(uint=Sync.REQUEST_AUTH,length=OptionalHeader.SYNC_TYPE)
        p.content = BitArray(bytes=BitArray(hex=self.tag).bytes, length=Sizes.TAG)
        return p

    # Method for generating a polling request packet
    def generatePollPacket(self,packt):
        p = Packet()
        p.session_id = self.sid
        self.seqnumber+=1
        p.seq_number = BitArray(uint=self.seqnumber,length=Header.SEQ_NUMBER)
        p.ack = packt.seq_number
        p.data_len = BitArray(bin='0'*Header.DATA_LEN)
        p.flags = BitArray(uint=Flags.SYNC,length=Header.FLAGS)
        p.optional_headers = True
        p.sync_type = BitArray(uint=Sync.POLLING_REQUEST,length=OptionalHeader.SYNC_TYPE)
        p.content = BitArray()
        return p

    # Method that generates a response packet to a session termination request
    def generateTermResponsePacket(self,packt):
        p = Packet()
        p.session_id = self.sid
        self.seqnumber+=1
        p.seq_number = BitArray(uint=self.seqnumber,length=Header.SEQ_NUMBER)
        p.ack = packt.seq_number
        p.data_len = BitArray(bin='0'*Header.DATA_LEN)
        p.flags = BitArray(bin='0'*Header.FLAGS)
        p.sync_type = BitArray()
        p.content = BitArray()
        return p

    # Method that generates a session reintialization packet
    def generateReintializationPacket(self,packt):
        p = Packet()
        p.session_id = self.sid
        self.seqnumber+=1
        p.seq_number = BitArray(uint=self.seqnumber,length=Header.SEQ_NUMBER)
        p.ack = packt.seq_number
        p.data_len = BitArray(bin='0'*Header.DATA_LEN)
        p.flags = BitArray(uint=Flags.SYNC,length=Header.FLAGS)
        p.optional_headers = True
        p.sync_type = BitArray(uint=Sync.REINITIALIZING,length=OptionalHeader.SYNC_TYPE)
        p.content = BitArray()
        return p

    # Method to generate a session termination request packet
    def generateTerminatePacket(self,packt):
        p = Packet()
        p.session_id = self.sid
        self.seqnumber+=1
        p.seq_number = BitArray(uint=self.seqnumber,length=Header.SEQ_NUMBER)
        p.ack = packt.seq_number
        p.data_len = BitArray(bin='0'*Header.DATA_LEN)
        p.flags = BitArray(uint=Flags.SYNC,length=Header.FLAGS)
        p.optional_headers = True
        p.sync_type = BitArray(uint=Sync.SESSION_TERMINATION,length=OptionalHeader.SYNC_TYPE)
        p.content = BitArray()
        return p

    # Method to generate a transfer packet (with data from the overlay).
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

    # Method to generate a confirmation packet
    def generateAckPacket(self,packt):
        p = Packet()
        p.session_id = self.sid
        self.seqnumber+=1
        p.seq_number = BitArray(uint=self.seqnumber,length=Header.SEQ_NUMBER)
        p.ack = packt.seq_number
        p.data_len = BitArray(bin='0'*Header.DATA_LEN)
        p.flags = BitArray(bin='0'*Header.FLAGS)
        p.sync_type = BitArray()
        p.content = BitArray()
        return p

    # Method that generates a polling packet based on the last packet received
    def getPollRequest(self):
        if self.lastPacketRecv is None:
            self._LOGGING_ and self.logger.error(f"[{self.name}] Any previous Packet Received in getPollRequest()")
            raise Exception("Any previous Packet Received in getPollRequest()")
        packettosend = self.generatePollPacket(self.lastPacketRecv)
        self.storePackets(None,packettosend)
        return [Message("clientworker",0,self.wrappername,0,MessageType.STREAM,packettosend.toBytes())]

    # Method that updates the reference to the last package sent and/or received.
    def storePackets(self,packetrecv,packetsent):
        if packetsent is not None:
            self._LOGGING_ and self.logger.debug(f"[{self.name}] Storing Sent Packet sq:{packetsent.seq_number} ack:{packetsent.ack}")
            self.lastPacketSent = packetsent
        if packetrecv is not None:
            self._LOGGING_ and self.logger.debug(f"[{self.name}] Storing Recv Packet sq:{packetrecv.seq_number} ack:{packetrecv.ack}")
            self.lastPacketRecv = packetrecv

    # Method that receives the Initialization Response, sets the session_id (from response packet)
    # and sends the overlay data, if it doesn't have it, simply generate a Polling Request packet.
    def doInitialize(self,packet):
        if self.sid is None:
            self.sid = packet.session_id
        packettosend = None
        if self.someOverlayData():
            self._LOGGING_ and self.logger.debug(f"[{self.name}] detected Overlay data in doInitialize()")
            packettosend = self.makeTransferPacket(packet)
            self.transceiving = True
        else:
            self._LOGGING_ and self.logger.debug(f"[{self.name}] generating Polling Request")
            packettosend = self.generatePollPacket(packet)
            self.transceiving = False
        self.wait_reply = True
        self.storePackets(packet,packettosend)
        self.st = Status.WORKING
        return [Message("clientworker",0,self.wrappername,0,MessageType.STREAM,packettosend.toBytes())]

    # Method that manages Polling Responses, Confirmations and Data Transfer packets
    # Data transfers can be full duplex
    def doWork(self,packet):
        response = []
        packettosend = None
        if packet.anyContentAvailable():
            self.extractIncomingData(packet)
            if packet.isFlagActive(Flags.PUSH):
                data_decrypt = self.decryptWrapperData()
                response.append(Message("clientworker",0,self.overlayname,0,MessageType.STREAM,data_decrypt))
                if self.someOverlayData():
                    packettosend = self.makeTransferPacket(packet)
                    response.append(Message("clientworker",0,self.wrappername,0,MessageType.STREAM,packettosend.toBytes()))
                else:
                    packettosend = self.generatePollPacket(packet)
                    response.append(Message("clientworker",0,self.wrappername,0,MessageType.STREAM,packettosend.toBytes()))
            else:
                if self.someOverlayData():
                    packettosend = self.makeTransferPacket(packet)
                    response.append(Message("clientworker",0,self.wrappername,0,MessageType.STREAM,packettosend.toBytes()))
                else:
                    packettosend = self.generateAckPacket(packet)
                    response.append(Message("clientworker",0,self.wrappername,0,MessageType.STREAM,packettosend.toBytes()))
            self.wait_reply = True
            self.transceiving = True
        else:
            if self.someOverlayData():
                packettosend = self.makeTransferPacket(packet)
                response.append(Message("clientworker",0,self.wrappername,0,MessageType.STREAM,packettosend.toBytes()))
                self.wait_reply = True
                self.transceiving = True
            else:
                self.wait_reply = False
                self.transceiving = False
        self.storePackets(packet,packettosend)
        return response

    # Method that extracts data (if any) from a packet received from the server (by full-duplex).
    def extractIncomingData(self,packet):
        if any(packet.data_len) == False or any(packet.content) == False:
            return
        self.bufWrapper.addChunk(packet)
        return

    # Method of starting a data transfer
    def makeTransferPacket(self,packet):
        response = None
        chunk, push = self.bufOverlay.getChunk()
        transpacket = self.generateTransferPacket(packet,chunk,push)
        response = transpacket
        if push and not self.bufOverlay.anyIndex():
            self.sotp_first_push = True
        self.lastPacketSent = transpacket
        return response

    # Method that responds to a server termination request
    def doTermination(self,packet):
        termpacket = self.generateTermResponsePacket(packet)
        self.st = Status.TERMINATING
        self.storePackets(packet,termpacket)
        return [
            Message("clientworker",0,self.overlayname,0,MessageType.SIGNAL,SignalType.COMMS_FINISHED),
            Message("clientworker",0,self.wrappername,0,MessageType.STREAM,termpacket.toBytes())
        ]

    # Method that performs the session reinitialization process
    def doReintialization(self,packt):
        repackt = self.generateReintializationPacket(packt)
        self.oldst = self.st
        self.st = Status.REINITIALIZING
        self.storePackets(packt,repackt)
        self.seqnumber=0
        return [Message("clientworker",0,self.wrappername,0,MessageType.STREAM,repackt.toBytes())]

    # functionality will be completed in the future
    def initializeStop(self,packt):
        stopackt = self.generateTerminatePacket(packt)
        self.st = Status.TERMINATING
        self.storePackets(packt,stopackt)
        return [Message("clientworker",0,self.wrappername,0,MessageType.STREAM,stopackt.toBytes())]

    # Method that resets the previous state after a session reinitialization.
    def resetSession(self,packet):
        response = []
        self.st = self.oldst
        packettosend = None
        if self.someOverlayData():
            self._LOGGING_ and self.logger.debug(f"[{self.name}] Overlay data detected, making transfer packet...")
            packettosend = self.makeTransferPacket(packet)
            response.append(Message("clientworker",0,self.wrappername,0,MessageType.STREAM,packettosend.toBytes()))
            self.wait_reply = True
            self.transceiving = True
        else:
            self._LOGGING_ and self.logger.debug(f"[{self.name}] No overlay data, waiting...")
            self.wait_reply = False
            self.transceiving = False
        self.storePackets(packet,packettosend)
        return response

    # Method used to resend the previous package, if it has not exceeded the maximum number of retries,
    # otherwise, loss of communication is reported
    def lookForRetries(self):
        if self.checkForRetries():
            self._LOGGING_ and self.logger.error(f"[{self.name}] exceeded the maximum number of retries")
            self.comms_broken = True
            return [Message("clientworker",0,self.overlayname,0,MessageType.SIGNAL,SignalType.COMMS_BROKEN)]
        else:
            packt = self.lostPacket()
            self.storePackets(packt,packt)
            return [Message("clientworker",0,self.wrappername,0,MessageType.STREAM,packt.toBytes())]

    # Trigger method that performs the checks associated with each function and then invokes it
    # by returning a response.
    def initialChecks(self,data,checkerFunc,nextFunc):
        try:
            p = self.transformToPacket(data.content)
            if self.st != Status.REINITIALIZING and self.checkReinitialization(p):
                self._LOGGING_ and self.logger.debug(f"[{self.name}] Reinitialization Request Packet detected")
                return self.doReintialization(p)
            if self.checkTermination(p):
                self._LOGGING_ and self.logger.debug(f"[{self.name}] Termination Request Packet detected")
                return self.doTermination(p)
            if checkerFunc(p) == False:
                self._LOGGING_ and self.logger.error(f"[{self.name}] {str(checkerFunc)} has failed, re-sending...")
                return self.lookForRetries()
            if self.checkConfirmation(p) == False:
                self._LOGGING_ and self.logger.error(f"[{self.name}] checkConfirmation has failed, lpks: {self.lastPacketSent.seq_number} != ack: {p.ack}")
                return self.lookForRetries()
            return nextFunc(p)
        except Exception as e:
            self._LOGGING_ and self.logger.exception(f"[{self.name}] initialChecks Exception: {e}")
            return [Message("clientworker",0,self.overlayname,0,MessageType.SIGNAL,SignalType.ERROR)]

    # Method that processes data from the Wrapper (messages/packets from the server).
    def wrapperProcessing(self, data):
        self._LOGGING_ and self.logger.debug(f"[{self.name}] Processing data from Wrapper. Status: {self.st}")
        if self.st == Status.INITIALIZING:
            return self.initialChecks(data,self.checkInitResponse,self.doInitialize)
        elif self.st == Status.WORKING:
            return self.initialChecks(data,self.checkWorkResponse,self.doWork)
        elif self.st == Status.TERMINATING:
            self.st = Status.NOT_INITIALIZING
            return [Message("clientworker",0,self.overlayname,0,MessageType.SIGNAL,SignalType.COMMS_FINISHED)]
        elif self.st == Status.REINITIALIZING:
            self._LOGGING_ and self.logger.debug(f"[{self.name}] About to reset session")
            return self.initialChecks(data,self.checkWorkResponse,self.resetSession)
        elif self.st == Status.STOPING:
            return self.initialChecks(data,self.checkForStop,self.initializeStop)
        else:
            self._LOGGING_ and self.logger.error(f"[{self.name}] Invalid status on Wrapper Processing: {self.st}")
            raise Exception(f"Invalid status on Wrapper Processing: {self.st}")

    # Method that processes the data from the overlay and stores it in its buffer.
    def overlayProcessing(self, data):
        self._LOGGING_ and self.logger.debug(f"[DataThread] {data.sender} sent {len(data.content)} bytes of data, storing...")
        self.storeOverlayContent(data.content)
        if self.sid and not self.wait_reply and not self.transceiving:
            return Message("datathread",0,"clientworker",0,MessageType.SIGNAL,SignalType.BUFFER_READY)
        return

    # A method (running on a thread) that receives the data from the overlay, encrypts it, 
    # chunks it and saves it parallel to the mistica client loop.
    def dataEntry(self,qsotp):
        while True:
            data = self.qdata.get()
            if data.isTerminateMessage() and data.sender == "clientworker":
                break
            msg = self.overlayProcessing(data)
            if msg is not None:
                qsotp.put(msg)

    # Entry point for data messages received by the sotp of the wrapper
    def streamEntry(self, data):
        if data.sender == self.wrappername:
            self.retries = 0
            self._LOGGING_ and self.logger.debug(f"[{self.name}] Header Recv: {data.printHeader()}")
            return self.wrapperProcessing(data)
        else:
            self._LOGGING_ and self.logger.error(f"[{self.name}] Invalid sender on streamEntry {data.sender} not [{self.overlayname}||{self.wrappername}]")
            raise Exception(f"Invalid sender on streamEntry {data.sender} wait {self.wrappername}")

    # Entry point for signal messages received by the sotp of the wrapper and/or overlay
    def signalEntry(self, data):
        response = []
        if data.isTerminateMessage():
            self._LOGGING_ and self.logger.debug_all(f"[{self.name}] signalEntry() received a signal terminate")
            if self.lastPacketRecv and self.sid:
                termpacket = self.generateTerminatePacket(self.lastPacketRecv)
                self._LOGGING_ and self.logger.debug_all(f"[{self.name}] signalEntry() coms active, so sending a termination request")
                not self.comms_broken and response.append(Message("clientworker",0,self.wrappername,0,MessageType.STREAM,termpacket.toBytes()))
            response.append(Message("clientworker",0,self.wrappername,0,MessageType.SIGNAL,SignalType.TERMINATE))
            self.qdata.put(Message("clientworker",0,'datathread',0,MessageType.SIGNAL,SignalType.TERMINATE))
            self.exit = True
        elif self.st == Status.NOT_INITIALIZING and data.isStartMessage():
            self._LOGGING_ and self.logger.debug_all(f"[{self.name}] signalEntry() received a signal Start")
            p = self.generateInitPacket()
            self.wait_reply = True
            response.append(Message("clientworker",0,self.wrappername,0,MessageType.STREAM,p.toBytes()))
            self.lastPacketSent = p
            self.st = Status.INITIALIZING
        elif data.isStopMessage():
            self._LOGGING_ and self.logger.debug_all(f"[{self.name}] signalEntry() received a signal Stop")
            self.st = Status.STOPING
        elif data.isCommunicationBrokenMessage():
            self._LOGGING_ and self.logger.debug_all(f"[{self.name}] signalEntry() received a signal CommunicationBrokenMessage")
            response = self.lookForRetries()
        elif data.isBufferReady() and self.lastPacketSent is not None:
            self._LOGGING_ and self.logger.debug_all(f"[{self.name}] signalEntry() received a signal Buffer Ready")
            if not self.transceiving:
                self.transceiving = True
                self._LOGGING_ and self.logger.debug_all(f"[{self.name}] signalEntry() not transceiving so generate a transfer packet")
                dpacket = self.makeTransferPacket(self.lastPacketRecv)
                response.append(Message("clientworker",0,self.wrappername,0,MessageType.STREAM,dpacket.toBytes()))
        else:
            self._LOGGING_ and self.logger.error(f"[{self.name}] Invalid signal on streamEntry {data}")
            raise Exception(f"Invalid signal on streamEntry {data}")
        return response

    # Main entry point, separated based on message type: data or signal
    def Entrypoint(self,data):
        try:
            if data.msgtype == MessageType.SIGNAL:
                self._LOGGING_ and self.logger.debug_all(f"[{self.name}] passing a signal message to Entrypoint")
                return self.signalEntry(data)
            else:
                self._LOGGING_ and self.logger.debug_all(f"[{self.name}] passing a stream message to Entrypoint")
                return self.streamEntry(data)
        except Exception as e:
            self._LOGGING_ and self.logger.exception(f"[{self.name}] Exception in Entrypoint: {e}")
            return self.lookForRetries()
