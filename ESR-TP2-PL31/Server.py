import sys, socket
import json
from ServerWorker import ServerWorker
from VideoStream import VideoStream
from RtpPacket import RtpPacket
import time
import threading
import os

received = False

class Server:	

	# SERVER SENDS UNICAST MESSAGE WITH CONTENTS,TIMESTAMP, AND STATE TO RP
	# IT SENDS PERIODICALLY 30s
	def unicastRP(host,port,conteudos,ipdestRP,portRP):
		while True:
			with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
				s.connect((ipdestRP, portRP))
				try:
					print("sending unicast...")
					timestamp = time.time_ns()
					info = json.dumps({"fonte":host,"port":port, "timestamp": timestamp , "conteudos":conteudos, "Estado": "Ativo" })
					print(info)
					msg = info.encode('utf-8')
					s.sendall(msg)
				except Exception as e:
					a=1
				time.sleep(10)


	def waitforsend(HOST):
		with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
			s.bind((HOST, 7778))
			s.listen()
			conn, addr = s.accept()
			with conn:
				data = conn.recv(1024)
				if(data):
					Server.sendVideo(data.decode('utf-8'), '10.0.4.1', 7777)

	# SEND RTP PACKETS WITH VIDEO CONTENT IN FRAMES TO RP
	def sendVideo(video,destIP,destPort):
		path = os.getcwd()+"/"+video
		vs = VideoStream(path,0)
		videodata = vs.nextFrame()
		if(videodata):
			with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as rp_socket:
				try:
					rp_socket.connect((destIP, destPort))
					while videodata:
						numeroframe = vs.frameNbr()
						#print(str(numeroframe))
						rp_socket.sendall(Server.makeRtp(videodata, numeroframe))
						videodata = vs.nextFrame()
						time.sleep(0.1)
				except Exception as e:
					failed=1

	# BUILD RTP PACKET
	def makeRtp(payload, frameNbr):
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