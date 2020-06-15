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
from sotp.misticathread import ClientWrapper
from socket import socket,timeout,AF_INET,SOCK_DGRAM
from struct import pack,unpack_from
from os import getpid,path
from collections import namedtuple
from base64 import urlsafe_b64encode,urlsafe_b64decode
from sotp.core import BYTE,Header,OptionalHeader,Sizes

def getInstance(qsotp, args, logger):
    return dns(qsotp, args, logger)


class QTYPE(object):
    A = 1
    AAAA = 28 
    CNAME = 5 
    MX = 15 
    NS = 2 
    PTR = 12 
    SOA = 6 
    TXT = 16 

class SimpleDnsClient(object):
    """
    This is an adaptation of the project:
    https://github.com/vlasebian/simple-dns-client
    """

    ### Tuples for message parts
    Header = namedtuple("Header", [
        'x_id',
        'qr',
        'opcode',
        'aa',
        'tc',
        'rd',
        'ra',
        'z',
        'rcode',
        'qdcount',
        'ancount',
        'nscount',
        'arcount',
        ])

    Question = namedtuple("Question", [
        'qname',
        'qtype',
        'qclass',
        ])

    Answer = namedtuple("Answer", [
        'name',
        'x_type',
        'x_class',
        'ttl',
        'rdlength',
        'rdata',
        ])

    Reply = namedtuple("Reply", [
        'header',
        'question',
        'answer',
        ])

    # Opcodes
    QUERY = 0
    IQUERY = 1
    STATUS = 2

    def __init__(self, servers, port, domain, query_timeout, name, logger):
        self.servers = servers
        self.port = port
        self.domain = domain
        self.name = name
        self.query_timeout = query_timeout
        # Logger parameters
        self.logger = logger
        self._LOGGING_ = False if logger is None else True

    def create_header(self, opcode):
        """ Function used to create a DNS query header.
        
        Args:
            opcode = opcode of the query. It can take the following values:
                QUERY = 0, IQUERY = 1, STATUS = 2

        Returns:
            The header

        """
        header = b''
        flags = b''

        # Message ID
        header += pack(">H", getpid())

        # Flags (QR, opcode, AA, TC, RD, RA, Z, RCODE)
        if opcode == self.QUERY:
            # Standard DNS query
            flags = 0b0000000100000000
        elif opcode == self.IQUERY:
            flags = 0b0000100100000000
        elif opcode == self.STATUS:
            flags = 0b0001000100000000

        header += pack(">H", flags)

        # QDCOUNT
        header += pack(">H", 1)
        # ANCOUNT
        header += pack(">H", 0)
        # NSCOUNT
        header += pack(">H", 0)
        # ARCOUNT
        header += pack(">H", 0)

        return header

    def create_qname(self, domain_name):
        """ Function used to transfrom URL from normal form to DNS form.

        Args:
            domain_name = URL that needs to be converted

        Returns:
            The URL in DNS form

        Example:
            3www7example3com0 to www.example.com

        """
        qname = b''

        split_name = domain_name.split(".")
        for atom in split_name:
            qname += pack(">B", len(atom))
            qname += bytes(atom, 'utf-8')
        qname += b'\x00'
        self._LOGGING_ and self.logger.debug_all(f"[{self.name}] create_qname() url to dns form qname: {qname}")

        return qname

    def get_dns_query(self, domain_name, query_type):
        """ Function used to create a DNS query question section.
        
        Args:
            domain_name = the domain name that needs to be resolved
            query_type = the query type of the DNS message

        Returns:
            The DNS query question section and the length of the qname in a tuple
            form: (question, qname_len)

        """
        # QNAME
        qname = self.create_qname(domain_name)
        self._LOGGING_ and self.logger.debug_all(f"[{self.name}] get_dns_query() query_type for request: {query_type}")

        code = 0
        # QTYPE - query for A record
        if query_type == "A":
            # host address
            code = 1
        elif query_type == "NS":
            # authoritative name server
            code = 2
        elif query_type == "CNAME":
            # the canonical name for an alias
            code = 5
        elif query_type == "SOA":
            # start of a zone of authority
            code = 6
        elif query_type == "MX":
            # mail exchange
            code = 15
        elif query_type == "TXT":
            # text strings
            code = 16
        #elif query_type == "PTR":
        #    # domain name pointer
        #    code = 12
        #    print("[Error]: Not implemented. Exiting...")
        #    exit(1)
        elif query_type == "AAAA":
            # AAAA record
            code = 28
        else:
            raise f"Invalid query type {query_type}"

        qtype = pack(">H", code)

        # QCLASS - internet
        qclass = pack(">H", 1)

        # whole question section
        question = self.create_header(self.QUERY) + qname + qtype + qclass

        return (question, len(qname))

    def query_dns_server(self, packet):
        """ Function used to create a UDP socket, to send the DNS query to the server
            and to receive the DNS reply.

        Args:
            packet = the DNS query message
        
        Returns:
            The reply of the server

        If none of the servers in the dns_servers.conf sends a reply, the program
        exits showing an error message.

        """
        sock = socket(AF_INET, SOCK_DGRAM)
        sock.settimeout(self.query_timeout)

        for server_ip in self.servers:
            got_response = False

            try:
                sock.sendto(packet, (server_ip, self.port))
                recv = sock.recvfrom(1024)
                if recv:
                    got_response = True
                    self._LOGGING_ and self.logger.debug_all(f"[{self.name}] query_dns_server() response from dns server {server_ip}:{self.port}")
                    break
            except (timeout,Exception):
                self._LOGGING_ and self.logger.debug_all(f"[{self.name}] query_dns_server() timeout expired for dns server {server_ip}:{self.port}")
                continue

        if not got_response:
            self._LOGGING_ and self.logger.debug_all(f"[{self.name}] query_dns_server() any response received from dns server list")
            raise "No response recieved from any servers"

        return recv[0]

    def extract_header(self, msg):
        """ Function used to extract the header from the DNS reply message.
            
        Args:
            msg: The message recieved from the DNS server

        Returns:
            The header of the reply as a Header namedtuple in the following
            form: Header(x_id, qr, opcode, aa, tc, rd, ra, z, rcode, qdcount, 
            ancount, nscount, arcount)

        """
        raw_header = unpack_from(">HHHHHH", msg, 0)

        x_id = raw_header[0]
        flags = raw_header[1]

        qr = flags >> 15
        opcode = (flags & 0x7800) >> 11
        aa = (flags & 0x0400) >> 10
        tc = (flags & 0x0200) >> 9
        rd = (flags & 0x0100) >> 8
        ra = (flags & 0x0080) >> 7
        z = (flags & 0x0070) >> 4
        rcode = (flags & 0x000f)

        qdcount = raw_header[2]
        ancount = raw_header[3]
        nscount = raw_header[4]
        arcount = raw_header[5]

        return self.Header(x_id, qr, opcode, aa, tc, rd, ra, z, rcode, qdcount, ancount, nscount, arcount)

    def convert_to_name(self, raw_name):
        """ Function used to convert an url from dns form to normal form.

        Args:
            The dns form of the url

        Returns:
            The normal form of the url

        Example: 
            3www7example3com0 to www.example.com

        """
        # might not work as expected in some cases - todo
        name = ''
        for byte in raw_name:
            if byte < 30:
                name += '.'
            else:
                name += chr(int(byte))

        name = name[1:-1]

        return name
    
    def extract_question(self, msg, qname_len):
        """ Function used to extract the question section from a DNS reply.
            
        Args:
            msg: The message recieved from the DNS server
            qname_len: The length of the name beign querried

        Returns:
            The question section of the reply as a Question namedtuple in the 
            following form: Question(qname, qtype, qclass)

        """
        # 12 is len(header_section)
        offset = 12

        # qname
        raw_qname = []
        for i in range(0, qname_len):
            byte = unpack_from(">B", msg, offset + i)[0]
            raw_qname.append(byte)

        qname = self.convert_to_name(raw_qname)
        qtype = unpack_from(">H", msg, offset + qname_len)[0]
        qclass = unpack_from(">H", msg, offset + qname_len + 2)[0]

        return self.Question(qname, qtype, qclass)

    def extract_name(self, msg, offset):
        """ Function used to extract the name field from the answer section.

        Args:
            msg: The message recieved from the DNS server
            offset: The number of bytes from the start of the message until the end
                of the question section (or until the end of the last RR)
            
        Returns: 
            Tuple containing the name and number of bytes read.

        """
        raw_name = []
        bytes_read = 1
        jump = False

        while True:
            byte = unpack_from(">B", msg, offset)[0]
            if byte == 0:
                offset += 1
                break

            # If the field has the first two bits equal to 1, it's a pointer
            if byte >= 192:
                next_byte = unpack_from(">B", msg, offset + 1)[0]
                # Compute the pointer
                offset = ((byte << 8) + next_byte - 0xc000) - 1
                jump = True
            else:
                raw_name.append(byte)

            offset += 1

            if jump == False:
                bytes_read += 1

        raw_name.append(0)
        if jump == True:
            bytes_read += 1

        name = self.convert_to_name(raw_name)

        return (name, bytes_read)
    
    def extract_a_rdata(self, msg, offset, rdlength):
        """ Function used to extract the RDATA from an A type message.
            
        Args:
            msg: The message recieved from the DNS server
            offset: The number of bytes from the start of the message until the end
                of the question section (or until the end of the last RR)
            rdlength: The length of the RDATA section

        Returns:
            The RDATA field of the answer section as a string (an IPv4 address).

        """
        fmt_str = ">" + "B" * rdlength
        rdata = unpack_from(fmt_str, msg, offset)

        ip = ''
        for byte in rdata:
            ip += str(byte) + '.'
        ip = ip[0:-1]

        return ip

    def extract_ns_rdata(self, msg, offset, rdlength):
        """ Function used to extract the RDATA from a NS type message.
            
        Args:
            msg: The message recieved from the DNS server
            offset: The number of bytes from the start of the message until the end
                of the question section (or until the end of the last RR)
            rdlength: The length of the RDATA section

        Returns:
            The RDATA field of the answer section as a string and the offset from
            the start of the message until the end of the rdata field as a tuple:
            (rdata, field)

        """
        (name, bytes_read) = self.extract_name(msg, offset)
        offset += bytes_read

        return (name, offset)

    def extract_cname_rdata(self, msg, offset, rdlength):
        """ Function used to extract the RDATA from a CNAME type message.
            
        Args:
            msg: The message recieved from the DNS server
            offset: The number of bytes from the start of the message until the end
                of the question section (or until the end of the last RR)
            rdlength: The length of the RDATA section

        Returns:
            The RDATA field of the answer section as a string and the offset from
            the start of the message until the end of the rdata field as a tuple:
            (rdata, field)

        """
        (name, bytes_read) = self.extract_name(msg, offset)
        offset += bytes_read

        return (name, offset)

    def extract_soa_rdata(self, msg, offset, rdlength):
        """ Function used to extract the RDATA from a SOA type message.
            
        Args:
            msg: The message recieved from the DNS server
            offset: The number of bytes from the start of the message until the end
                of the question section (or until the end of the last RR)
            rdlength: The length of the RDATA section

        Returns:
            The RDATA field of the answer section as a tuple of the following form:
            (pns, amb, serial, refesh, retry, expiration, ttl)    

        """
        # extract primary NS
        (pns, bytes_read) = self.extract_name(msg, offset)
        offset += bytes_read
        # extract admin MB
        (amb, bytes_read) = self.extract_name(msg, offset)
        offset += bytes_read

        aux = unpack_from(">IIIII", msg, offset)

        serial = aux[0]
        refesh = aux[1]
        retry = aux[2]
        expiration = aux[3]
        ttl = aux[4]

        return (pns, amb, serial, refesh, retry, expiration, ttl)

    def extract_mx_rdata(self, msg, offset, rdlength):
        """ Function used to extract the RDATA from a MX type message.
            
        Args:
            msg: The message recieved from the DNS server
            offset: The number of bytes from the start of the message until the end
                of the question section (or until the end of the last RR)
            rdlength: The length of the RDATA section

        Returns:
            The RDATA field of the answer section as a tuple of the following form:
            (preference, mail_ex)

        """
        preference = unpack_from(">H", msg, offset)
        offset += 3
        
        fmt_str = ">" + "B" * (rdlength - 5)
        rdata = unpack_from(fmt_str, msg, offset)
        mail_ex = ''
        for byte in rdata:
            mail_ex += chr(byte)
        return (preference, mail_ex)

    def extract_aaaa_rdata(self, msg, offset, rdlength):
        """ Function used to extract the RDATA from an AAAA type message.
            
        Args:
            msg: The message recieved from the DNS server
            offset: The number of bytes from the start of the message until the end
                of the question section (or until the end of the last RR)
            rdlength: The length of the RDATA section

        Returns:
            The RDATA field of the answer section (an IPv6 address as a string)

        """
        fmt_str = ">" + "H" * (rdlength / 2)
        rdata = unpack_from(fmt_str, msg, offset)

        ip = ''
        for short in rdata:
            ip += format(short, 'x') + ':'
        ip = ip[0:-1]

        return ip

    def extract_txt_rdata(self, msg, offset, msglength):
        try:
            records = []
            datn = msg[offset:]
            cont = offset
            while msglength > cont:
                rlen = unpack_from(">B", datn)[0]
                datn = datn[1:]
                records.append(datn[:rlen])
                rlen += 12 # skipping unknowing things
                cont += rlen + 1
                datn = datn[rlen:]
            return records
        except Exception:
            return []

    def extract_answer(self, msg, offset):
        """ Function used to extract a RR from a DNS reply.
            
        Args:
            msg: The message recieved from the DNS server
            offset: The number of bytes from the start of the message until the end
                of the question section (or until the end of the last RR)

        Returns:
            The resource record section of the reply that begins at the given offset
            and the offset from the start of the message to where the returned RR
            ends in the following form: (Answer(name, x_type, x_class, ttl, rdlength, 
            rdata), offset)

        If the DNS Response is not implemented or recognized, an error message is
        shown and the program will exit.

        """
        (name, bytes_read) = self.extract_name(msg, offset)
        offset = offset + bytes_read

        aux = unpack_from(">HHIH", msg, offset)
        offset = offset + 10

        x_type = aux[0]
        x_class = aux[1]
        ttl = aux[2]
        rdlength = aux[3]

        rdata = ''
        if x_type == 1:
            # A type
            rdata = self.extract_a_rdata(msg, offset, rdlength)
            offset = offset + rdlength
            self._LOGGING_ and self.logger.debug_all(f"[{self.name}] extract_answer() with qtype A, rdata: {rdata}")
        elif x_type == 2:
            # NS type
            rdata = self.extract_ns_rdata(msg, offset, rdlength)
            offset = offset + rdlength
            self._LOGGING_ and self.logger.debug_all(f"[{self.name}] extract_answer() with qtype NS, rdata: {rdata}")
        elif x_type == 5:
            # CNAME type
            rdata = self.extract_cname_rdata(msg, offset, rdlength)
            offset = offset + rdlength
            self._LOGGING_ and self.logger.debug_all(f"[{self.name}] extract_answer() with qtype CNAME, rdata: {rdata}")
        elif x_type == 6:
            # SOA type
            rdata = self.extract_soa_rdata(msg, offset, rdlength)
            offset = offset + rdlength
            self._LOGGING_ and self.logger.debug_all(f"[{self.name}] extract_answer() with qtype SOA, rdata: {rdata}")
        elif x_type == 15:
            # MX type
            rdata = self.extract_mx_rdata(msg, offset, rdlength)
            offset = offset + rdlength
            self._LOGGING_ and self.logger.debug_all(f"[{self.name}] extract_answer() with qtype MX, rdata: {rdata}")
        elif x_type == 28:
            # AAAA type
            rdata = self.extract_aaaa_rdata(msg, offset, rdlength)
            offset = offset + rdlength
            self._LOGGING_ and self.logger.debug_all(f"[{self.name}] extract_answer() with qtype AAAA, rdata: {rdata}")
        elif x_type == 16:
            # TXT type
            rdata = self.extract_txt_rdata(msg, offset, len(msg))
            offset = offset + rdlength
            self._LOGGING_ and self.logger.debug_all(f"[{self.name}] extract_answer() qtype TXT, rdata: {rdata}")
        else:
            self._LOGGING_ and self.logger.debug_all(f"[{self.name}] extract_answer() unexpected qtype value: {x_type}")
            raise f"DNS Response not recognized (type {str(x_type)})"

        return (self.Answer(name, x_type, x_class, ttl, rdlength, rdata), offset)    
    
    def parse_answer(self, msg, qname_len):
        """ Function used to parse the DNS reply message.
            
        Args:
            msg: The message recieved from the DNS server
            qname_len: The length of the name beign querried

        Returns:
            The DNS reply message as a Reply namedtuple in the following
            form: (Header, Question, [Answer]).

        """
        header = self.extract_header(msg)
        question = self.extract_question(msg, qname_len)
        # 12 is header length and 4 is len(qtype) + len(qclass)
        offset = 12 + qname_len + 4 
        answer = []
        for _ in range(header.ancount):
            (a, offset) = self.extract_answer(msg, offset)
            answer.append(a)
        for _ in range(header.nscount):
            (a, offset) = self.extract_answer(msg, offset)
            answer.append(a)
        for _ in range(header.arcount):
            (a, offset) = self.extract_answer(msg, offset)
            answer.append(a)
        return self.Reply(header, question, answer)

    def tuple_str(self, t):
        """ Auxiliary function used for turning a tuple into a string.

        Args:
            The tuple

        Returns:
            The string form of the tuple

        """
        res = ''
        for i in t:
            res += str(i) + ' '
        return res

    def parse_rdata_entries(self, reply):
        for entry in reply.answer:
            if entry.x_type == QTYPE.NS:
                subdomain = str(entry.rdata[0])
                data_from_subdomain = subdomain.replace(f".{self.domain}","")
                return data_from_subdomain
            elif entry.x_type == QTYPE.CNAME:
                subdomain = str(entry.rdata[0])
                data_from_subdomain = subdomain.replace(f".{self.domain}","")
                return data_from_subdomain
            elif entry.x_type == QTYPE.SOA:
                subdomain = str(entry.rdata[0])
                data_from_subdomain = subdomain.replace(f".{self.domain}","")
                return data_from_subdomain
            elif entry.x_type == QTYPE.MX:
                subdomain = str(entry.rdata[1])
                data_from_subdomain = subdomain.replace(f".{self.domain}","")
                return data_from_subdomain
            elif entry.x_type == QTYPE.TXT:
                # wait for only one rdata entry (but maybe could split sotp packet in multiple rdata entries)
                return "".join(r.decode("utf-8", "ignore") for r in entry.rdata)
        else:
            # queries A and AAAA (Ipv4 and Ipv6 not contempled yet)
            self._LOGGING_ and self.logger.debug_all(f"[{self.name}] parse_rdata_entries() invalid rdata type: {entry.x_type}")
            raise "No entries in rdata section"


