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
from subprocess import Popen,PIPE,STDOUT
from platform import system


class shell(ClientOverlay):

    NAME = "shell"
    CONFIG = {
        "prog": NAME,
        "description": "Executes commands recieved through the SOTP connection and returns the output. Compatible with io module.",
        "args": [
            {
                "--tag": {
                "help": "Tag used by the overlay at the server",
                "nargs": 1,
                "required": False,
                "default": ["0x1010"]
                }
            }
        ]
    }


    def __init__(self, qsotp, qdata, args, logger=None):
        ClientOverlay.__init__(self,type(self).__name__,qsotp,qdata,args,logger)
        self.name = type(self).__name__
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
            return data if (len(data) > 0) else None