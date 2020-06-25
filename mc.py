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

from argparse import ArgumentParser
from threading import Thread, Semaphore
from queue import Queue, Empty
from importlib import import_module
from sotp.clientworker import ClientWorker
from utils.messaging import Message, SignalType, MessageType
from utils.logger import Log
from time import sleep
from sys import exit, stdin
from platform import system
from signal import signal, SIGINT
from utils.prompt import Prompt
if system() != "Windows":
    from select import poll, POLLIN
from sotp.misticathread import ClientOverlay, ClientWrapper
from wrapper.client import *
from overlay.client import *

class MisticaClient(object):

    def __init__(self, key, args, verbose):
        self.name = type(self).__name__
        self.wrapper = None
        self.overlay = None
        self.qsotp = Queue()
        self.qdata = Queue()
        self.sem = Semaphore(1)
        self.sotp_sem = Semaphore(1)
        self.released = False
        # Overlay and Wrapper args
        self.overlayname = args["overlay"]
        self.wrappername = args["wrapper"]
        self.overlayargs = args["overlay_args"]
        self.wrapperargs = args["wrapper_args"]
        # Mistica Client args
        self.key = key
        # Arguments depended of overlay used
        self.tag = None
        # Arguments depended of wrapper used
        self.max_size = None
        self.poll_delay = None
        self.response_timeout = None
        self.max_retries = None
        # Logger parameters
        self.logger = Log('_client', verbose) if verbose > 0 else None
        self._LOGGING_ = False if self.logger is None else True


    def doWrapper(self):
        self.sem.acquire()
        self._LOGGING_ and self.logger.info(f"[Wrapper] Initializing...")
        self.wrapper = [x for x in ClientWrapper.__subclasses__() if x.NAME == self.wrappername][0](self.qsotp, self.wrapperargs, self.logger)
        self.wrapper.start()
        # setting sotp arguments depending on the wrapper to be used
        self.max_size = self.wrapper.max_size
        self.response_timeout = self.wrapper.response_timeout
        self.poll_delay = self.wrapper.poll_delay
        self.max_retries = self.wrapper.max_retries
        self.sem.release()


    def doSotp(self):
        try:
            self.sem.acquire()
            self._LOGGING_ and self.logger.info(f"[{self.name}] Initializing...")
            self.sem.release()
            self.sotp_sem.acquire()
            i = 1
            s = ClientWorker(self.key,
                        self.max_retries,
                        self.max_size,
                        self.tag,
                        self.overlayname,
                        self.wrappername,
                        self.qdata,
                        self.logger)
            dataThread = Thread(target=s.dataEntry, args=(self.qsotp,))
            dataThread.start()
            while not s.exit:
                answers = []
                self._LOGGING_ and self.logger.debug(f"[{self.name}] Iteration nº{i} Status: {s.st} Seq: {s.seqnumber}/65535")

                if s.wait_reply:
                    timeout = self.response_timeout
                else:
                    timeout = self.poll_delay
                try:
                    dataEntry = self.qsotp.get(True,timeout)
                    answers = s.Entrypoint(dataEntry)
                except Empty:
                    if s.wait_reply:
                        answers = s.lookForRetries()
                    else:
                        answers = s.getPollRequest()

                for answer in answers:
                    self._LOGGING_ and self.logger.debug(f"[{self.name}] Header Sent: {answer.printHeader()}")
                    if answer.receiver == self.wrapper.name:
                        self._LOGGING_ and self.logger.debug_all(f"[{self.name}] Retries {s.retries}/{self.max_retries}")
                        self.wrapper.inbox.put(answer)
                    elif answer.receiver == self.overlay.name:
                        self.overlay.inbox.put(answer)
                    else:
                        raise Exception(f"Invalid answer to {answer.receiver} in client loop")

                if self.released == False and s.sotp_first_push:
                    self._LOGGING_ and self.logger.debug(f"[{self.name}] Initialized! Unblocked sem")
                    self.sotp_sem.release()
                    self.released = True
                i += 1
            pass
            dataThread.join()
            self._LOGGING_ and self.logger.info(f"[DataThread] Terminated")
            self._LOGGING_ and self.logger.info(f"[{s.name}] Terminated")
        except Exception as e:
            print(e)
            self._LOGGING_ and self.logger.exception(f"[ClientWorker] Exception in doSotp: {e}")
            self.overlay.inbox.put(Message("clientworker", 0, self.overlayname, 0, MessageType.SIGNAL, SignalType.TERMINATE))
            self.wrapper.inbox.put(Message("clientworker", 0, self.wrappername, 0, MessageType.SIGNAL, SignalType.TERMINATE))


    def doOverlay(self):
        self.sem.acquire()
        self._LOGGING_ and self.logger.info(f"[Overlay] Initializing...")
        self.overlay = [x for x in ClientOverlay.__subclasses__() if x.NAME == self.overlayname][0](self.qsotp, self.qdata, self.overlayargs, self.logger)
        self.overlay.start()
        # setting sotp arguments depending on the overlay to be used
        self.tag = self.overlay.tag
        self.sem.release()


    def captureInput(self):
        self.sem.acquire()
        self._LOGGING_ and self.logger.info(f"[Input] Initializing...")
        self.sem.release()
        if system() != 'Windows':
            polling = poll()
        while True:
            if self.overlay.exit:
                break
            try:
                if system() == 'Windows':
                    # Ugly loop for windows
                    rawdata = stdin.buffer.raw.read(300000)
                    sleep(0.1)
                else:
                    # Nice loop for unix
                    polling.register(stdin.buffer.raw.fileno(), POLLIN)
                    polling.poll()

                    rawdata = stdin.buffer.raw.read(300000)
                    if rawdata == b'':  # assume EOF
                        self.sotp_sem.acquire()
                        self._LOGGING_ and self.logger.debug(f"[Input] SOTP initialized, sending terminate because input recv EOF")
                        self.overlay.inbox.put(Message("input", 0, self.overlayname, 0, MessageType.SIGNAL, SignalType.TERMINATE))
                        self.sotp_sem.release()
                        break

                if rawdata and len(rawdata) > 0 and self.overlay.hasInput:
                    self.overlay.inbox.put(Message("input", 0, self.overlayname, 0, MessageType.STREAM, rawdata))
            except KeyboardInterrupt:
                self._LOGGING_ and self.logger.debug("[Input] CTRL+C detected. Passing to wrapper")
                self.overlay.inbox.put(Message("input", 0, self.overlayname, 0, MessageType.SIGNAL, SignalType.TERMINATE))
                break
        self._LOGGING_ and self.logger.info(f"[Input] Terminated")
        return


    def captureExit(self, signal_received, frame):
        self._LOGGING_ and self.logger.debug("[Input] CTRL+C detected. Passing to overlay")
        self.overlay.inbox.put(Message("input", 0, self.overlayname, 0, MessageType.SIGNAL, SignalType.TERMINATE))


    def run(self):
        try:
            self.doWrapper()
            self.doOverlay()
            sotpThread = Thread(target=self.doSotp)
            sotpThread.start()
            if self.overlay.hasInput:
                self.captureInput()
            else:
                signal(SIGINT, self.captureExit)
            # Crappy loop for windows
            if system() == 'Windows':
                while not self.overlay.exit:
                    sleep(0.5)
            # Nice sync primitive for unix
            else:
                sotpThread.join()
        except Exception as e:
            self._LOGGING_ and self.logger.exception(f"Exception at run(): {e}")
        finally:
            self._LOGGING_ and self.logger.debug(f"[{self.name}] Terminated")


