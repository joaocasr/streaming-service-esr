import queue
import time
from tkinter import *
import tkinter.messagebox
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os
import socket
from RtpPacket import RtpPacket

from Request import Request

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"
pause_click = False
receive_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

class ClienteGUI:
	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT
	
	SETUP = 0
	PLAY = 1
	PAUSE = 2
	TEARDOWN = 3
	# Initiation..
	def __init__(self, master, addr, port,rtpaddress,rtpport,video,streamport,name):
		self.master = master
		self.master.protocol("WM_DELETE_WINDOW", self.handler)
		self.createWidgets()
		self.addr = addr
		self.port = int(port)
		self.addrtp = rtpaddress
		self.portrtp = rtpport
		self.video = video
		self.rtspSeq = 0
		self.sessionId = 0
		self.requestSent = -1
		self.teardownAcked = 0
		self.openRtpPort()
		self.rtspSocket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
		self.rtspSocket.connect((self.addr, self.port))
		self.stream_port = streamport
		self.frameNbr = 0
		self.clientname = name
		self.packet_buffer = queue.Queue(1024)

	def createWidgets(self):
		"""Build GUI."""
		# Create Play button
		self.setup = Button(self.master, width=20, padx=3, pady=3,bg='#B0C4DE')
		self.setup["text"] = "Play"
		self.setup["command"] = self.playMovie
		self.setup.grid(row=1, column=0, padx=2, pady=2)
		
		# Create Pause button			
		self.pause = Button(self.master, width=20, padx=3, pady=3,bg='#B0C4DE')
		self.pause["text"] = "Pause"
		self.pause["command"] = self.pauseMovie
		self.pause.grid(row=1, column=1, padx=2, pady=2)
		
		# Create Teardown button
		self.teardown = Button(self.master, width=20, padx=3, pady=3,bg='#B0C4DE')
		self.teardown["text"] = "Quit"
		self.teardown["command"] =  self.exitClient
		self.teardown.grid(row=1, column=2, padx=2, pady=2)
		
		# Create a label to display the movie
		self.label = Label(self.master, height=19)
		self.label.grid(row=0, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5) 
	
	def playMovie(self):
		"""Setup button handler."""
		global pause_click
		if pause_click == True:
			pause_click = False
		else: 
			threading.Thread(target=self.listenRtp).start()
			self.playEvent = threading.Event()
			self.playEvent.clear()
			self.sendRtspRequest(self.SETUP)

	
	def exitClient(self):
		"""Teardown button handler."""
		self.master.destroy() # Close the gui window
		os.remove("movie-image" + CACHE_FILE_EXT) # Delete the cache image from video
		pause_click = False
		receive_socket.close()

	def pauseMovie(self):
		"""Pause button handler."""
		global pause_click
		pause_click = True
		if self.state == self.PLAYING:
			self.sendRtspRequest(self.PAUSE)
	
	# CLIENT SENDS REAL TIME REQUEST 
	def sendRtspRequest(self,request):
		if(request==self.PLAY):
			self.rtspSeq += 1
			self.requestSent = self.PLAY
			cli_request = Request(self.PLAY,self.rtspSeq,self.video,socket.gethostname(),self.portrtp,self.addrtp,self.stream_port,self.addrtp,self.clientname)
			self.rtspSocket.sendto(cli_request.toJson().encode('utf-8'),(self.addr, self.port))
		if(request == self.SETUP):
			threading.Thread(target=self.recvRtspReply).start()
			self.rtspSeq += 1
			self.requestSent = self.SETUP
			cli_request = Request(self.SETUP,self.rtspSeq,self.video,socket.gethostname(),self.portrtp,self.addrtp,self.stream_port,self.addrtp,self.clientname)
			self.rtspSocket.sendto(cli_request.toJson().encode('utf-8'),(self.addr, self.port))
		if(request == self.PAUSE):
			threading.Thread(target=self.recvRtspReply).start()
			self.rtspSeq += 1
			self.requestSent = self.SETUP
			cli_request = Request(self.PAUSE,self.rtspSeq,self.video,socket.gethostname(),self.portrtp,self.addrtp,self.stream_port,self.addrtp,self.clientname)
			self.rtspSocket.sendto(cli_request.toJson().encode('utf-8'),(self.addr, self.port))

	def processBuffer(self):
		payload = None
		if not self.packet_buffer.empty():
			payload = self.packet_buffer.get()
		return payload

	def listenRtp(self):
		"""Listen for RTP packets."""
		global receive_socket
		receive_socket.bind((self.addrtp,self.stream_port))
		print("à escuta de rtp packets")
		receive_socket.listen()
		while True:
			#print((self.addrtp,self.stream_port))
			conn, addr = receive_socket.accept()
			try:
				while True:
					data = conn.recv(20480)
					if data:
						rtpPacket = RtpPacket()
						rtpPacket.decode(data)
						print("seq "+str(rtpPacket.seqNum()))
						if pause_click == False:
							self.packet_buffer.put(rtpPacket.getPayload())
						else:
							self.packet_buffer.put(rtpPacket.getPayload())
							continue
						p = self.processBuffer()
						rr = self.writeFrame(p)
						x = threading.Thread(target=self.updateMovie, args=(rr,))
						x.start()
					else:
						break
			except:
				wrong=1
				# Stop listening upon requesting PAUSE or TEARDOWN
				#print("something went wrong")
				#if self.playEvent.isSet(): 
				#	break
				
				#self.rtpSocket.shutdown(socket.SHUT_RDWR)
				#self.rtpSocket.close()
				#break
				
	def recvRtspReply(self):
		"""Receive RTSP reply from the server."""
		while True: 
			reply = self.rtspSocket.recv(1024)
			
			if reply:
				self.parseRtspReply(reply.decode("utf-8"))
			
			# Close the RTSP socket upon requesting Teardown
			if self.requestSent == self.TEARDOWN:
				self.rtspSocket.shutdown(socket.SHUT_RDWR)
				self.rtspSocket.close()
				break

	def parseRtspReply(self, data):
		"""Parse the RTSP reply from the server."""
		lines = data.split('\n')
		print("***************")
		print(lines)
		print("***************")
		seqNum = int(lines[1].split(' ')[1])
		# Process only if the server reply's sequence number is the same as the request's
		print("server reply's sequence number:"+str(seqNum))
		print("requests sequence number:"+str(self.rtspSeq))
		if seqNum == self.rtspSeq:
			session = int(lines[2].split(' ')[1])
			# New RTSP session ID
			if self.sessionId == 0:
				self.sessionId = session
			print("sessão gerada:"+str(session))
			print("sessão atual:"+str(self.sessionId))
			print(">>>>>>>>>>>>>>>>>>>")
			print(str(self.requestSent))
			# Process only if the session ID is the same
			if self.sessionId == session:
				if int(lines[0].split(' ')[1]) == 200: 
					if self.requestSent == self.SETUP:
						#-------------
						# TO COMPLETE
						#-------------
						# Update RTSP state.
						self.state = self.READY
						print("Ready")
						# Open RTP port.
						self.openRtpPort() 
					elif self.requestSent == self.PLAY:
						# self.state = ...
						self.state = self.PLAYING
						print('\nPLAY sent\n')
					elif self.requestSent == self.PAUSE:
						# self.state = ...
						self.state = self.READY
						# The play thread exits. A new thread is created on resume.
						self.playEvent.set()
					elif self.requestSent == self.TEARDOWN:
						# self.state = ...
						self.state = self.TEARDOWN
						# Flag the teardownAcked to close the socket.
						self.teardownAcked = 1 

	def writeFrame(self, data):
		"""Write the received frame to a temp image file. Return the image file."""
		cachename = "movie-image" + CACHE_FILE_EXT
		file = open(cachename, "wb")
		file.write(data)
		file.close()
		return cachename
	
	def updateMovie(self, imageFile):
		"""Update the image file as video frame in the GUI."""
		#print("new image file updated")
		try:
			photo = ImageTk.PhotoImage(Image.open(imageFile))
			self.label.configure(image = photo, height=288) 
			self.label.image = photo
		except:
			couldnshow=1
			#print("couldn't show image")

		
	
	def openRtpPort(self):
		"""Open RTP socket binded to a specified port."""
		# Create a new datagram socket to receive RTP packets from the server
		self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		
		# Set the timeout value of the socket to 0.5sec
		self.rtpSocket.settimeout(0.5)
		
		try:
			# Bind the socket to the address using the RTP port
			self.rtpSocket.bind((self.addrtp, self.portrtp))
			print('\nBind \n')
		except:
			a=1
			#tkMessageBox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' %self.rtpPort)

	def handler(self):
		"""Handler on explicitly closing the GUI window."""
		self.pauseMovie()
		if tkMessageBox.askokcancel("Quit?", "Are you sure you want to quit?"):
			self.exitClient()
		else: # When the user presses cancel, resume playing.
			self.playMovie()
