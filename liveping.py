#!/usr/bin/env python
##########################
# liveping.py - Displays a live graph with ping stats
# By makzk, 2015 - https://github.com/makzk/liveping
# Licensed under MIT license, available here:
# https://github.com/makzk/liveping/blob/master/LICENSE
##########################

import sys, time, threading, socket, admin, ping, tkMessageBox
from Tkinter import *

class Liveping:
	ping = ping.Ping().ping

	def __init__(self):
		# Settings
		self.host = '8.8.8.8'
		if __name__ == '__main__' and len(sys.argv) > 1: self.host = sys.argv[1]

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
		self.win.config()

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
		try:
			host = socket.gethostbyname(self.host)
		except socket.error:
			tkMessageBox.showerror('Liveping error', 'Could not resolve host "' + self.host + '"')
			raise

		if host != self.host:
			self.win.wm_title('Liveping - pinging %s (%s)' % (self.host, host))
			self.host = host
		else:
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

	admin = admin.Admin()

	if not admin.isUserAdmin():
		admin.runAsAdmin()
		sys.exit(0)

	lp = Liveping()
	lp.run()