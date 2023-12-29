import os
import re
from random import randint
import sys, traceback, threading, socket
import json
from VideoStream import VideoStream
from RtpPacket import RtpPacket
import threading

class ServerWorker:
	SETUP = 0
	PLAY = 1
	PAUSE = 2
	TEARDOWN = 3
	
	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT

	OK_200 = 0
	FILE_NOT_FOUND_404 = 1
	CON_ERR_500 = 2
	
	clientInfo = {}
	
	def __init__(self, clientInfo):
		self.data_lock = threading.Lock()
		self.clientInfo = clientInfo
		self.numeroframe = 0
		self.allRTP = []
		self.streaming = False

	def storeRTP(packet):
		self.allRTP.append(d)

	def setonStreaming():
		self.streaming = True

	def run(self):
		threading.Thread(target=self.recvRtspRequest).start()
	
	def recvRtspRequest(self):
		"""Receive RTSP request from the client."""
		connSocket = self.clientInfo['rtspSocket'][0]
		while True:
			data = connSocket.recv(256)
			if data:
				#print("Data received:\n" + data.decode("utf-8")) # process data received from client
				self.processRtspRequest(data.decode("utf-8"))
	
	def processRtspRequest(self, data):
		"""Process RTSP request sent from the client."""
		#REQUEST JSON
		request_data = json.loads(data)
		print(data)
		# Get the request type
		#request = request_data["Type"]
		#line1 = request[0].split(' ')
		self.requestType = request_data["Type"]
		
		# Get the media file name
		filename = request_data["Video"]
		path = os.getcwd()+"/"+filename
		# Get the RTSP sequence number 
		seq = request_data["Seq"]
		
		# Process SETUP request
		if self.requestType == self.SETUP:
			if self.state == self.INIT:
				# Update state
				print("PROCESSING SETUP\n")
				
				try:
					self.clientInfo['videoStream'] = VideoStream(path,self.numeroframe)
					self.state = self.READY
					print("SETUP DONE\n")
				except IOError:
					self.replyRtsp(self.FILE_NOT_FOUND_404, seq)
				
				# Generate a randomized RTSP session ID
				self.clientInfo['session'] = randint(100000, 999999)
				
				# Send RTSP reply
				self.replyRtsp(self.OK_200, seq)
				
				# Get the RTP/UDP port from the last line
				self.clientInfo['rtpPort'] = request_data["Port"]
		
		# Process PLAY request 		
		elif self.requestType == self.PLAY:
			if self.state == self.READY:
				print("PROCESSING PLAY\n")
				self.state = self.PLAYING
				
				# Create a new socket for RTP/UDP
				self.clientInfo["rtpSocket"] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
				
				self.replyRtsp(self.OK_200, seq)
				
				# Create a new thread and start sending RTP packets
				self.clientInfo['event'] = threading.Event()
				self.clientInfo['worker']= threading.Thread(target=self.sendRtp) 
				self.clientInfo['worker'].start()
		
		# Process PAUSE request
		elif self.requestType == self.PAUSE:
			if self.state == self.PLAYING:
				print("PROCESSING PAUSE\n")
				self.state = self.READY

				self.clientInfo['event'].set()

				self.replyRtsp(self.OK_200, seq)
		
		# Process TEARDOWN request
		elif self.requestType == self.TEARDOWN:
			print("processing TEARDOWN\n")

			self.clientInfo['event'].set()
			
			self.replyRtsp(self.OK_200, seq)
			
			# Close the RTP socket
			self.clientInfo['rtpSocket'].close()
			
	def sendRtp(self):
		"""Send RTP packets over UDP."""
		while True:
			self.clientInfo['event'].wait(0.05) 
			
			# Stop sending if request is PAUSE or TEARDOWN
			if self.clientInfo['event'].isSet(): 
				break 

			#data = self.clientInfo['videoStream'].nextFrame()
			self.videodata = self.clientInfo['videoStream'].nextFrame()
			if self.videodata: 
				#frameNumber = self.clientInfo['videoStream'].frameNbr()
				self.numeroframe = self.clientInfo['videoStream'].frameNbr()
				try:
					address = self.clientInfo['rtspSocket'][1][0]
					port = int(self.clientInfo['rtpPort'])
					with self.data_lock:
						self.clientInfo['rtpSocket'].sendto(self.makeRtp(self.videodata, self.numeroframe), (address, port))
				except:
					print("Connection Error")
					#print('-'*60)
					#traceback.print_exc(file=sys.stdout)
					#print('-'*60)

	def makeRtp(self, payload, frameNbr):
		"""RTP-packetize the video data."""
		version = 2
		padding = 0
		extension = 0
		cc = 0
		marker = 0
		pt = 26 # MJPEG type
		seqnum = frameNbr
		ssrc = 0 
		
		rtpPacket = RtpPacket()
		
		rtpPacket.encode(version, padding, extension, cc, seqnum, marker, pt, ssrc, payload)
		
		return rtpPacket.getPacket()
		
	def replyRtsp(self, code, seq):
		"""Send RTSP reply to the client."""
		if code == self.OK_200:
			#print("200 OK")
			reply = 'RTSP/1.0 200 OK\nCSeq: ' + str(seq) + '\nSession: ' + str(self.clientInfo['session'])
			connSocket = self.clientInfo['rtspSocket'][0]
			connSocket.send(reply.encode())
		
		# Error messages
		elif code == self.FILE_NOT_FOUND_404:
			print("404 NOT FOUND")
		elif code == self.CON_ERR_500:
			print("500 CONNECTION ERROR")
