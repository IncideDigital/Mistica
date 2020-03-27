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
class Index(object):
    def __init__(self):
        self.chunks = []
    
    def add(self, chunk):
        self.chunks.append(chunk)


class OverlayBuffer(object):
    def __init__(self):
        self.data = []
    
    def addIndex(self, index):
        self.data.append(index)

    def getChunk(self):
        if not self.data:
            raise Exception("There is no Index in OverlayBuffer")
        if not self.data[0].chunks:
            raise Exception("There is no Chunk in OverlayBuffer")
        chunk = self.data[0].chunks.pop(0)
        if not self.data[0].chunks:
            self.data.pop(0)
            return chunk,True
        return chunk,False

    def anyIndex(self):
        return True if self.data else False


class WrapperBuffer(object):
    def __init__(self):
        self.data = Index()
    
    def addChunk(self, chunk):
        self.data.add(chunk)

    def getChunks(self):
        if not self.data.chunks:
            raise Exception("There is no Chunk in WrapperBuffer")
        chunks = self.data.chunks
        self.data = Index()
        return chunks