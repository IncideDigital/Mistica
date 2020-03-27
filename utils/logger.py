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
from logging import DEBUG, INFO, ERROR
from logging import Formatter, FileHandler, getLogger
from glob import glob as Glob
from os import remove as Remove

formatter = Formatter('%(asctime)s - %(message)s')

class Log():

    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3

    def __init__(self,prefix="",level=NONE):
        self.level = level
        if level != self.NONE:
            self.clearFiles(prefix)
            self.deb = self.setup_logger('debug_log', f"logs/debug{prefix}.log",DEBUG)
            self.inf = self.setup_logger('info_log', f"logs/info{prefix}.log",INFO)
            self.err = self.setup_logger('error_log', f"logs/error{prefix}.log",ERROR)
            self.exc = self.setup_logger('exception_log', f"logs/exception{prefix}.log",ERROR)

    def clearFiles(self,prefix):
        files = Glob(f"logs/*{prefix}.log")
        for f in files:
            Remove(f)
        
    def setup_logger(self, name, log_file, level):
        handler = FileHandler(log_file)        
        handler.setFormatter(formatter)

        logger = getLogger(name)
        logger.setLevel(level)
        logger.addHandler(handler)

        return logger

    def debug_all(self, message):
        if self.level == self.HIGH:
            self.deb.debug(message)

    def debug(self, message):
        if self.level > self.LOW:
            self.deb.debug(message)

    def error(self, message):
        if self.level != self.NONE:
            self.err.error(message)

    def info(self, message):
        if self.level != self.NONE:
            self.inf.info(message)

    def exception(self, message):
        if self.level != self.NONE:
            self.exc.exception(message)