class dns(ClientWrapper):

    NAME = "dns"
    
    MAX_RFC_DOMAIN_LEN = 255                 # see rfc1035 
    MAX_DOMAIN_LEN = MAX_RFC_DOMAIN_LEN - 2  # external dotted-label specification
    MAX_SUBDOMAIN_LEN = 63                   # see rfc1035

    def __init__(self, qsotp, args, logger):
        ClientWrapper.__init__(self,type(self).__name__,qsotp,logger)
        self.name = type(self).__name__
        self.exit = False
        # Generate argparse
        self.argparser = self.generateArgParse(self.name)
        # Parse arguments
        self.domain = None
        self.hostname = None
        self.port = None
        self.query = None
        self.query_timeout = None
        self.multiple = None
        # Base arguments
        self.max_size = None
        self.poll_delay = None
        self.response_timeout = None
        self.max_retries = None
        self.parseArguments(args)
        # Dnsclient parameters
        self.dnsclient = SimpleDnsClient(self.hostname,self.port, self.domain, self.query_timeout, self.name, self.logger)
        # Logger parameters
        self.logger = logger
        self._LOGGING_ = False if logger is None else True

    # needed to check max size depending of method used for embed sotp data in dns requests.
    def checkMaxProtoSize(self,max_size,domain,multiple):
        if multiple:
            headerlen = int(Sizes.HEADER/BYTE)
            encmaxsizelen = len(urlsafe_b64encode(b'A' * (headerlen + max_size)))
            domainlen = len(domain) + 1
            numpoints = int(encmaxsizelen/self.MAX_SUBDOMAIN_LEN)
            totalen = (encmaxsizelen + numpoints) + domainlen
            self._LOGGING_ and self.logger.debug_all(f"[{self.name}] checkMaxProtoSize() headerlen:{headerlen}, encmaxsizelen:{encmaxsizelen},domainlen+1:{domainlen},numpoints:{numpoints},totalen:{totalen}")

            if totalen > self.MAX_DOMAIN_LEN:
                raise BaseException(f"Total Length is {totalen} and max available for this module is 253. Please, reduce max_size value or use a shorter domain")
        else:
            headerlen = int(Sizes.HEADER/BYTE)
            totalen = len(urlsafe_b64encode(b'A' * (headerlen + max_size)))
            self._LOGGING_ and self.logger.debug_all(f"[{self.name}] checkMaxProtoSize() headerlen:{headerlen},max_size:{max_size},totalen:{totalen}")

            if totalen > self.MAX_SUBDOMAIN_LEN:
                raise BaseException(f"Total Length is {totalen} and max available for this module is 63. Please, reduce max_size value or use --multiple parameter")

    def parseArguments(self, args):
        args = self.argparser.parse_args(args.split())
        self.domain = args.domain[0]
        self.hostname = args.hostname
        self.port = args.port[0]
        self.query = args.query[0]
        self.query_timeout = args.query_timeout[0]
        self.multiple = args.multiple
        self.max_size = args.max_size[0]
        self.poll_delay = args.poll_delay[0]
        self.response_timeout = args.response_timeout[0]
        self.max_retries = args.max_retries[0]
        self.checkMaxProtoSize(self.max_size,self.domain, self.multiple)

    def splitInMultipleSubdomains(self, sotpdata):
        lendata = len(sotpdata)
        complete = ""
        for i in range(0,lendata,self.MAX_SUBDOMAIN_LEN):
            complete = complete + "." + sotpdata[i:i+self.MAX_SUBDOMAIN_LEN]  
        newdomain = complete[1:] + "." + self.domain
        return newdomain

    def wrap(self,content):
        # make your own routine to encapsulate sotp content in dns packet (i use b64 in subdomain space)
        sotpDataBytes = urlsafe_b64encode(content)
        sotpDataEnc = str(sotpDataBytes, "utf-8")
        packedata = None

        # if multiple is supported, split sotp content in multiple subdomains
        if self.multiple:
            packedata = self.splitInMultipleSubdomains(sotpDataEnc)
        else:
            packedata = sotpDataEnc + "." + self.domain

        # doing dns query and obtaining a raw dns response
        self._LOGGING_ and self.logger.debug_all(f"[{self.name}] wrap() domain for query: {packedata}")
        query, querylen = self.dnsclient.get_dns_query(packedata, self.query)
        raw_reply = self.dnsclient.query_dns_server(query)

        self.inbox.put(self.messageToWrapper((raw_reply,querylen)))

    def unwrap(self,content):
        raw_reply, querylen = content
        # parsing raw dns response and getting rdata content
        reply = self.dnsclient.parse_answer(raw_reply, querylen)
        dataEnc = self.dnsclient.parse_rdata_entries(reply)
        self._LOGGING_ and self.logger.debug_all(f"[{self.name}] wrap() data dns response: {dataEnc}")
        data = urlsafe_b64decode(dataEnc)
        return data