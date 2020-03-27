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
from os import walk, path
from json import load, loads
from argparse import ArgumentParser


class Prompt(object):
    def __init__(self):
        self.banner = "[Mistica] >>> "

    def GetFromStdin(self):
        data = input(self.banner)
        return data

    @staticmethod
    def getDescription(filename):
        with open(filename, "r") as fd:
            return loads(fd.read())["description"]

    @staticmethod
    def getName(filename):
        with open(filename, "r") as fd:
            return loads(fd.read())["prog"]

    @staticmethod
    def getArgs(filename):
        with open(filename, "r") as fd:
            return loads(fd.read())["args"]

    @staticmethod
    def getWrapServer(filename):
        with open(filename, "r") as fd:
            return loads(fd.read())["wrapserver"]

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
        overlaydict = {}
        for dirname, _, filenames in walk(f'overlay/{type}'):
            for filename in filenames:
                if filename == "config.json":
                    name = Prompt.getName(path.join(dirname, filename))
                    overlaydict[name] = Prompt.getDescription(path.join(dirname, filename))
        output = "\nOverlay modules:\n\n"
        for k in sorted(overlaydict):
            output = output + "- {}: {}\n".format(k, overlaydict[k])
        return output

    @staticmethod
    def listWrapModules(type):
        wmdict = {}
        p = (type if type == "client" else "server/wrap_module")
        for dirname, _, filenames in walk(f'wrapper/{p}'):
            for filename in filenames:
                if filename == "config.json":
                    name = Prompt.getName(path.join(dirname, filename))
                    wmdict[name] = Prompt.getDescription(path.join(dirname, filename))
        output = "\nWrap modules:\n\n"
        for k in sorted(wmdict):
            output = output + "- {}: {}\n".format(k, wmdict[k])
        return output

    @staticmethod
    def listParameteres(type, lst):
        module = Prompt.findModule(type, lst)
        if not module:
            return f"Module {lst} does not exist"
        argparser = Prompt.generateArgParser(module)
        try:
            argparser.parse_args(["-h"])
        except SystemExit:
            pass
        try:
            wsname = Prompt.getWrapServer(module)
        except Exception:
            wsname = None
        if wsname:
            print(f"\n{lst} uses {wsname} as wrap server\n")
            ws = Prompt.findWrapServer(wsname)
            argparser = Prompt.generateArgParser(ws)
            try:
                argparser.parse_args(["-h"])
            except SystemExit:
                pass

    @staticmethod
    def findModule(type, lst):
        for dirname, _, filenames in walk(f'overlay/{type}'):
            for filename in filenames:
                if filename == "config.json":
                    name = Prompt.getName(path.join(dirname, filename))
                    if name == lst:
                        return path.join(dirname, filename)
        p = (type if type == "client" else "server/wrap_module")
        for dirname, _, filenames in walk(f'wrapper/{p}'):
            for filename in filenames:
                if filename == "config.json":
                    name = Prompt.getName(path.join(dirname, filename))
                    if name == lst:
                        return path.join(dirname, filename)
        return None

    @staticmethod
    def findWrapServer(lst):
        for dirname, _, filenames in walk('wrapper/server/wrap_server'):
            for filename in filenames:
                if filename == "config.json":
                    name = Prompt.getName(path.join(dirname, filename))
                    if name == lst:
                        return path.join(dirname, filename)

    @staticmethod
    def generateArgParser(filepath):
        with open(filepath, 'r') as f:
            config = load(f)

        parser = ArgumentParser(prog=config["prog"], description=config["description"])
        for arg in config["args"]:
            for name, field in arg.items():
                opts = {}
                for key,value in field.items():
                    if key == "type":
                        value = Prompt.getType(value)
                    opts[key] = value
                parser.add_argument(name, **opts)
        return parser

    # For the arg parsers (we can't set "int" on json file because syntax)
    @staticmethod
    def getType(value):
        if value == "int":
            return int
        elif value == "float":
            return float
        elif value == "str":
            return str
