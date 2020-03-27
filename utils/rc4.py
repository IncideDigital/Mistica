#
# MIT License
# 
# Copyright (c) 2018 David Buchanan
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

class RC4:
    """
    https://github.com/DavidBuchanan314/rc4
    
    This class implements the RC4 streaming cipher.
    
    Derived from http://cypherpunks.venona.com/archive/1994/09/msg00304.html
    """

    def __init__(self, key, streaming=True):
        assert(isinstance(key, (bytes, bytearray)))

        # key scheduling
        S = list(range(0x100))
        j = 0
        for i in range(0x100):
            j = (S[i] + key[i % len(key)] + j) & 0xff
            S[i], S[j] = S[j], S[i]
        self.S = S

        # in streaming mode, we retain the keystream state between crypt()
        # invocations
        if streaming:
            self.keystream = self._keystream_generator()
        else:
            self.keystream = None

    def crypt(self, data):
        """
        Encrypts/decrypts data (It's the same thing!)
        """
        assert(isinstance(data, (bytes, bytearray)))
        keystream = self.keystream or self._keystream_generator()
        return bytes([a ^ b for a, b in zip(data, keystream)])

    def _keystream_generator(self):
        """
        Generator that returns the bytes of keystream
        """
        S = self.S.copy()
        x = y = 0
        while True:
            x = (x + 1) & 0xff
            y = (S[x] + y) & 0xff
            S[x], S[y] = S[y], S[x]
            i = (S[x] + S[y]) & 0xff
            yield S[i]