from tkinter import *
import tkinter.messagebox
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os
from RtpPacket import RtpPacket

import datetime

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"

class Client:
	SETUP_STR = 'SETUP'
	PLAY_STR = 'PLAY'
	PAUSE_STR = 'PAUSE'
	TEARDOWN_STR = 'TEARDOWN'
	DESCRIBE_STR = 'DESCRIBE'
	PROCESS_STR = 'PROCESS'

	INIT = 0
	READY = 1
	PLAYING = 2
	PROCESSING = 3
	state = INIT
	
	SETUP = 0
	PLAY = 1
	PAUSE = 2
	TEARDOWN = 3
	PROCESS = 4
	DESCRIBE = 5

	RTSP_VER = "RTSP/1.0"
	TRANSPORT = "RTP/UDP"
	
	# Initiation..
	def __init__(self, master, serveraddr, serverport, rtpport, filename):
		self.master = master
		self.master.protocol("WM_DELETE_WINDOW", self.handler)
		self.createWidgets()
		self.serverAddr = serveraddr
		self.serverPort = int(serverport)
		self.rtpPort = int(rtpport)
		self.fileName = filename
		self.rtspSeq = 0
		self.sessionId = 0
		self.requestSent = -1
		self.teardownAcked = 0
		self.connectToServer()
		self.frameNbr = 0

		self.totalFrame = 0
		self.totalReceivedFrame = 0
		self.numLostFrame = 0
		self.totalReceivedData = 0
		self.setupMovie()
		
	# THIS GUI IS JUST FOR REFERENCE ONLY, STUDENTS HAVE TO CREATE THEIR OWN GUI 	
	def createWidgets(self):
		"""Build GUI."""
		# Create Setup button
		# self.setup = Button(self.master, width=20, padx=3, pady=3)
		# self.setup["text"] = "Setup"
		# self.setup["command"] = self.setupMovie
		# self.setup.grid(row=1, column=0, padx=2, pady=2)
		
		# Create Play button		
		self.start = Button(self.master, width=20, padx=3, pady=3)
		self.start["text"] = "Play"
		self.start["command"] = self.playMovie
		self.start.grid(row=1, column=1, padx=2, pady=2)
		
		# Create Pause button			
		self.pause = Button(self.master, width=20, padx=3, pady=3)
		self.pause["text"] = "Pause"
		self.pause["command"] = self.pauseMovie
		self.pause.grid(row=1, column=2, padx=2, pady=2)
		
		# Create Teardown button
		self.teardown = Button(self.master, width=20, padx=3, pady=3)
		self.teardown["text"] = "Teardown"
		self.teardown["command"] =  self.exitClient
		self.teardown.grid(row=1, column=3, padx=2, pady=2)
		
		# Create a label to display the movie
		self.label = Label(self.master, height=19)
		self.label.grid(row=0, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5) 

		self.total = Label(self.master, height=2)
		self.total.grid(row=2, column=4, padx=2, pady=2)
		self.total.configure(text=str(datetime.timedelta(seconds=0)))

		self.currFrame = Label(self.master, height=2)
		self.currFrame.grid(row=2, column=0, padx=2, pady=2)
		self.currFrame.configure(text=str(datetime.timedelta(seconds=0)))

		self.scale = Scale(self.master, from_=0, to=200, orient=HORIZONTAL, length=200)
		self.scale.grid(row=2, column=1, columnspan=2, padx=2, pady=2)

		self.syncTime = Button(self.master, width=20, padx=3, pady=3)
		self.syncTime["text"]= "Sync"
		self.syncTime["command"] = self.sync
		self.syncTime.grid(row=2, column=3, padx=2, pady=2)
	
		#Create describe button
		self.describe = Button(self.master, width=20, padx=3, pady=3)
		self.describe["text"] = "Describe"
		self.describe["command"] =  self.describeVideo
		self.describe.grid(row=1, column=0, padx=2, pady=2)
