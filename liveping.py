#!/usr/bin/env python
import os, sys, socket, struct, select, time, threading, warnings
import pylab as plt
from timeit import default_timer as timer
from Tkinter import TclError

##########################
# ping.py
# taken from https://gist.github.com/zed/255009
##########################
"""
    A pure python ping implementation using raw socket.


    Note that ICMP messages can only be sent from processes running as root.


    Derived from ping.c distributed in Linux's netkit. That code is
    copyright (c) 1989 by The Regents of the University of California.
    That code is in turn derived from code written by Mike Muuss of the
    US Army Ballistic Research Laboratory in December, 1983 and
    placed in the public domain. They have my thanks.

    Bugs are naturally mine. I'd be glad to hear about them. There are
    certainly word - size dependenceies here.

    Copyright (c) Matthew Dixon Cowles, <http://www.visi.com/~mdc/>.
    Distributable under the terms of the GNU General Public License
    version 2. Provided with no warranties of any sort.

    Original Version from Matthew Dixon Cowles:
      -> ftp://ftp.visi.com/users/mdc/ping.py

    Rewrite by Jens Diemer:
      -> http://www.python-forum.de/post-69122.html#69122


    Revision history
    ~~~~~~~~~~~~~~~~

    December 12, 2009
    - [zed] replaced time.clock() with timeit.default_timer()
    - [zed] renamed do_one() -> ping()

    May 30, 2007
    little rewrite by Jens Diemer:
     -  change socket asterisk import to a normal import
     -  replace time.time() with time.clock()
     -  delete "return None" (or change to "return" only)
     -  in checksum() rename "str" to "source_string"

    November 22, 1997
    Initial hack. Doesn't do much, but rather than try to guess
    what features I (or others) will want in the future, I've only
    put in what I need now.

    December 16, 1997
    For some reason, the checksum bytes are in the wrong order when
    this is run under Solaris 2.X for SPARC but it works right under
    Linux x86. Since I don't know just what's wrong, I'll swap the
    bytes always and then do an htons().

    December 4, 2000
    Changed the struct.pack() calls to pack the checksum and ID as
    unsigned. My thanks to Jerome Poincheval for the fix.


    Last commit info:
    ~~~~~~~~~~~~~~~~~
    $LastChangedDate: $
    $Rev: $
    $Author: $
"""

# From /usr/include/linux/icmp.h; your milage may vary.
ICMP_ECHO_REQUEST = 8 # Seems to be the same on Solaris.


def checksum(source_string):
	"""
	I'm not too confident that this is right but testing seems
	to suggest that it gives the same answers as in_cksum in ping.c
	"""
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


def receive_one_ping(my_socket, ID, timeout):

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

def send_one_ping(my_socket, dest_addr, ID):
	"""
	Send one ping to the given >dest_addr<.
	"""
	dest_addr  =  socket.gethostbyname(dest_addr)

	# Header is type (8), code (8), checksum (16), id (16), sequence (16)
	my_checksum = 0

	# Make a dummy heder with a 0 checksum.
	header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, my_checksum, ID, 1)
	bytesInDouble = struct.calcsize("d")
	data = (192 - bytesInDouble) * "Q"
	data = struct.pack("d", timer()) + data

	# Calculate the checksum on the data and the dummy header.
	my_checksum = checksum(header + data)

	# Now that we have the right checksum, we put that in. It's just easier
	# to make up a new header than to stuff it into the dummy.
	header = struct.pack(
		"bbHHh", ICMP_ECHO_REQUEST, 0, socket.htons(my_checksum), ID, 1
	)
	packet = header + data
	my_socket.sendto(packet, (dest_addr, 1)) # Don't know about the 1


#Returns either the delay (in seconds) or none on timeout.
def ping(dest_addr, timeout):
	icmp = socket.getprotobyname("icmp")
	try:
		my_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, icmp)
	except socket.error, (errno, msg):
		if errno == 1:
			# Operation not permitted
			msg = msg + (
				" - Note that ICMP messages can only be sent from processes"
				" running as root."
			)
			raise socket.error(msg)
		raise # raise the original error

	my_ID = os.getpid() & 0xFFFF

	send_one_ping(my_socket, dest_addr, my_ID)
	delay = receive_one_ping(my_socket, my_ID, timeout)

	my_socket.close()
	return delay
do_one = ping # preserve  old name for compatibility

##########################
# liveping.py
##########################

exit = False
host = '8.8.8.8' if len(sys.argv) < 2 else sys.argv[1]
last_latency = 0
max_latency = 0
min_latency = 0
n = 100

y = []

def get_ping_ms():
	global exit
	try:
		lat = ping(host, .3)
		return 0 if lat == None else (lat * 1000)
	except BaseException,e:
		print 'Ping error:', e
		exit = True

def updater():
	global y, last_latency, max_latency, min_latency
	while not exit:
		time.sleep(.2)
		last_latency = get_ping_ms()
		if len(y) == n:
			for i in range(1, len(y)):
				y[i-1] = y[i]
			y[len(y)-1] = last_latency
		else:
			y.append(last_latency)
		if len(y) == 1:
			max_latency = last_latency
			min_latency = last_latency
		else:
			max_latency = max(last_latency, max_latency)
			min_latency = min(last_latency, min_latency)

if __name__ == '__main__':
	thread = threading.Thread(target=updater)
	thread.daemon = True
	thread.start()
	time.sleep(.3)

	if not exit:
		with warnings.catch_warnings():
			warnings.simplefilter("ignore")
			f = plt.figure()
			f.canvas.set_window_title('Ping live graph')
			plt.title('pinging ' + host, fontsize=12)
			plt.ylabel('latency [ms]', fontsize=12)
			ln, = plt.plot(range(n), [300]+[0]*(n-1)) # Initial view
			plt.ion()
			plt.show()
			while not exit:
				try:
					plt.pause(.2)
					data_y = y
					data_x = range(len(data_y))
					ln.set_ydata(data_y)
					ln.set_xdata(data_x)
					chart_title = 'pinging ' + host + ', now: '
					chart_title += 'Timeout' if last_latency == 0 else '%.2f ms' % last_latency
					chart_title += ' max: %.2f min: %.2f' % (max_latency, min_latency)
					plt.title(chart_title, fontsize=12)
					plt.draw()
				except (KeyboardInterrupt, TclError, RuntimeError):
					exit = True
			plt.close()
