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
from threading import Thread
from queue import Queue
from utils.messaging import Message, MessageType, SignalType
from json import load
from argparse import ArgumentParser
from utils.prompt import Prompt


class MisticaMode:
    SINGLE = 0
    MULTI = 1


class MisticaThread(Thread):
    def __init__(self, name, logger):
        Thread.__init__(self)
        self.name = name
        self.inbox = Queue()
        self.exit = False
        # Logger parameters
        self.logger = logger
        self._LOGGING_ = False if logger is None else True

    def handleMessage(self, msg):
        answer = None
        if (msg.isSignalMessage()):
            answer = self.handleSignal(msg)
        elif (msg.isStreamMessage()):
            answer = self.handleStream(msg)
        else:
            raise Exception('Invalid Message')
        return answer

    # OVERRIDE ME
    def handleSignal(self, msg):
        pass

    # OVERRIDE ME
    def handleStream(self, msg):
        pass

    # OVERRIDE ME
    def processAnswer(self, msg):
        pass

    def run(self):
        while True:
            try:
                message = self.inbox.get()
                answer = self.handleMessage(message)  # Answer can be None
                self.processAnswer(answer)
                if self.exit:
                    self._LOGGING_ and self.logger.debug(f"[{self.name}] MisticaThread detect Exit Flag.")
                    break
            except Exception as e:
                self._LOGGING_ and self.logger.exception(f"[{self.name}] MisticaThread Exception: {e}")
        self._LOGGING_ and self.logger.debug(f"[{self.name}] Terminated")


class ClientOverlay(MisticaThread):

    def __init__(self, name, qsotp, qdata, args, logger):
        MisticaThread.__init__(self, name, logger)
        self.qsotp = qsotp
        self.qdata = qdata
        self.hasInput = False
        # Generate argparse and parse args
        self.argparser = self.generateArgParse(name)
        self.args = self.argparser.parse_args(args.split())
        self.parseArguments(self.args)
        # Get tag, by default, from args
        self.tag = self.args.tag[0]
        # Logger parameters
        self.logger = logger
        self._LOGGING_ = False if logger is None else True
        self.initCommunication()

    # OVERRIDE ME
    def parseArguments(self, args):
        pass

    # First of all, Overlay send a Signal Start Msg to Sotp.
    def initCommunication(self):
        m = Message(self.name, 0, "clientworker", 0, MessageType.SIGNAL, SignalType.START)
        self.qsotp.put(m)

    def handleSignal(self, msg):
        if msg.isTerminateMessage() or msg.isCommunicationEndedMessage() or msg.isCommunicationBrokenMessage():
            self.exit = True
            self.qsotp.put(Message(self.name, 0, "clientworker", 0, MessageType.SIGNAL, SignalType.TERMINATE))
        pass

    def handleStream(self, msg):
        answer = None
        if (msg.sender == "input"):
            answer = self.handleInputStream(msg)
        elif (msg.sender == "clientworker"):
            answer = self.handleSOTPStream(msg)
        return answer

    def handleInputStream(self, msg):
        content = self.processInputStream(msg.content)
        if content is None:
            return None
        return Message(self.name, 0, "datathread", 0, MessageType.STREAM, content)

    def handleSOTPStream(self, msg):
        content = self.processSOTPStream(msg.content)
        if content is None:
            return None
        return Message(self.name, 0, "datathread", 0, MessageType.STREAM, content)

    # Route answer to sotp or datathread queue.
    def processAnswer(self, answer):
        if answer is not None:
            if answer.receiver == "clientworker":
                self.qsotp.put(answer)
            elif answer.receiver == "datathread":
                self.qdata.put(answer)
        pass

    def generateArgParse(self, name):
        filepath = f"./overlay/client/{name}/config.json"
        config = ""
        with open(filepath, 'r') as f:
            config = load(f)

        parser = ArgumentParser(prog=config["prog"],description=config["description"])
        for arg in config["args"]:
            for name,field in arg.items():
                opts = {}
                for key,value in field.items():
                    if key == "type":
                        value = Prompt.getType(value)
                    opts[key] = value
                parser.add_argument(name, **opts)
        return parser

    # OVERRIDE ME
    def processInputStream(self, content):
        pass

    # OVERRIDE ME
    def processSOTPStream(self, content):
        pass


