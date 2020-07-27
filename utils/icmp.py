#
# Copyright (c) 2020 Raul Caro.
#
# This file is part of ICMPack 
# (see https://github.com/rcaroncd/ICMPack).
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
from sys import byteorder
from socket import htons
from random import random


class Sizes(object):
	'''
	See https://tools.ietf.org/html/rfc792 Page 14
	'''
	IP_HEADER = 20
	ICMP_HEADER = 8
	ICMP_TYPE = 1
	ICMP_CODE = 1
	ICMP_CHECKSUM = 2
	ICMP_IDENTIFIER = 2
	ICMP_SEQUENCE = 2
	# extra field of icmp data (sent by ping program by default)
	ICMP_TIMESTAMP = 8
	ICMP_UNKNOWN = 8


class Offsets(object):
	'''
	Precalculate Offsets to parse ICMP Packet.
	'''
	IP_HEADER = Sizes.IP_HEADER
	ICMP_HEADER = Sizes.IP_HEADER + Sizes.ICMP_HEADER
	# after ip header, start icmp header
	ICMP_TYPE = Sizes.ICMP_TYPE
	ICMP_CODE = ICMP_TYPE + Sizes.ICMP_CODE
	ICMP_CHECKSUM = ICMP_CODE + Sizes.ICMP_CHECKSUM
	ICMP_IDENTIFIER = ICMP_CHECKSUM + Sizes.ICMP_IDENTIFIER
	ICMP_SEQUENCE = ICMP_IDENTIFIER + Sizes.ICMP_SEQUENCE
	# extra field of icmp data (sent by ping program by default)
	ICMP_TIMESTAMP = ICMP_SEQUENCE + Sizes.ICMP_TIMESTAMP
	ICMP_UNKNOWN = ICMP_TIMESTAMP + Sizes.ICMP_UNKNOWN


