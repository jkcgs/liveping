#!/usr/bin/env python
##########################
# liveping.py - Displays a live graph with ping stats
# Singlefile version
# By makzk, 2015 - https://github.com/makzk/liveping
# Licensed under MIT license, available here:
# https://github.com/makzk/liveping/blob/master/LICENSE
##########################

import sys, os, time, threading, ctypes, socket, struct, select
from Tkinter import *
from timeit import default_timer as timer

##########################
# admin.py - Run as administrator (this is required by ping)
# On Windows requires Windows XP SP2 or higher
# Cutted version from http://stackoverflow.com/a/19719292
##########################

class Admin:
	def isUserAdmin(self):
		if os.name == 'nt':
			try:
				import ctypes
				return ctypes.windll.shell32.IsUserAnAdmin()
			except:
				return False
		elif os.name == 'posix':
			return os.getuid() == 0
		else:
			return True # OS not recognized, assuming true

	def runAsAdmin(self):
		if os.name == 'posix':
			# sudo or gksu depending if running on console or not
			run = "sudo" if sys.stdin.isatty() else "gksudo"
			os.execvp(run, [run, sys.executable] + sys.argv)
		elif os.name != 'nt':
			raise RuntimeError, "Could not run as administrator. Do it manually, please."

		import win32api, win32con, win32event, win32process
		from win32com.shell.shell import ShellExecuteEx
		from win32com.shell import shellcon

		params = " ".join(['"%s"' % (x,) for x in sys.argv])
		procInfo = ShellExecuteEx(fMask=shellcon.SEE_MASK_NOCLOSEPROCESS,
								  lpVerb='runas', lpFile=sys.prefix+'\pythonw.exe', lpParameters=params)

		procHandle = procInfo['hProcess']
		obj = win32event.WaitForSingleObject(procHandle, win32event.INFINITE)
		rc = win32process.GetExitCodeProcess(procHandle)

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

class Liveping:
	ping = Ping().ping

	def __init__(self):
		# Settings
		self.host = '8.8.8.8'
		self.max_display = 100
		self.spacing = 5
		self.win_height = 300
		self.ping_timeout = 1000

		# Self data
		self.cv_width = self.max_display*self.spacing-self.spacing
		self.last_ping = 0
		self.max_ping = 0
		self.min_ping = 9999
		self.avg_ping = 0
		self.exit = False
		self.data = []
		self.data_avg = []

		# Window
		self.win = Tk()

		frame = Frame()
		self.sidebar = Canvas(frame, bg="white", height=self.win_height, width=40)
		self.sidebar.pack(side="left")

		self.graph = Canvas(frame, bg="black", height=self.win_height, width=self.cv_width)
		self.graph.after(100, self.drawer)
		self.graph.pack(side="left")
		frame.pack()

		self.bar = Label(self.win, text="Waiting data...")
		self.bar.pack(fill=X)

	def run(self):
		if __name__ == '__main__' and len(sys.argv) > 1: self.host = sys.argv[1]

		try:
			host = socket.gethostbyname(self.host)
		except socket.error:
			raise

		if host != self.host:
			self.win.wm_title('Liveping - pinging %s (%s)' % (self.host, host))
			self.host = host
		else
			self.win.wm_title('Liveping - pinging ' + self.host)

		# Ping data updating thread
		thread = threading.Thread(target=self.updater)
		thread.daemon = True
		thread.start()
		time.sleep(.3)

		try:
			self.win.mainloop()
		except KeyboardInterrupt:
			print

		exit = True # Stop updater thread

	def get_ping_ms(self):
		lat = self.ping(self.host, self.ping_timeout / 1000)
		return 0.0 if lat == None else (lat * 1000)

	def updater(self):
		while not self.exit:
			time.sleep(.2)
			self.last_ping = self.get_ping_ms()
			if len(self.data) == self.max_display: del self.data[0]
			self.data.append(self.last_ping)
			self.max_ping = max([self.last_ping, self.max_ping])
			self.min_ping = self.min_ping if self.last_ping == 0 else min([self.min_ping, self.last_ping])

			self.avg_ping = reduce(lambda x, y: x + y, self.data) / len(self.data)
			if len(self.data_avg) == self.max_display: del self.data_avg[0]
			self.data_avg.append(self.avg_ping)

			txt = "Last: %.1f, " % self.last_ping;
			txt += "Min: %.1f, Max: %.1f, " % (self.min_ping, self.max_ping);
			txt += "MinS: %.1f, MaxS: %.1f, " % (min(self.data), max(self.data));
			txt += "Avg: %.1f" % self.avg_ping;
			try:
				self.bar.config(text=txt)
			except TclError:
				pass

	def drawer(self):
		data = self.data
		if len(data) == 0:
			self.graph.after(100, self.drawer)
			return

		self.graph.delete(ALL)

		# Calculate the max y position on for 50 multiples
		max_y = max(data)
		mult = 1
		scale_num = 50 if max_y > 30 else (5 if max_y > 5 else 2)
		while scale_num * mult <= max_y:
			mult += 1
		max_y = mult * scale_num

		# Draw the scale on sidebar
		self.draw_rule(max_y)

		for i in range(len(data)):
			if len(data) > i + 1: # Check if there is another ping
				# Draw a red line for a timeout (0)
				color = "red" if data[i+1] == 0 else "white"
				y1 = data[i] * self.win_height / max_y
				y2 = data[i+1] * self.win_height / max_y
				x1 = i * self.spacing
				x2 = i * self.spacing + self.spacing
				self.graph.create_line(x1, self.win_height-y1, x2, self.win_height-y2, fill=color)

				# Draw average curve
				y1 = self.data_avg[i] * self.win_height / max_y
				y2 = self.data_avg[i+1] * self.win_height / max_y
				x1 = i * self.spacing
				x2 = i * self.spacing + self.spacing
				self.graph.create_line(x1, self.win_height-y1, x2, self.win_height-y2, fill="green")

		self.graph.after(100, self.drawer)

	# Draws the sidebar scale and graphic grid
	def draw_rule(self, mx):
		self.sidebar.delete(ALL)
		for i in range(10):
			y = (self.win_height/10)*i
			r = (mx/10.0)*(10.0-i)

			if i > 0:
				self.sidebar.create_line(35, y, 40, y, fill="black")
				self.sidebar.create_text(20, y, text=('%i' % r if mx >= 10 else '%.1f' % r))
				self.graph.create_line(0, y, self.cv_width, y, fill="gray18")

if __name__ == '__main__':
	helpargs = ['-h', '-help', '--help', '/?', '/h', '/help']
	if len(sys.argv) > 1 and sys.argv[1] in helpargs:
		print 'liveping by makzk'
		print 'Usage: ' + sys.argv[0] + ' [host = 8.8.8.8]'
		sys.exit(0)

	admin = Admin()

	if not admin.isUserAdmin():
		admin.runAsAdmin()
		sys.exit(0)

	lp = Liveping()
	lp.run()