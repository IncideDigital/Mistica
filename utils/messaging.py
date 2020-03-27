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
from enum import Enum
from sotp.core import Header,OptionalHeader,Sizes,Offsets,Status,Flags,Sync
from sotp.core import Core


class MessageType(Enum):
    STREAM = 0
    SIGNAL = 1


class SignalType(Enum):
    START = 0
    TERMINATE = 1
    STOP = 2
    RESTART = 3
    COMMS_FINISHED = 4
    COMMS_BROKEN = 5
    ERROR = 6
    BUFFER_READY = 7


class Message():
    '''
    {
        from : string,
        from_id : int,
        to : string,
        to_id : int,
        type : int,
        content : (Arbitrary),
        wrapServerQ: Queue (only in Mistica Server)
    }
    '''
    def __init__(self, sender, sender_id, receiver, receiver_id, msgtype, content, wrapServerQ=None):
        self.sender = sender
        self.sender_id = sender_id
        self.receiver = receiver
        self.receiver_id = receiver_id
        self.msgtype = msgtype
        self.content = content
        self.wrapServerQ = wrapServerQ

    def __eq__(self, other):
        return self.sender == other.sender and self.receiver == other.receiver and self.msgtype == other.msgtype and self.content == other.content

    def isCommsFinishedMessage(self):
        if self.msgtype == MessageType.SIGNAL and self.content == SignalType.COMMS_FINISHED:
            return True
        return False

    def isCommsBrokenMessage(self):
        if self.msgtype == MessageType.SIGNAL and self.content == SignalType.COMMS_BROKEN:
            return True
        return False

    def isTerminateMessage(self):
        if self.msgtype == MessageType.SIGNAL and self.content == SignalType.TERMINATE:
            return True
        return False

    def isCommunicationEndedMessage(self):
        if self.msgtype == MessageType.SIGNAL and self.content == SignalType.COMMS_FINISHED:
            return True
        return False

    def isCommunicationBrokenMessage(self):
        if self.msgtype == MessageType.SIGNAL and self.content == SignalType.COMMS_BROKEN:
            return True
        return False

    def isStartMessage(self):
        if self.msgtype == MessageType.SIGNAL and self.content == SignalType.START:
            return True
        return False

    def isStopMessage(self):
        if self.msgtype == MessageType.SIGNAL and self.content == SignalType.STOP:
            return True
        return False

    def isRestartMessage(self):
        if self.msgtype == MessageType.SIGNAL and self.content == SignalType.RESTART:
            return True
        return False

    def isBufferReady(self):
        if self.msgtype == MessageType.SIGNAL and self.content == SignalType.BUFFER_READY:
            return True
        return False

    def isStreamMessage(self):
        return (self.msgtype == MessageType.STREAM)

    def isSignalMessage(self):
        return (self.msgtype == MessageType.SIGNAL)

    # method for print/debug messages
    def printHeader(self):
        if self.isSignalMessage():
            return f"Signal Message: {self.content}"
        if not self.isStreamMessage():
            return "Message is not a Stream Message"
        try:
            p = Core.transformToPacket(self.content)
            sid = p.session_id.uint
            sq = p.seq_number.uint
            ack = p.ack.uint
            dl = p.data_len.uint
            fl = p.flags.uint
            oh = p.optional_headers
            st = p.sync_type.uint if fl == 1 else 0
            return f"SID: {sid}, SQ: {sq}, ACK: {ack}, DL: {dl}, FL: {fl}, OH: {oh}, SYT: {st}"
        except Exception:
            return f"Message content is not a SOTP Packet {self.content}"