class Packet(object):
	"""
	Class for handling ICMP Echo Request and Echo Response packets
	from an array of bytes passed through input.
	Represents an ICMP package Echo Request/Response

	ICMP Echo / Echo Reply Message header info from RFC792
		-> http://tools.ietf.org/html/rfc792

		0                   1                   2                   3
		0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
		+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
		|     Type      |     Code      |          Checksum             |
		+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
		|           Identifier          |        Sequence Number        |
		+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
		|     Data ...
		+-+-+-+-+-

	*Max data (available) per ICMP packet 65507 bytes:

		65535 bytes (Max IP Packet)
		  -20 bytes (IP Header)
		   -8 bytes (ICMP Header) 
		===== 
		65507 bytes ~= 65 Kb (1Mb ~= 16 ICMP Packets)

	"""

	REQUEST_TYPE = 8
	REQUEST_CODE = 0
	REQUEST_CHECKSUM = 0
	REQUEST_IDENTIFIER = 0
	REQUEST_SEQUENCE = 1

	RESPONSE_TYPE = 0
	RESPONSE_CODE = 0
	RESPONSE_CHECKSUM = 0
	RESPONSE_IDENTIFIER = 0
	RESPONSE_SEQUENCE = 1

	def __init__(self, rawdata=None):
		self.type = b''
		self.code = b''
		self.checksum = b''
		self.id = b''
		self.seq = b''
		self.data = b''
		# passing raw data, try to unpack within icmp packet
		if rawdata != None:
			self.unpack(rawdata)

	def __repr__(self):
		return "Packet()"

	def __str__(self):
		r =  f"Type: '{self.type.hex()}', "
		r += f"Code: '{self.code.hex()}', "
		r += f"Checksum: '{self.checksum.hex()}', "
		r += f"Identifier: '{self.id.hex()}', "
		r += f"Sequence Number: '{self.seq.hex()}', "
		r += f"Data: '{self.data.hex()}'"
		return r

	def unpack(self, data):
		"""
		Extracts data from a received ICMP Packet (Echo Request or Echo Response).
		Does not ensure that the resulting data is that of a 
		valid icmp package, so the attributes should be
		checked after performing this transformation.
		"""
		ip_header = data[:Offsets.IP_HEADER]
		icmp_data = data[Offsets.IP_HEADER:]
		self.type = icmp_data[:Offsets.ICMP_TYPE]
		self.code = icmp_data[Offsets.ICMP_TYPE:Offsets.ICMP_CODE]
		self.checksum = icmp_data[Offsets.ICMP_CODE:Offsets.ICMP_CHECKSUM]
		self.id = icmp_data[Offsets.ICMP_CHECKSUM:Offsets.ICMP_IDENTIFIER]
		self.seq = icmp_data[Offsets.ICMP_IDENTIFIER:Offsets.ICMP_SEQUENCE]
		self.data = icmp_data[Offsets.ICMP_SEQUENCE:]

	def calc_checksum(self, source_string):
		"""
		A port of the functionality of in_cksum() from ping.c
		Ideally this would act on the string as a series of 16-bit ints (host
		packed), but this works.
		Network data is big-endian, hosts are typically little-endian.

		From https://github.com/mjbright/python3-ping/blob/master/ping.py
		"""
		countTo = (int(len(source_string)/2))*2
		sum = 0
		count = 0

		# Handle bytes in pairs (decoding as short ints)
		loByte = 0
		hiByte = 0
		while count < countTo:
			if (byteorder == "little"):
				loByte = source_string[count]
				hiByte = source_string[count + 1]
			else:
				loByte = source_string[count + 1]
				hiByte = source_string[count]
			sum = sum + (hiByte * 256 + loByte)
			count += 2

		# Handle last byte if applicable (odd-number of bytes)
		# Endianness should be irrelevant in this case
		if countTo < len(source_string): # Check for odd length
			loByte = source_string[len(source_string)-1]
			sum += loByte

		sum &= 0xffffffff # Truncate sum to 32 bits (a variance from ping.c, which
						  # uses signed ints, but overflow is unlikely in ping)

		sum = (sum >> 16) + (sum & 0xffff)    # Add high 16 bits to low 16 bits
		sum += (sum >> 16)                    # Add carry from above (if any)
		answer = ~sum & 0xffff                # Invert and truncate to 16 bits
		answer = htons(answer)
		return answer

	def pack_request(self, data=None):
		"""
		Create an ICMP Echo Request package with default data (like ping)
		or allow custom data to be passed to it.
		"""
		self.type = self.REQUEST_TYPE.to_bytes(Sizes.ICMP_TYPE,byteorder=byteorder)
		self.code = self.REQUEST_CODE.to_bytes(Sizes.ICMP_CODE,byteorder=byteorder)
		self.checksum = self.REQUEST_CHECKSUM.to_bytes(Sizes.ICMP_CHECKSUM,byteorder='big')
		new_identifier = int((id(data) * random()) % 65535)
		self.id = new_identifier.to_bytes(Sizes.ICMP_IDENTIFIER,byteorder=byteorder)
		self.seq = self.REQUEST_SEQUENCE.to_bytes(Sizes.ICMP_SEQUENCE,byteorder='big')		
		self.data = data
		
		# calculate new checksum of icmp request packet
		raw_packet = self.toBytes()
		newchecksum = self.calc_checksum(raw_packet)
		self.checksum = newchecksum.to_bytes(Sizes.ICMP_CHECKSUM,byteorder='big')

	def pack_response(self, request, data=None):
		"""
		Create an ICMP Echo Response package
		"""
		assert isinstance(request, Packet)
		self.type = self.RESPONSE_TYPE.to_bytes(Sizes.ICMP_TYPE,byteorder=byteorder)
		self.code = self.RESPONSE_CODE.to_bytes(Sizes.ICMP_CODE,byteorder=byteorder)
		self.checksum = self.RESPONSE_CHECKSUM.to_bytes(Sizes.ICMP_CHECKSUM,byteorder='big')
		self.id = request.id
		self.seq = request.seq
		assert isinstance(data, bytes)
		self.data = data

		# calculate new checksum of icmp response packet
		raw_packet = self.toBytes()
		newchecksum = self.calc_checksum(raw_packet)
		self.checksum = newchecksum.to_bytes(Sizes.ICMP_CHECKSUM,byteorder='big')

	def toBytes(self):
		"""
		Returns an array of bytes corresponding to the icmp package built.
		"""
		return (self.type + self.code + self.checksum + self.id + self.seq + self.data)