class ClientWrapper(MisticaThread):

    def __init__(self, name, qsotp, logger):
        MisticaThread.__init__(self,name, logger)
        self.qsotp = qsotp
        self.exit = False
        # Logger parameters
        self.logger = logger
        self._LOGGING_ = False if logger is None else True

    def handleSignal(self, msg):
        if msg.isTerminateMessage():
            self.exit = True
        pass

    def handleStream(self, msg):
        try:
            if (msg.sender == self.name):
                return self.unwrap(msg.content)
            elif (msg.sender == "clientworker"):
                self.wrap(msg.content)
        except Exception as e:
            m = Message(self.name,0,"clientworker",0,MessageType.SIGNAL,SignalType.COMMS_BROKEN)
            self._LOGGING_ and self.logger.exception(f"[{self.name}] Exception at handleStream: {e}")
            self.qsotp.put(m)

    # Route answer to sotp queue.
    def processAnswer(self, answer):
        if answer is not None:
            m = self.messageToSOTP(answer)
            self.qsotp.put(m)

    def messageToSOTP(self, content):
        return Message(self.name, 0, "clientworker", 0, MessageType.STREAM, content)

    def messageToWrapper(self, content):
        return Message(self.name, 0, "wrapper", 0, MessageType.STREAM, content)

    def generateArgParse(self, name):
        filepath = f"./wrapper/client/{name}/config.json"
        config = ""
        with open(filepath, 'r') as f:
            config = load(f)

        parser = ArgumentParser(prog=config["prog"],description=config["description"])
        for arg in config["args"]:
            for name,field in arg.items():
                opts = {}
                for key,value in field.items():
                    if key == "type":
                        value = Prompt.getType(value)
                    opts[key] = value
                parser.add_argument(name, **opts)
        return parser

    # OVERRIDE ME
    def wrap(self, content):
        pass

    # OVERRIDE ME
    def unwrap(self, content):
        pass


class ServerOverlay(MisticaThread):

    def __init__(self, name, id, qsotp, mode, args, logger):
        MisticaThread.__init__(self, name, logger)
        self.workers = []
        self.id = id
        self.qsotp = qsotp
        self.mode = mode
        # Generate argparse and parse args
        self.argparser = self.generateArgParse(name)
        self.args = self.argparser.parse_args(args.split())
        self.parseArguments(self.args)
        # Get tag
        self.tag = self.args.tag[0]
        # Logger parameters
        self.logger = logger
        self._LOGGING_ = False if logger is None else True

    # override me!
    def parseArguments(self, args):
        pass

    def handleSignal(self, msg):
        answer = None
        if (msg.sender == "input"):
            answer = self.handleInputSignal(msg)
        elif (msg.sender == "serverworker" or msg.sender == "router"):
            answer = self.handleSOTPSignal(msg)
        return answer

    def handleInputSignal(self, msg):

        if msg.isTerminateMessage():
            if self.mode == MisticaMode.SINGLE:
                return Message(self.name, self.id, "router", 0,
                               MessageType.SIGNAL, SignalType.TERMINATE)
            else:
                return self.handleInterrupt()

    # override this function to alter the behavior on multihandler mode
    def handleInterrupt(self):
        print("Interrupt ignored.")
        return None

    def handleSOTPSignal(self, msg):
        answer = None
        if msg.isTerminateMessage():
            self.exit = True
        elif msg.isCommsFinishedMessage() or msg.isCommsBrokenMessage():
            if self.mode == MisticaMode.SINGLE:
                answer = Message(self.name, self.id, "router", 0,
                                 MessageType.SIGNAL, SignalType.TERMINATE)
            else:
                self.removeWorker(msg.sender_id)  # crashed worker
        return answer

    def handleStream(self, msg):
        answer = None
        if (msg.sender == "input"):
            answer = self.handleInputStream(msg)
        elif (msg.sender == "serverworker"):
            answer = self.handleSOTPStream(msg)
        return answer

    def handleInputStream(self, msg):
        content = self.processInputStream(msg.content)
        # By default, only one worker. Must be overriden for more
        # In a multi-worker scenario inputs must be mapped to workers
        return self.streamToSOTPWorker(content, self.workers[0].id)

    def handleSOTPStream(self, msg):
        for worker in self.workers:
            if msg.sender_id == worker.id:
                break
        else:
            return None
        content = self.processSOTPStream(msg.content)
        if content is None:
            return None
        return self.streamToSOTPWorker(content, msg.sender_id)

    def processAnswer(self, answer):
        if answer is None:
            return
        elif answer.receiver == "serverworker":
            for worker in self.workers:
                if answer.receiver_id == worker.id:
                    worker.inbox.put(answer)
                    return
        elif answer.receiver == "datathread":
            for worker in self.workers:
                if answer.receiver_id == worker.id:
                    worker.datainbox.put(answer)
                    return
        elif answer.receiver == "router":
            self.qsotp.put(answer)

    def generateArgParse(self, name):
        filepath = f"./overlay/server/{name}/config.json"
        config = ""
        with open(filepath, 'r') as f:
            config = load(f)

        parser = ArgumentParser(prog=config["prog"],description=config["description"])
        for arg in config["args"]:
            for name,field in arg.items():
                opts = {}
                for key,value in field.items():
                    if key == "type":
                        value = Prompt.getType(value)
                    opts[key] = value
                parser.add_argument(name, **opts)
        return parser

    # override me
    def processInputStream(self, content):
        pass

    # override me
    def processSOTPStream(self, content):
        pass

    def addWorker(self, worker):
        # By default only one worker can be added.
        # For multi-worker scenarios (e.g. RAT console), this method must be overrriden
        if not self.workers:  # empty
            self.workers.append(worker)
        else:
            raise(f"Cannot Register worker on overlay module. Module {self.name} only accepts one worker")

    def removeWorker(self, id):
        for worker in self.workers:
            if id == worker.id:
                self.workers.remove(id)
                break

    def streamToSOTPWorker(self, content, workerid):
        return Message(self.name, self.id, "datathread", workerid, MessageType.STREAM, content)

    def signalToSOTPWorker(self, content, workerid):
        return Message(self.name, self.id, "serverworker", workerid, MessageType.SIGNAL, content)


