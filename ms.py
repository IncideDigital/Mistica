#!/usr/bin/python3.7
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

import argparse
from utils.logger import Log
from utils.messaging import Message, SignalType, MessageType
from sotp.router import Router
from importlib import import_module
from signal import signal, SIGINT
from random import choice
from utils.prompt import Prompt
from sys import exit, stdin
from platform import system
from select import poll, POLLIN
from time import sleep


class MisticaMode:
    SINGLE = 0
    MULTI = 1


class ModuleType:
    WRAP_MODULE = 0
    WRAP_SERVER = 2
    OVERLAY = 3


class MisticaServer():

    def __init__(self, mode, key, verbose, moduleargs):
        # Get args and set attributes
        self.args = moduleargs
        # Logger params
        self.logger = Log('_server', verbose) if verbose > 0 else None
        self._LOGGING_ = False if self.logger is None else True
        # init Router
        self.key = key
        self.Router = Router(self.key, self.logger)
        self.Router.start()
        self.mode = mode
        self.procid = 0
        if self.mode == MisticaMode.SINGLE:
            self.overlayname = self.args["overlay"]
            self.wrappername = self.args["wrapper"]

    # Checks if the wrap_server of a certain wrap_module is up and running.
    def dependencyLaunched(self, name):
        dname = self.getDependencyName(name)
        for elem in self.Router.wrapServers:
            if dname == elem.name:
                return True
        return False

    # Gets the name of the wrap_server associated to a wrap_module
    def getDependencyName(self, name):
        modulename = f'wrapper.server.wrap_module.{name}.module'
        try:
            module = import_module(modulename)
        except Exception:
            print(f"Failed to import module {name}")
            return ""
        return module.getServerDependency()

    # Returns a wrap_module, wrap_server or overlay module
    def getModuleInstance(self, type, name, args):
        self.procid += 1
        if (type == ModuleType.WRAP_MODULE):
            mpath = f"wrapper.server.wrap_module.{name}.module"
            return import_module(mpath).getInstance(self.procid, self.Router.inbox, args, self.logger)
        elif (type == ModuleType.WRAP_SERVER):
            mpath = f"wrapper.server.wrap_server.{name}.module"
            return import_module(mpath).getInstance(self.procid, args, self.logger)
        else:
            mpath = f"overlay.server.{name}.module"
            return import_module(mpath).getInstance(self.procid, self.Router.inbox, self.mode, args, self.logger)

    def sigintDetect(self, signum, frame):
        self._LOGGING_ and self.logger.info("[Sotp] SIGINT detected")
        if (self.mode == MisticaMode.SINGLE):
            targetoverlay = self.Router.overlayModules[0]
            targetoverlay.inbox.put(Message('input',
                                            0,
                                            self.Router.overlayModules[0].name,
                                            self.Router.overlayModules[0].id,
                                            MessageType.SIGNAL,
                                            SignalType.TERMINATE))
        else:
            # TODO: Depends on who's on the foreground
            pass

    def captureInput(self, overlay):
        while True:
            if overlay.exit:
                break
            if system() != 'Windows':
                polling = poll()
            try:
                if system() == 'Windows':
                    # Ugly loop for windows
                    rawdata = stdin.buffer.raw.read(50000)
                    sleep(0.1)
                else:
                    # Nice loop for unix
                    polling.register(stdin.buffer.raw.fileno(), POLLIN)
                    polling.poll()

                    rawdata = stdin.buffer.raw.read(50000)
                    if rawdata == b'':  # assume EOF
                        self._LOGGING_ and self.logger.info("[MísticaServer] Input is dead")
                        self.Router.join()

                if rawdata and len(rawdata) > 0 and overlay.hasInput:
                    overlay.inbox.put(Message('input', 0, 'overlay', overlay.id, MessageType.STREAM, rawdata))
            except KeyboardInterrupt:
                self._LOGGING_ and self.logger.info("[MísticaServer] CTRL+C detected. Passing to overlay")
                overlay.inbox.put(Message('input',
                                          0,
                                          self.Router.overlayModules[0].name,
                                          self.Router.overlayModules[0].id,
                                          MessageType.SIGNAL,
                                          SignalType.TERMINATE))
                break
        return

    def run(self):

        # If the mode is single-handler only a wrapper module and overlay module is used
        if self.mode == MisticaMode.SINGLE:

            # Launch wrap_module
            wmitem = self.getModuleInstance(ModuleType.WRAP_MODULE, self.wrappername, self.args["wrapper_args"])
            wmitem.start()
            self.Router.wrapModules.append(wmitem)

            # Check wrap_server dependency of wrap_module and launch it
            wsname = self.getDependencyName(self.wrappername)
            if (not self.dependencyLaunched(self.wrappername)):
                wsitem = self.getModuleInstance(ModuleType.WRAP_SERVER, wsname, self.args["wrap_server_args"])
                wsitem.start()
                self.Router.wrapServers.append(wsitem)
            else:
                for elem in self.Router.wrapServers:
                    if wsname == elem.name:
                        wsitem = elem
                        break

            # add wrap_module to wrap_server list
            wsitem.addWrapModule(wmitem)

            # Launch overlay module
            omitem = self.getModuleInstance(ModuleType.OVERLAY, self.overlayname, self.args["overlay_args"])
            omitem.start()
            self.Router.overlayModules.append(omitem)
            targetoverlay = self.Router.overlayModules[0]
            self.captureInput(targetoverlay)
            self.Router.join()
            self._LOGGING_ and self.logger.debug("[MísticaServer] Terminated")
        elif self.mode == MisticaMode.MULTI:
            # Launch prompt etc.
            # Before registering a wrapper or an overlay, we must make sure that there is no other
            # module with incompatible parameters (e.g 2 DNS base64-based wrap_modules)
            self.Router.inbox.put(Message("Mistica", 0, "sotp", 0, MessageType.SIGNAL, SignalType.TERMINATE))
            print("Multi-handler mode is not implemented yet! use -h")
            exit(0)