# Giai đoạn 1#
# ##################################
	def setupMovie(self):
		"""Setup button handler."""
		if self.state == self.INIT:
			self.sendRtspRequest(self.SETUP)
	
	def exitClient(self):
		"""Teardown button handler."""
		self.sendRtspRequest(self.TEARDOWN)
		self.master.destroy()
		os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT)

	def pauseMovie(self):
		"""Pause button handler."""
		if self.state == self.PLAYING:
			self.sendRtspRequest(self.PAUSE)
	
	def playMovie(self):
		"""Play button handler."""
		if self.state == self.READY:
			# tao 1 luong moi de nghe goi RTP
			threading.Thread(target=self.listenRtp).start()
			self.playEvent = threading.Event()
			self.playEvent.clear()
			self.sendRtspRequest(self.PLAY)
	
	def moveToFrame(self, value):
		nextFrame = int(int(value) * self.totalFrame / 200)
		minDiff = int(self.totalFrame / 200)
		if abs(nextFrame - self.frameNbr)>=minDiff and self.state == self.READY:
			self.sendRtspRequest(self.PROCESS, nextFrame)
			self.state = self.PROCESSING
			self.totalReceivedFrame += (self.frameNbr - nextFrame)
			self.frameNbr = nextFrame

	def sync(self):
		value = self.scale.get()
		self.moveToFrame(value)

	def describeVideo(self):
		self.sendRtspRequest(self.DESCRIBE)
	
