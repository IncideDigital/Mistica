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


def getInstance(id, qsotp, mode, args, logger):
    return io(id, qsotp, mode, args, logger)


class io(ServerOverlay):

    def __init__(self, id, qsotp, mode, args, logger):
        ServerOverlay.__init__(self, type(self).__name__, id, qsotp, mode, args, logger)
        self.name = type(self).__name__
        self.buffer = []
        # Setting input capture
        self.hasInput = True
        # Logger parameters
        self.logger = logger
        self._LOGGING_ = False if logger is None else True

    def processInputStream(self, content):
        self._LOGGING_ and self.logger.debug(f"[{self.name}] Read from STDIN: {len(content)}")
        return content

    def processSOTPStream(self, content):
        self._LOGGING_ and self.logger.debug(f"[{self.name}] Write to STDOUT: {len(content)}")
        stdout.buffer.write(content)
        stdout.flush()

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
