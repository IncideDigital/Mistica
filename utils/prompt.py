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

from sotp.misticathread import ClientOverlay, ClientWrapper, ServerOverlay, ServerWrapper
from overlay.client import *
from overlay.server import *
#from wrapper.server.wrap_module import *
from wrapper.client import *
from argparse import ArgumentParser


class Prompt(object):
    def __init__(self):
        self.banner = "[Mistica] >>> "

    def GetFromStdin(self):
        data = input(self.banner)
        return data

    @staticmethod
    def listModules(type, lst):
        if lst == "overlays":
            output = Prompt.listOverlays(type)
        elif lst == "wrappers":
            output = Prompt.listWrapModules(type)
        else:
            output = Prompt.listOverlays(type)
            output = output + Prompt.listWrapModules(type)
        return output

    @staticmethod
    def listOverlays(type):
        if type == "server":
            overlaylist = [x for x in ServerOverlay.__subclasses__()]
        else:
            overlaylist = [x for x in ClientOverlay.__subclasses__()]
        overlaydict = {}
        for elem in overlaylist:
            overlaydict[elem.NAME] = elem.CONFIG["description"]
        output = "\nOverlay modules:\n\n"
        for k in sorted(overlaydict):
            output = output + "- {}: {}\n".format(k, overlaydict[k])
        return output


    @staticmethod
    def listWrapModules(type):
        if type == "server":
            overlaylist = [x for x in ServerWrapper.__subclasses__()]
        else:
            overlaylist = [x for x in ClientWrapper.__subclasses__()]
        wmdict = {}
        for elem in overlaylist:
            wmdict[elem.NAME] = elem.CONFIG["description"]
        output = "\nWrap modules:\n\n"
        for k in sorted(wmdict):
            output = output + "- {}: {}\n".format(k, wmdict[k])
        return output

    @staticmethod
    def listParameters(type, lst):
        module = Prompt.findModule(type, lst)
        if not module:
            return f"Module {lst} does not exist"
        argparser = Prompt.generateArgParser(module)
        try:
            argparser.parse_args(["-h"])
        except SystemExit:
            pass
        try:
            ws = module.SERVER_CLASS
        except Exception:
            ws = None
        if ws:
            print(f"\n{lst} uses {ws.NAME} as wrap server\n")
            argparser = Prompt.generateArgParser(ws)
            try:
                argparser.parse_args(["-h"])
            except SystemExit:
                pass

    @staticmethod
    def findModule(type, lst):
        if type == "server":
            for x in ServerWrapper.__subclasses__():
                if x.NAME == lst:
                    return x
            for x in ServerOverlay.__subclasses__():
                if x.NAME == lst:
                    return x
        for x in ClientWrapper.__subclasses__():
                if x.NAME == lst:
                    return x
        for x in ClientOverlay.__subclasses__():
            if x.NAME == lst:
                return x
        return None
    
    @staticmethod
    def generateArgParser(module):
        config = module.CONFIG

        parser = ArgumentParser(prog=config["prog"],description=config["description"])
        for arg in config["args"]:
            for name,field in arg.items():
                opts = {}
                for key,value in field.items():
                    opts[key] = value
                parser.add_argument(name, **opts)
        return parser
