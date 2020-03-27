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
from sotp.packet import Packet
from utils.bitstring import BitArray
from utils.rc4 import RC4
from utils.buffer import Index, OverlayBuffer, WrapperBuffer


BYTE = 8


class Header(object):
    SESSION_ID = 1 * BYTE
    SEQ_NUMBER = 2 * BYTE
    ACK = 2 * BYTE
    DATA_LEN = 2 * BYTE
    FLAGS = 1 * BYTE


class OptionalHeader(object):
    SYNC_TYPE = 1 * BYTE


class Sizes(object):
    HEADER = Header.SESSION_ID + Header.SEQ_NUMBER + Header.ACK + Header.DATA_LEN + Header.FLAGS
    OPTIONAL_HEADER = OptionalHeader.SYNC_TYPE
    MAX_MESSAGES = (2**Header.SEQ_NUMBER)-1
    TAG = 2 * BYTE


class Offsets(object):
    SESSION_ID = 0 + Header.SESSION_ID
    SEQ_NUMBER = SESSION_ID + Header.SEQ_NUMBER
    ACK = SEQ_NUMBER + Header.ACK
    DATA_LEN = ACK + Header.DATA_LEN
    FLAGS = DATA_LEN + Header.FLAGS
    SYNC_TYPE = 0 + OptionalHeader.SYNC_TYPE


class Status(object):
    NOT_INITIALIZING = 0
    INITIALIZING = 1
    WORKING = 2
    TERMINATING = 3
    REINITIALIZING = 4
    STOPING = 5


class Flags(object):
    SYNC = 1
    PUSH = 2


class Sync(object):
    REQUEST_AUTH = 0
    RESPONSE_AUTH = 1
    REINITIALIZING = 2
    POLLING_REQUEST = 5
    SESSION_TERMINATION = 6


class Core(object):

    def __init__(self, key, maxretries, maxsize):
        self.rc4 = RC4(bytes(key, encoding='utf8'), False)
        self.st = Status.NOT_INITIALIZING
        self.maxretries = maxretries
        self.retries = 0
        self.lastPacketSent = None
        self.lastPacketRecv = None
        self.bufOverlay = OverlayBuffer()
        self.bufWrapper = WrapperBuffer()
        self.checkMaxSizeAvailable(maxsize)

    def checkMaxSizeAvailable(self, maxsize):
        if maxsize > 2**Header.DATA_LEN:
            raise Exception(f"MaxSize {maxsize} is exced {2**Header.DATA_LEN} which is max representation with {Header.DATA_LEN} bits of Data Length")
        self.maxsize = maxsize

    @staticmethod
    def fromBytesToBitArray(data):
        return BitArray(bytes=data)

    @staticmethod
    def parseRawPacket(binarypacket):
        if len(binarypacket) < Sizes.HEADER:
            raise Exception(f"Raw Packet size {len(binarypacket)} is lower than the minimun Header size {Sizes.HEADER}")
        return binarypacket[:Sizes.HEADER], binarypacket[Sizes.HEADER:]

    @staticmethod
    def buildPacket(header, body):
        p = Packet()
        p.session_id = header[0:Offsets.SESSION_ID]
        p.seq_number = header[Offsets.SESSION_ID:Offsets.SEQ_NUMBER]
        p.ack = header[Offsets.SEQ_NUMBER:Offsets.ACK]
        p.data_len = header[Offsets.ACK:Offsets.DATA_LEN]
        p.flags = header[Offsets.DATA_LEN:Offsets.FLAGS]
        p.sync_type = None
        p.content = None
        if p.isFlagActive(Flags.SYNC):
            p.sync_type = BitArray(bin=body.bin[0:Offsets.SYNC_TYPE])
            p.content = BitArray(bin=body.bin[Offsets.SYNC_TYPE:])
            p.optional_headers = True
        else:
            p.sync_type = BitArray()
            p.content = BitArray(bin=body.bin)
        return p

    @staticmethod
    def transformToPacket(rawbytes):
        bitarraydata = Core.fromBytesToBitArray(rawbytes)
        header, body = Core.parseRawPacket(bitarraydata)
        packt = Core.buildPacket(header, body)
        return packt

    def checkMainFields(self,packt):
        if any(packt.session_id) == False:
            return False
        if any(packt.seq_number) == False:
            return False
        if any(packt.ack) == False:
            return False
        return True

    def checkForRetries(self):
        if self.retries == self.maxretries:
            self.retries = 0
            return True
        self.retries = self.retries + 1
        return False

    def lostPacket(self):
        if self.lastPacketSent is None:
            raise Exception("Last sent packet is None, cannot resend")
        else:
            return self.lastPacketSent

    def decryptWrapperData(self):
        packets = self.bufWrapper.getChunks()
        content = BitArray()
        for packet in packets:
            content.append('0b' + packet.content.bin)
        bytescontent = content.tobytes()
        decryptcontent = self.rc4.crypt(bytescontent)
        return decryptcontent

    def storeOverlayContent(self, data):
        data = self.rc4.crypt(data)
        index = Index()
        lendata = len(data)
        for i in range(0, lendata, self.maxsize):
            index.add(data[i:i + self.maxsize])
        self.bufOverlay.addIndex(index)

    def someOverlayData(self):
        return self.bufOverlay.anyIndex()

    def checkConfirmation(self,packt):
        if self.lastPacketSent is None:
            raise Exception("Haven't sent any packet, can't perform confirmation.")
        if self.lastPacketSent.seq_number != packt.ack:
            return False
        return True

    def checkTermination(self,packt):
        if self.checkMainFields(packt) == False:
            return False
        if packt.isFlagActive(Flags.SYNC) == False:
            return False
        if packt.isSyncType(Sync.SESSION_TERMINATION) == False:
            return False
        return True
