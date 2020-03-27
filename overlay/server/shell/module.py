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
from subprocess import Popen,PIPE,STDOUT
from platform import system


def getInstance(id, qsotp, mode, args, logger):
    return shell(id, qsotp, mode, args, logger)


class shell(ServerOverlay):

    def __init__(self, id, qsotp, mode, args, logger):
        ServerOverlay.__init__(self, type(self).__name__, id, qsotp, mode, args, logger)
        self.name = type(self).__name__
        self.hasInput = False
        # Logger parameters
        self.logger = logger
        self._LOGGING_ = False if logger is None else True

    def processSOTPStream(self, content):
        data = b""
        try:
            # Windows by default pass Popen data to CreateProcess() Winapi
            if system() == "Windows":
                commandline = "cmd /c " + str(content,"utf-8")
            else:
                commandline = str(content,"utf-8")

            p = Popen(commandline.split(), stdout=PIPE, stderr=STDOUT)
            data = p.communicate()[0]
        except Exception as e:
            self._LOGGING_ and self.logger.exception(f"[{self.name}] Exception in shell: {str(e)}")
        finally:
            # By default, only one worker.
            (len(data) > 0) and self.workers[0].datainbox.put(self.streamToSOTPWorker(data,self.workers[0].id))
