##########################
# ping.py - Cutted down version from https://gist.github.com/pklaus/856268
# Copyright (c) Matthew Dixon Cowles, <http://www.visi.com/~mdc/>.
#
# Distributable under the terms of the GNU General Public License
# version 2. Provided with no warranties of any sort.
#
# Original Version from Matthew Dixon Cowles <ftp://ftp.visi.com/users/mdc/ping.py>
# Rewrite by Jens Diemer <http://www.python-forum.de/post-69122.html#69122>
# Rewrite by Johannes Meyer <http://www.python-forum.de/viewtopic.php?p=183720>
#
# Cutted down version by Makzk.
#
##########################

import os,socket, struct, select
from timeit import default_timer as timer

class Ping:
    # From /usr/include/linux/icmp.h; your milage may vary.
    ICMP_ECHO_REQUEST = 8 # Seems to be the same on Solaris.

    def checksum(self, source_string):
        sum = 0
        countTo = (len(source_string)/2)*2
        count = 0
        while count<countTo:
            thisVal = ord(source_string[count + 1])*256 + ord(source_string[count])
            sum = sum + thisVal
            sum = sum & 0xffffffff # Necessary?
            count = count + 2

        if countTo<len(source_string):
            sum = sum + ord(source_string[len(source_string) - 1])
            sum = sum & 0xffffffff # Necessary?

        sum = (sum >> 16)  +  (sum & 0xffff)
        sum = sum + (sum >> 16)
        answer = ~sum
        answer = answer & 0xffff

        # Swap bytes. Bugger me if I know why.
        answer = answer >> 8 | (answer << 8 & 0xff00)

        return answer


    def receive_one(self, my_socket, ID, timeout):
        timeLeft = timeout
        while True:
            startedSelect = timer()
            whatReady = select.select([my_socket], [], [], timeLeft)
            howLongInSelect = (timer() - startedSelect)
            if whatReady[0] == []: # Timeout
                return

            timeReceived = timer()
            recPacket, addr = my_socket.recvfrom(1024)
            icmpHeader = recPacket[20:28]
            type, code, checksum, packetID, sequence = struct.unpack(
                "bbHHh", icmpHeader
            )
            if packetID == ID:
                bytesInDouble = struct.calcsize("d")
                timeSent = struct.unpack("d", recPacket[28:28 + bytesInDouble])[0]
                return timeReceived - timeSent

            timeLeft = timeLeft - howLongInSelect
            if timeLeft <= 0:
                return

    def send_one(self, my_socket, dest_addr, ID):
        dest_addr  =  socket.gethostbyname(dest_addr)

        # Header is type (8), code (8), checksum (16), id (16), sequence (16)
        my_checksum = 0

        # Make a dummy heder with a 0 checksum.
        header = struct.pack("bbHHh", self.ICMP_ECHO_REQUEST, 0, my_checksum, ID, 1)
        bytesInDouble = struct.calcsize("d")
        data = (192 - bytesInDouble) * "Q"
        data = struct.pack("d", timer()) + data

        # Calculate the checksum on the data and the dummy header.
        my_checksum = self.checksum(header + data)

        # Now that we have the right checksum, we put that in. It's just easier
        # to make up a new header than to stuff it into the dummy.
        header = struct.pack(
            "bbHHh", self.ICMP_ECHO_REQUEST, 0, socket.htons(my_checksum), ID, 1
        )
        packet = header + data
        my_socket.sendto(packet, (dest_addr, 1)) # Don't know about the 1


    #Returns either the delay (in seconds) or none on timeout.
    def ping(self, dest_addr, timeout):
        icmp = socket.getprotobyname("icmp")
        try:
            my_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, icmp)
        except socket.error, (errno, msg):
            if errno == 1:
                raise socket.error(msg)
            raise # raise the original error

        my_ID = os.getpid() & 0xFFFF

        self.send_one(my_socket, dest_addr, my_ID)
        delay = self.receive_one(my_socket, my_ID, timeout)

        my_socket.close()
        return delay