#Giai đoạn 2#
############################
	def listenRtp(self):		
		"""Listen for RTP packets."""
		#TODO
		while True:
			try:
				print("LISTENING...")
				data = self.rtpSocket.recv(20480)
				if data:
					rtpPacket = RtpPacket()
					rtpPacket.decode(data)
					
					currFrameNbr = rtpPacket.seqNum()
					print ("CURRENT SEQUENCE NUM: " + str(currFrameNbr))
										
					if currFrameNbr > self.frameNbr: # Discard the late packet
						self.numLostFrame += (currFrameNbr - self.frameNbr - 1)
						self.frameNbr = currFrameNbr
						self.totalReceivedData += len(rtpPacket.getPayload())
						self.updateMovie(self.writeFrame(rtpPacket.getPayload()))
			except:
				# Stop listening upon requesting PAUSE or TEARDOWN
				if self.playEvent.isSet(): 
					break
				
				# Upon receiving ACK for TEARDOWN request,
				# close the RTP socket
				if self.teardownAcked == 1:
					self.rtpSocket.shutdown(socket.SHUT_RDWR)
					self.rtpSocket.close()
					break
					
	def writeFrame(self, data):
		"""Write the received frame to a temp image file. Return the image file."""
		cachefile=CACHE_FILE_NAME+str(self.sessionId) +CACHE_FILE_EXT
		file= open(cachefile,"wb")
		file.write(data)
		file.close()
		return cachefile
	
	def updateMovie(self, imageFile):
		"""Update the image file as video frame in the GUI."""
		photo = ImageTk.PhotoImage(Image.open(imageFile))
		self.label.configure(image = photo, height=288) 
		self.label.image = photo
		#update current time
		currTime = int(self.frameNbr / self.fps)
		self.currFrame.configure(text=str(datetime.timedelta(seconds=currTime)))
		self.scale.set(int(200 * self.frameNbr / self.totalFrame))
	
		
	def connectToServer(self):
		"""Connect to the Server. Start a new RTSP/TCP session."""
		self.rtspSocket=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
		try:
			self.rtspSocket.connect((self.serverAddr,self.serverPort))
		except:
			tkinter.messagebox.showwarning("Connection failed","Connection to \'%s\' failed." %self.serverAddr)

	
	
	def sendRtspRequest(self, requestCode,value=0):
		"""Send RTSP request to the server."""	
		#-------------
		# TO COMPLETE
		#-------------
		if requestCode== self.SETUP and self.state==self.INIT:
			threading.Thread(target=self.recvRtspReply).start()
			#update sequence number RTSP
			self.rtspSeq+=1
			#Sent request
			request="%s %s %s" % (self.SETUP_STR,self.fileName,self.RTSP_VER)
			request+="\nCSeq: %d" % self.rtspSeq
			request+="\nTransport: %s; client_port= %d" % (self.TRANSPORT,self.rtpPort)
			self.requestSent=self.SETUP
		#play
		elif requestCode==self.PLAY and self.state==self.READY:
			self.rtspSeq+=1
			request="%s %s %s" % (self.PLAY_STR,self.fileName,self.RTSP_VER)
			request+="\nCSeq: %d" % self.rtspSeq
			request+="\nSession %d" % self.sessionId
			self.requestSent=self.PLAY
		#pause
		elif requestCode==self.PAUSE and self.state==self.PLAYING:
			self.rtspSeq+=1
			request="%s %s %s" % (self.PAUSE_STR,self.fileName,self.RTSP_VER)
			request+="\nCSeq: %d" % self.rtspSeq
			request+="\nSession: %d" % self.sessionId
			self.requestSent=self.PAUSE
		#teardown
		elif requestCode == self.TEARDOWN and not self.state== self.INIT:
			self.rtspSeq+=1
			request="%s %s %s" %(self.TEARDOWN_STR,self.fileName,self.RTSP_VER)
			request+="\nCSeq: %d " % self.rtspSeq
			request+="\nSession: %d" % self.sessionId
			self.requestSent=self.TEARDOWN
		elif requestCode == self.PROCESS and self.state == self.READY:
			# Update RTSP sequence number.
			self.rtspSeq+=1

			# Write the RTSP request to be sent.
			request = "%s %s %s" % (self.PROCESS_STR, self.fileName, self.RTSP_VER)
			request+="\nCSeq: %d" % self.rtspSeq
			request+="\nSession: %d" % self.sessionId
			request+="\nFrameNum: %d" %  value

			self.requestSent = self.PROCESS
		
		elif requestCode == self.DESCRIBE and self.state == self.READY:
			request = "%s %s %s" % (self.DESCRIBE_STR,self.fileName, self.RTSP_VER)
			request+="\nCSeq: %d" % self.rtspSeq
			request+="\nSession: %d" % self.sessionId
			request+="\nFrameNum: %d" %  value
		else:
			return
		
		#send RTSP request by rtspsocket
		self.rtspSocket.send(request.encode())
		print('\nData Sent:\n'+ request)
	
	
	def recvRtspReply(self):
		"""Receive RTSP reply from the server."""
		while True:
			reply = self.rtspSocket.recv(1024)
			
			if reply: 
				self.parseRtspReply(reply)
			
			# Close the RTSP socket upon requesting Teardown
			if self.requestSent == self.TEARDOWN:
				self.rtspSocket.shutdown(socket.SHUT_RDWR)
				self.rtspSocket.close()
				self.totalReceivedFrame -= (self.totalFrame - self.frameNbr)
				packLostRate = float(self.numLostFrame)/float(self.totalReceivedFrame)
				print ("RTP packet loss rate: ", packLostRate, "%")
				videoDataRate = float(self.totalReceivedData) / ((self.totalReceivedFrame - self.numLostFrame) / self.fps)
				print ("Video data rate", videoDataRate, " Bytes per second")
				break
		#TODO
	
	def parseRtspReply(self, data):
		"""Parse the RTSP reply from the server."""
		lines = data.decode().split('\n')
		seqNum = int(lines[1].split(' ')[1])

		# Process only if the server reply's sequence number is the same as the request's
		if seqNum == self.rtspSeq:
			session = int(lines[2].split(' ')[1])
			# New RTSP session ID
			if self.sessionId == 0:
				self.sessionId = session

			# Process only if the session ID is the same
			if self.sessionId == session:
				if int(lines[0].split(' ')[1]) == 200:
					if self.requestSent == self.SETUP:
						# Update RTSP state.
						self.state = self.READY

						# Open RTP port.
						self.openRtpPort()

						# update Fps and total frame
						self.totalFrame = int(lines[3])
						self.totalReceivedFrame = self.totalFrame
						self.fps = int(lines[4])
						totalTime= int(self.totalFrame / self.fps)
						self.total.configure(text=str(datetime.timedelta(seconds=totalTime)))
					elif self.requestSent == self.PLAY:
						self.state = self.PLAYING
					elif self.requestSent == self.PAUSE:
						self.state = self.READY
                        
						# The play thread exits. A new thread is created on resume.
						self.playEvent.set()
					elif self.requestSent == self.TEARDOWN:
						self.state = self.INIT

						# Flag the teardownAcked to close the socket.
						self.teardownAcked = 1
					elif self.requestSent == self.PROCESS:
						self.state = self.READY
		#TODO
	
	def openRtpPort(self):
		"""Open RTP socket binded to a specified port."""
		#-------------
		# TO COMPLETE
		#-------------
		# Create a new datagram socket to receive RTP packets from the server
		# self.rtpSocket = ...
		
		# Set the timeout value of the socket to 0.5sec
		# ...
		self.rtpSocket =socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
		self.rtpSocket.settimeout(0.5)
		try:
			self.state=self.READY
			self.rtpSocket.bind(('',self.rtpPort))
		except:
			tkinter.messagebox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' % self.rtpPort)
		

	def handler(self):
		"""Handler on explicitly closing the GUI window."""
		flag=0
		if self.state==self.PLAYING:
			self.pauseMovie()
			flag=1
		if tkinter.messagebox.askokcancel("Quit?", "Are you sure you want to quit?"):
			self.exitClient()
		else: # When the user presses cancel, resume playing.
			if flag == 1:
				self.playMovie()
			else:
				self.pauseMovie()
