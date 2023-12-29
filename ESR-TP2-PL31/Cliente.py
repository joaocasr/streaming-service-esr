import sys
import os
from tkinter import Tk
from RtpPacket import RtpPacket
from ClienteGUI import ClienteGUI
import socket

class Cliente:	
	def runClient(clientip,clientport,server_addr,server_port,streamport,name):
		os.environ.__setitem__('DISPLAY', ':0.0')
		try:
			addr = '127.0.0.1'
			port = 25000
		except:
			print("[Usage: Cliente.py]\n")	
		
		root = Tk()
		root.config(bg = '#528B8B')
		content = "movie.Mjpeg"
		
		# Create a new client
		app = ClienteGUI(root, server_addr, server_port,clientip,clientport,content,streamport,name)
		app.master.title("STREAM - ESR | User: "+name)
		root.mainloop()