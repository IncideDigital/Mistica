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

class io(ClientOverlay):

    NAME = "io"

    def __init__(self, qsotp, qdata, args, logger=None):
        ClientOverlay.__init__(self,type(self).__name__,qsotp,qdata,args,logger)
        self.name = type(self).__name__
        # Setting input capture
        self.hasInput = True
        # Logger parameters
        self.logger = logger
        self._LOGGING_ = False if logger is None else True

    def processInputStream(self, content):
        self._LOGGING_ and self.logger.debug(f"[{self.name}] Read from STDIN: {len(content)} bytes")
        return content

    def processSOTPStream(self, content):
        self._LOGGING_ and self.logger.debug(f"[{self.name}] Write to STDOUT: {len(content)} bytes")
        stdout.buffer.write(content)
        stdout.flush()