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
from sotp.misticathread import ServerWrapper
from base64 import urlsafe_b64encode,urlsafe_b64decode
from dnslib import QTYPE, CLASS, RR
from dnslib import DNSHeader, DNSRecord
from dnslib import TXT, CNAME, MX, NS, SOA


def getServerDependency():
    return dnswrapper.SERVER_NAME

def getInstance(id, qsotp, args, logger):
    return dnswrapper(id, qsotp, args, logger)


class dnswrapper(ServerWrapper):
    SERVER_NAME = "dnsserver"

    def __init__(self, id, qsotp, args, logger):
        ServerWrapper.__init__(self, id, "dns", qsotp, dnswrapper.SERVER_NAME, logger)
        self.request = []
        # Module args
        self.domains = None
        self.ttl = None
        self.query = None
        # Base args
        self.max_size = None
        self.max_retries = None
        # Parsing args
        self.argparser = self.generateArgParse(self.name)
        self.parseArguments(args)
        # Logger parameters
        self.logger = logger
        self._LOGGING_ = False if logger is None else True

    def parseArguments(self, args):
        parsed = self.argparser.parse_args(args.split())
        self.domains = parsed.domains
        self.ttl = parsed.ttl[0]
        self.queries = parsed.queries
        self.max_size = parsed.max_size[0]
        self.max_retries = parsed.max_retries[0]

    def extractFromSubdomain(self, qname):
        reqhostname = qname.idna()[:-1]
        for hostname in self.domains:
            if reqhostname.endswith(f".{hostname}"):
                # urlsafe_b64decode ignore '.' characters, so its okey for decode packets in multiple mode
                self._LOGGING_ and self.logger.debug_all(f"[{self.name}] extractFromSubdomain() extract data from query: {reqhostname}")
                return urlsafe_b64decode(reqhostname.replace(f".{hostname}",""))
        else:
            self._LOGGING_ and self.logger.error(f"[{self.name}] Extracting SOTP from Subdomain and not in hostname list")
            return None

    def parseQuestion(self,request):
        if request.q.qtype is QTYPE.NS:
            self._LOGGING_ and self.logger.debug(f"[{self.name}] Received a dns question with qtype NS")
            return self.extractFromSubdomain(request.q.qname)
        elif request.q.qtype is QTYPE.CNAME:
            self._LOGGING_ and self.logger.debug(f"[{self.name}] Received a dns question with qtype CNAME")
            return self.extractFromSubdomain(request.q.qname)
        elif request.q.qtype is QTYPE.SOA:
            self._LOGGING_ and self.logger.debug(f"[{self.name}] Received a dns question with qtype SOA")
            return self.extractFromSubdomain(request.q.qname)
        elif request.q.qtype is QTYPE.MX:
            self._LOGGING_ and self.logger.debug(f"[{self.name}] Received a dns question with qtype MX")
            return self.extractFromSubdomain(request.q.qname)
        elif request.q.qtype is QTYPE.TXT:
            self._LOGGING_ and self.logger.debug(f"[{self.name}] Received a dns question with qtype TXT")
            return self.extractFromSubdomain(request.q.qname)
        else:
            # A, AAAA, PTR for future releases
            self._LOGGING_ and self.logger.error(f"[{self.name}] parseQuestion() recieved a dns with invalid question type: {request.q.qtype}")
            return None

    def inHostnameList(self, request):
        reqhostname = request.q.qname.idna()[:-1]
        for hostname in self.domains:
            if reqhostname == hostname or reqhostname.endswith(f".{hostname}"):
                return True
        self._LOGGING_ and self.logger.error(f"[{self.name}] received dns query to {reqhostname} which is not in the hostname list")
        return False

    def inQueryList(self,request):
        for q in self.queries:
            if getattr(QTYPE,q) is request.q.qtype:
                return True
        self._LOGGING_ and self.logger.error(f"[{self.name}] received dns query {request.q.qtype} which is not in the query list {self.queries}")
        return False

    def unwrap(self, content):
        if not self.inHostnameList(content):
            return None
        if not self.inQueryList(content):
            return None
        self.request.append(content)
        return self.parseQuestion(content)

    def getDomainFromRequest(self, reqhostname):
        for hostname in self.domains:
            if reqhostname.endswith(f".{hostname}"):
                return hostname
        raise f"Request Hostname not found in domain list: {reqhostname}"

    def createNsResponse(self, data, request):
        dataRawEnc = urlsafe_b64encode(data)
        dataEnc = str(dataRawEnc, "utf-8")
        self._LOGGING_ and self.logger.debug_all(f"[{self.name}] createNSResponse() with sotp_data: {dataEnc}")
        rdomain = self.getDomainFromRequest(request.q.qname.idna()[:-1])
        reply = DNSRecord(DNSHeader(id=request.header.id, qr=1, aa=1, ra=1), q=request.q)
        reply.add_answer(RR(rname=request.q.qname,
                            rtype=QTYPE.NS,
                            rclass=CLASS.IN,
                            ttl=self.ttl,
                            rdata=NS(f"{dataEnc}.{rdomain}")))
        return reply

    def createCnameResponse(self, data, request):
        dataRawEnc = urlsafe_b64encode(data)
        dataEnc = str(dataRawEnc, "utf-8")
        self._LOGGING_ and self.logger.debug_all(f"[{self.name}] createCnameResponse() with sotp_data: {dataEnc}")
        rdomain = self.getDomainFromRequest(request.q.qname.idna()[:-1])
        reply = DNSRecord(DNSHeader(id=request.header.id, qr=1, aa=1, ra=1), q=request.q)
        reply.add_answer(RR(rname=request.q.qname,
                            rtype=QTYPE.CNAME,
                            rclass=CLASS.IN,
                            ttl=self.ttl,
                            rdata=CNAME(f"{dataEnc}.{rdomain}")))
        return reply

    def createSoaResponse(self, data, request):
        dataRawEnc = urlsafe_b64encode(data)
        dataEnc = str(dataRawEnc, "utf-8")
        self._LOGGING_ and self.logger.debug_all(f"[{self.name}] createSoaResponse() with sotp_data: {dataEnc}")
        rdomain = self.getDomainFromRequest(request.q.qname.idna()[:-1])
        reply = DNSRecord(DNSHeader(id=request.header.id, qr=1, aa=1, ra=1), q=request.q)
        reply.add_answer(RR(rname=request.q.qname,
                            rtype=QTYPE.SOA,
                            rclass=CLASS.IN,
                            ttl=self.ttl,
                            rdata=SOA(f"{dataEnc}.{rdomain}")))
        return reply

    def createMxResponse(self, data, request):
        dataRawEnc = urlsafe_b64encode(data)
        dataEnc = str(dataRawEnc, "utf-8")
        self._LOGGING_ and self.logger.debug_all(f"[{self.name}] createMxResponse() with sotp_data: {dataEnc}")
        rdomain = self.getDomainFromRequest(request.q.qname.idna()[:-1])
        reply = DNSRecord(DNSHeader(id=request.header.id, qr=1, aa=1, ra=1), q=request.q)
        reply.add_answer(RR(rname=request.q.qname,
                            rtype=QTYPE.MX,
                            rclass=CLASS.IN,
                            ttl=self.ttl,
                            rdata=MX(f"{dataEnc}.{rdomain}")))
        return reply

    def createTxtResponse(self, data, request):
        # I embebed sopt data in one RR in TXT Response (but you can split sotp data in multiple RR)
        dataRawEnc = urlsafe_b64encode(data)
        dataEnc = str(dataRawEnc, "utf-8")
        self._LOGGING_ and self.logger.debug_all(f"[{self.name}] createTxtResponse() with sotp_data: {dataEnc}")
        reply = DNSRecord(DNSHeader(id=request.header.id, qr=1, aa=1, ra=1), q=request.q)
        reply.add_answer(RR(rname=request.q.qname,
                            rtype=QTYPE.TXT,
                            rclass=CLASS.IN,
                            ttl=self.ttl,
                            rdata=TXT(dataEnc)))
        return reply

    def generateResponse(self, data, request):
        if request.q.qtype is QTYPE.NS:
            return self.createNsResponse(data, request)
        elif request.q.qtype is QTYPE.CNAME:
            return self.createCnameResponse(data, request)
        elif request.q.qtype is QTYPE.SOA:
            return self.createSoaResponse(data, request)
        elif request.q.qtype is QTYPE.MX:
            return self.createMxResponse(data, request)
        elif request.q.qtype is QTYPE.TXT:
            return self.createTxtResponse(data, request)
        else:
            # A, AAAA, PTR for future releases
            self._LOGGING_ and self.logger.error(f"[{self.name}] generateResponse() invalid request qtype: {request.q.qtype}")
            return None

    def wrap(self, content):
        request = self.request.pop(0)
        reply = self.generateResponse(content,request)
        return reply