if __name__ == '__main__':
    fortunes = ["The Last Protocol Bender.",
                "Your friendly data smuggler.",
                "Anything is a tunnel if you're brave enough.",
                "It's a wrap!",
                "The Overlay Overlord."]
    parser = argparse.ArgumentParser(description=f"Mistica server. {choice(fortunes)} Run without parameters to launch multi-handler mode.")
    parser.add_argument('-k', "--key", action='store', default="", required=False, help="RC4 key used to encrypt the comunications")
    parser.add_argument("-l", "--list", action='store', required=False, help="Lists modules or parameters. Options are: all, overlays, wrappers, <overlay name>, <wrapper name>")
    parser.add_argument("-m", "--modules", action='store', required=False, help="Module pair in single-handler mode. format: 'overlay:wrapper'")
    parser.add_argument("-w", "--wrapper-args", action='store', required=False, default='', help="args for the selected overlay module (Single-handler mode)")
    parser.add_argument("-o", "--overlay-args", action='store', required=False, default='', help="args for the selected wrapper module (Single-handler mode)")
    parser.add_argument("-s", "--wrap-server-args", action='store', required=False, default='', help="args for the selected wrap server (Single-handler mode)")
    parser.add_argument('-v', '--verbose', action='count', default=0, help="Level of verbosity in logger (no -v None, -v Low, -vv Medium, -vvv High)")

    args = parser.parse_args()
    moduleargs = {}

    if args.list:
        # list and quit
        if args.list == "all" or args.list == "overlays" or args.list == "wrappers":
            print(Prompt.listModules("server", args.list))
        else:
            Prompt.listParameteres("server", args.list)
        exit(0)
    elif args.modules:
        if args.key == "":
            print("You must suply a key for RC4 encryption. Use -k or --key")
            exit(1)
        moduleargs["overlay"] = args.modules.partition(":")[0]
        moduleargs["wrapper"] = args.modules.partition(":")[2]
        if Prompt.findModule("server", moduleargs["overlay"]) is None:
            print(f"Invalid overlay module {moduleargs['overlay']}. Please specify a valid module.")
            exit(1)
        if Prompt.findModule("server", moduleargs["wrapper"]) is None:
            print(f"Invalid wrap module {moduleargs['wrapper']}. Please specify a valid module.")
            exit(1)
        moduleargs["overlay_args"] = args.overlay_args
        moduleargs["wrapper_args"] = args.wrapper_args
        moduleargs["wrap_server_args"] = args.wrap_server_args
        mode = MisticaMode.SINGLE
    elif args.overlay_args:
        print("Error: Overlay parameters without overlay module. Please use -m")
        exit(1)
    elif args.wrapper_args:
        print("Error: Wrapper parameters without wrapper module. Please use -m")
        exit(1)
    else:
        mode = MisticaMode.MULTI

    s = MisticaServer(mode, args.key, args.verbose, moduleargs)
    s.run()