class ServerWrapper(MisticaThread):

    def __init__(self, id, name, qsotp, servername, logger):
        MisticaThread.__init__(self, name, logger)
        self.id = id
        self.servername = servername
        self.qsotp = qsotp
        # Logger parameters
        self.logger = logger
        self._LOGGING_ = False if logger is None else True

    def handleSignal(self, msg):
        answer = None
        if (msg.sender == self.servername):
            answer = self.handleServerSignal(msg)
        elif (msg.sender == "router"):
            answer = self.handleSOTPSignal(msg)
        return answer

    def handleSOTPSignal(self, msg):
        if msg.isTerminateMessage():
            self.exit = True
        return None

    def handleServerSignal(self, msg):
        # TODO
        pass

    def handleStream(self, msg):
        answer = None
        if (msg.sender == self.servername):
            answer = self.messageToRouter(self.unwrap(msg.content), msg.wrapServerQ)
        elif (msg.sender == "serverworker" or msg.sender == "router"):
            answer = self.messageToWrapServer(self.wrap(msg.content), msg.wrapServerQ)
        return answer

    # OVERRIDE ME
    def wrap(self, content):
        pass

    # OVERRIDE ME
    def unwrap(self, content):
        pass

    def processAnswer(self, answer):
        if answer is None:
            return
        if answer.receiver == "router":
            self.qsotp.put(answer)
        else:  # For a wrap server
            answer.wrapServerQ.put(answer)

    def messageToRouter(self, content, wrapServerQ):
        if content is None:
            return None
        else:
            return Message(self.name, self.id, "router", 0, MessageType.STREAM, content, wrapServerQ)

    def messageToWrapServer(self, content, wrapServerQ):
        if content is None:
            return None
        else:
            return Message(self.name, self.id, self.servername, 0, MessageType.STREAM, content, wrapServerQ)

    def generateArgParse(self, name):
        filepath = f"./wrapper/server/wrap_module/{name}/config.json"
        config = ""
        with open(filepath, 'r') as f:
            config = load(f)

        parser = ArgumentParser(prog=config["prog"], description=config["description"])
        for arg in config["args"]:
            for name, field in arg.items():
                opts = {}
                for key, value in field.items():
                    if key == "type":
                        value = Prompt.getType(value)
                    opts[key] = value
                parser.add_argument(name, **opts)
        return parser