if __name__ == '__main__':
    parser = ArgumentParser(description=f"Mistica client.")

    # Sotp Client arguments.
    parser.add_argument('-k', "--key", action='store', default="",required=False, help="RC4 key used to encrypt the comunications")
    parser.add_argument("-l", "--list", action='store', required=False, help="Lists modules or parameters. Options are: all, overlays, wrappers, <overlay name>, <wrapper name>")
    # Wrapper and Overlay arguments.
    parser.add_argument("-m", "--modules", action='store', required=False, help="Module pair. Format: 'overlay:wrapper'")
    parser.add_argument("-w", "--wrapper-args", action='store', required=False, default='', help="args for the selected overlay module")
    parser.add_argument("-o", "--overlay-args", action='store', required=False, default='', help="args for the selected wrapper module")
    parser.add_argument('-v', '--verbose', action='count', default=0, help="Level of verbosity in logger (no -v None, -v Low, -vv Medium, -vvv High)")
    args = parser.parse_args()
    moduleargs = {}

    if args.list:
        # list and quit
        if args.list == "all" or args.list == "overlays" or args.list == "wrappers":
            print(Prompt.listModules("client", args.list))
        else:
            Prompt.listParameters("client", args.list)
        exit(0)
    elif args.modules:
        if args.key == "":
            print("You must suply a key for RC4 encryption. Use -k or --key")
            exit(1)
        moduleargs["overlay"] = args.modules.partition(":")[0]
        moduleargs["wrapper"] = args.modules.partition(":")[2]
        if Prompt.findModule("client", moduleargs["overlay"]) is None:
            print(f"Invalid overlay module {moduleargs['overlay']}. Please specify a valid module.")
            exit(1)
        if Prompt.findModule("client", moduleargs["wrapper"]) is None:
            print(f"Invalid wrap module {moduleargs['wrapper']}. Please specify a valid module.")
            exit(1)
        moduleargs["overlay_args"] = args.overlay_args
        moduleargs["wrapper_args"] = args.wrapper_args
    elif args.overlay_args:
        print("Error: Overlay parameters without overlay module. Please use -m")
        exit(1)
    elif args.wrapper_args:
        print("Error: Wrapper parameters without wrapper module. Please use -m")
        exit(1)
    else:
        parser.print_help()
        exit(0)

    c = MisticaClient(args.key,moduleargs,args.verbose)
    c.run()
