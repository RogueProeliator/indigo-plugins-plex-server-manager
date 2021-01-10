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
import requests
import datetime
import time
import urllib2
import xml.etree.ElementTree

import indigo
from plexapi.myplex import MyPlexAccount 
from plexapi.server import PlexServer

import RPFramework
import plexMediaContainer 


#/////////////////////////////////////////////////////////////////////////////////////////
# Constants and Enumerations
#/////////////////////////////////////////////////////////////////////////////////////////
PLEX_CMD_DOWNLOAD_CURRENT_ART = u'downloadCurrentlyPlayingArt'


#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
# PlexMediaServerDefinition
#	Handles the configuration of a single Plex Media Server... and acts as a parent device
#	for all the subsequent library and client child devices
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
class PlexMediaServer(RPFramework.RPFrameworkRESTfulDevice.RPFrameworkRESTfulDevice):
	
	#/////////////////////////////////////////////////////////////////////////////////////
	# Class construction and destruction methods
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# Constructor called once upon plugin class receiving a command to start device
	# communication. The plugin will call other commands when needed, simply zero out the
	# member variables
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def __init__(self, plugin, device):
		super(PlexMediaServer, self).__init__(plugin, device)
		
		# this server member variable will be created during the initial login/security
		# token phase of the device processing
		self.plexServer = None

		# we will store the list of last clients found so that any dialog box may
		# instantly retrieve them
		self.currentClientList = list()
		
		# we do not need to be quite as interactive as some plugins... so increase the wait
		# time when the queue is empty
		self.emptyQueueProcessingThreadSleepTime = 0.20
		
		# add in updated/new states and properties
		self.upgradedDeviceProperties.append((u'requestMethod', u'http')) 
		self.upgradedDeviceProperties.append((u'loginRequired', u'False')) 
		self.upgradedDeviceProperties.append((u'plexUsername', u'')) 
		self.upgradedDeviceProperties.append((u'plexPassword', u'')) 
		
		self.upgradedDeviceStates.append(u'serverIdentifier')
		self.upgradedDeviceStates.append(u'serverName')
		
		
	#/////////////////////////////////////////////////////////////////////////////////////
	# RESTful device overloads
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine should return the HTTP address that will be used to connect to the
	# RESTful device. It may connect via IP address or a host name
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def getRESTfulDeviceAddress(self):
		if self.plexServer == None:
			return (self.indigoDevice.pluginProps.get(u'httpAddress', u''), int(self.indigoDevice.pluginProps.get(u'httpPort', u'80')))
		else:
			return self.plexServer.baseurl
		
		
	#/////////////////////////////////////////////////////////////////////////////////////
	# Action Callbacks and Handlers
	#/////////////////////////////////////////////////////////////////////////////////////	
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine should be overridden in individual device classes whenever they must
	# handle custom commands that are not already defined
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def handleUnmanagedCommandInQueue(self, deviceHTTPAddress, rpCommand):
		if rpCommand.commandName == u'updateServerStatusFull':
			#self.retrieveSecurityToken()
			pass
					
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will be called prior to any network operation to allow the addition
	# of custom headers to the request (does not include file download)
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def addCustomHTTPHeaders(self, httpRequestHeaders):
		if self.plexSecurityToken != u'':
			httpRequestHeaders[u'X-Plex-Token'] = self.plexSecurityToken
			self.hostPlugin.logger.threaddebug(u'Added authentication token to request')
			
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will handle an error as thrown by the REST call... it allows 
	# descendant classes to do their own processing
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-		
	def handleRESTfulError(self, rpCommand, err, response=None):
		if rpCommand != None and rpCommand.commandName == u'updateServerStatusFull' and not response is None:
			# this could be an authorization issue...
			if response.status_code == 401 and self.plexSecurityToken != u'':
				self.plexSecurityToken = u''
				self.hostPlugin.logger.debug(u'Invalidating security token due to unauthorized response from status request')
				return
		super(PlexMediaServer, self).handleRESTfulError(rpCommand, err, response)
					
	
	#/////////////////////////////////////////////////////////////////////////////////////
	# Utility Routines
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will gather a list of all of the clients connected to the media server
	# for use in a menu / config dialog. It will ensure the passed-in value is always
	# present
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def retrieveCurrentClientMenu(self, selectedClient = u''):
		# retrieve the last set of connected clients that were retrieved from the Plex server
		currentClients = self.currentClientList
		
		# ensure that the selected client ID was found
		if selectedClient != u'':
			selectedClientFound = False
			for client in currentClients:
				if client[0] == selectedClient:
					selectedClientFound = True
							
			if selectedClientFound == False:
				currentClients.append((selectedClient, selectedClient))
		
		return currentClients
	
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will gather generate a menu of slots available for "generic" clients
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def retrieveCurrentClientSlotMenu(self):
		currentClients = []
	
		# append the "generic slots" to the list
		for slotNum in range(1,11):
			currentClients.append(("Slot " + RPFramework.RPFrameworkUtils.to_unicode(slotNum), "Slot " + RPFramework.RPFrameworkUtils.to_unicode(slotNum)))
		
		return currentClients
		
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will attempt to obtain the Plex security token from the Plex service
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def retrieveSecurityToken(self):
		# we need to obtain a security token from the plex website in order to_unicode
		# access the plex server; if we already have a security token this may be skipped
		if self.plexSecurityToken == u'':
			plexHeaders = {u'X-Plex-Platform':u'Indigo', u'X-Plex-Platform-Version':indigo.server.apiVersion, u'X-Plex-Provides':u'controller', u'X-Plex-Client-Identifier':indigo.server.getDbName(), u'X-Plex-Product':u'Plex Media Server Manager', u'X-Plex-Version':self.hostPlugin.pluginVersion, u'X-Plex-Device':u'Indigo HA Server', u'X-Plex-Device-Name':u'Indigo Plugin'}
			
			responseObj = requests.post(u'https://plex.tv/users/sign_in.xml', headers=plexHeaders, auth=(self.indigoDevice.pluginProps.get(u'plexUsername', u''), self.indigoDevice.pluginProps.get(u'plexPassword', u'')))
			self.hostPlugin.logger.threaddebug(u'Plex.tv Sign-In Response: [' + RPFramework.RPFrameworkUtils.to_unicode(responseObj.status_code) + u'] ' + RPFramework.RPFrameworkUtils.to_unicode(responseObj.text))
			self.hostPlugin.logger.threaddebug(u'Plex.tv Sign-In Response Headers: ' + RPFramework.RPFrameworkUtils.to_unicode(responseObj.headers))
			
			# if successful, this should be a 201 response (Created)
			if responseObj.status_code == 201:
				# the response will be an XML return...
				authenticationXml = xml.etree.ElementTree.fromstring(RPFramework.RPFrameworkUtils.to_str(responseObj.text))
				authTokenNode = authenticationXml.find(u'authentication-token')
				self.plexSecurityToken = authTokenNode.text
				self.hostPlugin.logger.debug(u'Successfully obtained plex.tv authentication token')
			else:
				self.plexSecurityToken = u''
				self.hostPlugin.logger.error(u'Failed to obtain authentication token from plex.tv site.')
			
			
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
# PlexMediaClient
#	Handles the configuration and states of a client which connects to the Plex Media
#	server for consuming media
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
class PlexMediaClient(RPFramework.RPFrameworkNonCommChildDevice.RPFrameworkNonCommChildDevice):

	#/////////////////////////////////////////////////////////////////////////////////////
	# Class construction and destruction methods
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# Constructor called once upon plugin class receiving a command to start device
	# communication. The plugin will call other commands when needed, simply zero out the
	# member variables
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def __init__(self, plugin, device):
		super(PlexMediaClient, self).__init__(plugin, device)
		
		self.clientCommandID = 0
		
		self.upgradedDeviceStates.append(u'currentlyPlayingParentThumbnailUrl')
		self.upgradedDeviceStates.append(u'currentlyPlayingGrandparentArtUrl')
		self.upgradedDeviceStates.append(u'currentlyPlayingSummary')
		self.upgradedDeviceStates.append(u'playerDeviceTitle')
		self.upgradedDeviceStates.append(u'currentlyPlayingContentLengthDisplay')
		self.upgradedDeviceStates.append(u'currentlyPlayingContentLengthOffsetDisplay')
		self.upgradedDeviceStates.append(u'currentlyPlayingParentTitle')
		self.upgradedDeviceStates.append(u'currentlyPlayingGrandparentTitle')
		self.upgradedDeviceStates.append(u'currentlyPlayingGenre')
		self.upgradedDeviceStates.append(u'clientAddress')
		self.upgradedDeviceStates.append(u'clientPort')
		self.upgradedDeviceStates.append(u'currentlyPlayingParentKey')
		self.upgradedDeviceStates.append(u'currentlyPlayingGrandparentKey')
		self.upgradedDeviceStates.append(u'currentlyPlayingKey')
		
	#/////////////////////////////////////////////////////////////////////////////////////
	# Utility methods
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# Returns the command ID to use when sending commands to the client player
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def getClientCommandID(self):
		self.clientCommandID += 1
		return self.clientCommandID
		