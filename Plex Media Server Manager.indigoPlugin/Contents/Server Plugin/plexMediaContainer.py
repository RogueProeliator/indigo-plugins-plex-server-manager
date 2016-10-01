#! /usr/bin/env python
# -*- coding: utf-8 -*-
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
# Plex Server Manager by RogueProeliator <rp@rogueproeliator.com>
# 	See plugin.py for more plugin details and information
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////

#/////////////////////////////////////////////////////////////////////////////////////////
# Python imports
#/////////////////////////////////////////////////////////////////////////////////////////
import httplib
import re
import time
import urllib2
import xml.etree.ElementTree
import indigo
import RPFramework


#/////////////////////////////////////////////////////////////////////////////////////////
# Constants
#/////////////////////////////////////////////////////////////////////////////////////////
MEDIACONTAINERTYPE_UNKNOWN = 0
MEDIACONTAINERTYPE_SERVERNODE = 1
MEDIACONTAINERTYPE_CLIENTLIST = 2
MEDIACONTAINERTYPE_SESSIONLIST = 3


#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
# PlexMediaContainer
#	Handles the XML-based MediaContainer element that all of the Plex Media Server API
#	calls return
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
class PlexMediaContainer(object):
	
	#/////////////////////////////////////////////////////////////////////////////////////
	# Class construction and destruction methods
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# Constructor allows passing in the XML data that has a MediaContainer at its root
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def __init__(self, mediaContainerXml, plexContainerPath):
		# setup the basic properties that we will populate for external use
		self.containerAttributes = dict()
		self.directories = list()
		self.clients = list()
		self.videoSessions = list()
		
		# based upon what information we have, we should be able to determine what type of information
		# is being stored in the dictionary...
		if plexContainerPath == u'/':
			self.containerType = MEDIACONTAINERTYPE_SERVERNODE
		elif plexContainerPath == u'/clients':
			self.containerType = MEDIACONTAINERTYPE_CLIENTLIST
		elif plexContainerPath == u'/status/sessions':
			self.containerType = MEDIACONTAINERTYPE_SESSIONLIST
		else:
			self.containerType = MEDIACONTAINERTYPE_UNKNOWN
	
		# parse the XML provided...
		mediaContainerNode = xml.etree.ElementTree.fromstring(RPFramework.RPFrameworkUtils.to_str(mediaContainerXml))
		
		# the root container node will have a bunch of attributes which should be loaded into
		# our attributes container
		for key,value in mediaContainerNode.items():
			self.containerAttributes[key] = value
		
		# retrieve the list of directories that may be content of the media container
		# node
		for directoryNode in mediaContainerNode.findall(u'Directory'):
			self.directories.append(PlexMediaContainerDirectory(directoryNode))
			
		# retrieve the list of clients that may be content of the media container
		# node (these are connected clients, not necessarily streaming now)
		if self.containerType == MEDIACONTAINERTYPE_CLIENTLIST:
			for clientNode in mediaContainerNode.findall(u'Server'):
				self.clients.append(PlexMediaClient(clientNode))
			
		# the session status requires special handling - it will have a Video node along with
		# embedded player and media information nodes
		if self.containerType == MEDIACONTAINERTYPE_SESSIONLIST:
			for video in mediaContainerNode.findall(u'Video'):
				self.videoSessions.append(PlexMediaContainerVideoSession(video))
			for audio in mediaContainerNode.findall(u'Track'):
				self.videoSessions.append(PlexMediaContainerVideoSession(audio))
		
		
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
# PlexMediaContainerDirectory
#	Stores information about a "directory" element within the Plex API... this is
#	basically anything that can be drilled deeper into its hierarchy
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
class PlexMediaContainerDirectory(object):
		
	#/////////////////////////////////////////////////////////////////////////////////////
	# Class construction and destruction methods
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# Constructor allows passing in the XML node of which the directory is its root
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def __init__(self, dictionaryXmlNode):
		# we will keep a copy of the attributes of the dictionary as these are essentially
		# "properties" of the object
		self.dictionaryAttributes = dict()
		
		# the root container node will have a bunch of attributes which should be loaded into
		# our attributes container
		for key,value in dictionaryXmlNode.items():
			self.dictionaryAttributes[key] = value

			

#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
# PlexMediaClient
#	Stores information about a "Server" element within the Plex API... this is
#	basically a connected client
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
class PlexMediaClient(object):
		
	#/////////////////////////////////////////////////////////////////////////////////////
	# Class construction and destruction methods
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# Constructor allows passing in the XML node of which the directory is its root
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def __init__(self, serverXmlNode):
		# we will keep a copy of the attributes of the dictionary as these are essentially
		# "properties" of the object
		self.clientAttributes = dict()
		
		# the root container node will have a bunch of attributes which should be loaded into
		# our attributes container
		loadXmlElementToDictionary(serverXmlNode, self.clientAttributes)
		
	
	#/////////////////////////////////////////////////////////////////////////////////////
	# Public Utilities
	#/////////////////////////////////////////////////////////////////////////////////////
	def getClientId(self):
		return RPFramework.RPFrameworkUtils.to_unicode(self.clientAttributes["machineIdentifier"] if "machineIdentifier" in self.clientAttributes else "")
	
	def getClientName(self):
		return RPFramework.RPFrameworkUtils.to_unicode(self.clientAttributes["product"] if "product" in self.clientAttributes else "")
		
	def getClientAddress(self):
		return RPFramework.RPFrameworkUtils.to_unicode(self.clientAttributes["address"] if "address" in self.clientAttributes else "")
		
	def getClientPort(self):
		return int(RPFramework.RPFrameworkUtils.to_unicode(self.clientAttributes["port"] if "port" in self.clientAttributes else "0"))



#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
# PlexMediaContainerVideo
#	Stores information about a video that is being served in-session (as obtained from
#	the session status request)
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
class PlexMediaContainerVideoSession(object):
	
	#/////////////////////////////////////////////////////////////////////////////////////
	# Class construction and destruction methods
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# Constructor allows passing in the XML node of which the video is its root
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def __init__(self, videoXmlNode):
		self.videoAttributes = dict()
		self.userInfo = dict()
		self.playerInfo = dict()
		self.mediaInfo = dict()
		
		# the root Video node will have a bunch of attributes which should be loaded into
		# our attributes container
		loadXmlElementToDictionary(videoXmlNode, self.videoAttributes)
			
		# there may be a "User" node if the session is not an anonymous session; if so then
		# load all of the user's details into our user dictionary
		userXmlNode = videoXmlNode.find("User")
		if not userXmlNode is None:
			loadXmlElementToDictionary(userXmlNode, self.userInfo)
				
		# there should be a Player node that identifies what client/player is doing the
		# streaming... load all of its properties in the appropriate dictionary
		playerXmlNode = videoXmlNode.find("Player")
		if not playerXmlNode is None:
			loadXmlElementToDictionary(playerXmlNode, self.playerInfo)
			
		# there may be specific media information that we should read
		mediaXmlNode = videoXmlNode.find("Media")
		if not mediaXmlNode is None:
			loadXmlElementToDictionary(mediaXmlNode, self.mediaInfo)
				
				
				
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
# Static Utility Routines
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
def loadXmlElementToDictionary(xmlElement, targetDict):
	for key,value in xmlElement.items():
		targetDict[key] = value
