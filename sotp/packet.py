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
from utils.bitstring import BitArray

BYTE = 8

class Packet(object):
    def __init__(self):
        self.session_id = None
        self.seq_number = None
        self.ack = None
        self.data_len = None
        self.flags = None
        self.sync_type = None
        self.content = None
        self.optional_headers = False

    # Method for transforming a sotp packet into BitArray
    def toBytes(self):
        data = BitArray()
        data.append('0b'+self.session_id.bin)
        data.append('0b'+self.seq_number.bin)
        data.append('0b'+self.ack.bin)
        data.append('0b'+self.data_len.bin)
        data.append('0b'+self.flags.bin)
        if self.optional_headers:
            data.append('0b'+self.sync_type.bin)
        if any(self.content):
            data.append('0b'+self.content.bin)
        return data.tobytes()

    def isFlagActive(self,checkflag):
        return True if self.flags.uint == checkflag else False

    def isSyncType(self,checktype):
        return True if self.optional_headers and self.sync_type.uint == checktype else False

    def anyContentAvailable(self):
        return True if any(self.data_len) and any(self.content) else False
