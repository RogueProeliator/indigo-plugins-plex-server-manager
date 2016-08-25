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
import datetime
import time
import urllib2
import xml.etree.ElementTree

import indigo
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
		
		# we will store the list of last clients found so that any dialog box may
		# instantly retrieve them
		self.currentClientList = list()
		
		# we do not need to be quite as interactive as some plugins... so increase the wait
		# time when the queue is empty
		self.emptyQueueProcessingThreadSleepTime = 0.20
		
		# these variables store the data sent/obtained from the plex.tv servers whenever
		# the user desires to require authentication on the server
		self.plexSecurityToken = u''
		
		# add in updated/new states and properties
		self.upgradedDeviceProperties.append((u'requestMethod', u'http')) 
		self.upgradedDeviceProperties.append((u'loginRequired', u'False')) 
		self.upgradedDeviceProperties.append((u'plexUsername', u'')) 
		self.upgradedDeviceProperties.append((u'plexPassword', u'')) 
		
		
	#/////////////////////////////////////////////////////////////////////////////////////
	# RESTful device overloads
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine should return the HTTP address that will be used to connect to the
	# RESTful device. It may connect via IP address or a host name
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def getRESTfulDeviceAddress(self):
		return (self.indigoDevice.pluginProps.get(u'httpAddress', u''), int(self.indigoDevice.pluginProps.get(u'httpPort', u'80')))
		
		
	#/////////////////////////////////////////////////////////////////////////////////////
	# Action Callbacks and Handlers
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will be called in order to handle a valid return from the PMS which
	# should be a MediaContainer-based XML return
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def handlePlexMediaContainerResult(self, responseObj, rpCommand):
		# this should be a valid return to have made it here since this will be called as an
		# effect and not during initial request processing; the obj should be a string
		plexContainer = plexMediaContainer.PlexMediaContainer(responseObj, rpCommand.getPayloadAsList()[1])
		self.hostPlugin.logDebugMessage(u'MediaContainer Information: ' + RPFramework.RPFrameworkUtils.to_unicode(plexContainer.containerAttributes), RPFramework.RPFrameworkPlugin.DEBUGLEVEL_MED)
		
		# assuming this is the primary command then we need to update the current state information
		# of this device
		if plexContainer.containerType == plexMediaContainer.MEDIACONTAINERTYPE_SERVERNODE:
			self.indigoDevice.updateStateOnServer(key=u'connectionState', value=u'Connected')
			self.indigoDevice.updateStateOnServer(key=u'serverVersion', value=plexContainer.containerAttributes["version"])
			self.indigoDevice.updateStateOnServer(key=u'transcoderActiveVideoSessions', value=plexContainer.containerAttributes["transcoderActiveVideoSessions"])
		elif plexContainer.containerType == plexMediaContainer.MEDIACONTAINERTYPE_CLIENTLIST:
			pass
		elif plexContainer.containerType == plexMediaContainer.MEDIACONTAINERTYPE_SESSIONLIST:
			self.indigoDevice.updateStateOnServer(key=u'activeSessionsCount', value=int(plexContainer.containerAttributes["size"]))
			self.hostPlugin.logDebugMessage(u'Found ' + RPFramework.RPFrameworkUtils.to_unicode(len(plexContainer.videoSessions)) + u' active video sessions', RPFramework.RPFrameworkPlugin.DEBUGLEVEL_MED)
			
			# update the status of any child client devices that are currently streaming; we also need to update
			# the list of available clients for the config dialog boxes
			newClientList = list()
			connectedClientHash = dict()
			slotNum = 0
			for session in plexContainer.videoSessions:
				slotNum = slotNum + 1
				
				# output debug information
				self.hostPlugin.logDebugMessage(u'MediaContainer Media Information: ' + RPFramework.RPFrameworkUtils.to_unicode(session.mediaInfo), RPFramework.RPFrameworkPlugin.DEBUGLEVEL_MED)
				self.hostPlugin.logDebugMessage(u'MediaContainer Player Information: ' + RPFramework.RPFrameworkUtils.to_unicode(session.playerInfo), RPFramework.RPFrameworkPlugin.DEBUGLEVEL_MED)
				self.hostPlugin.logDebugMessage(u'Identified as Slot ' + RPFramework.RPFrameworkUtils.to_unicode(slotNum), RPFramework.RPFrameworkPlugin.DEBUGLEVEL_MED)
			
				# retrieve the basic identification information about the player which is
				# connected for this session
				playerMachineId = session.playerInfo.get(u'machineIdentifier', u'')
				playerName = session.playerInfo.get(u'title', playerMachineId)
				
				# we only have to update state information if this client is a defined Indigo device or a generic
				# slot has been created
				clientsToProcess = list()
				if playerMachineId in self.childDevices:
					clientsToProcess.append(self.childDevices[playerMachineId])
				slotClientId = u'Slot ' + RPFramework.RPFrameworkUtils.to_unicode(slotNum)
				if slotClientId in self.childDevices:
					clientsToProcess.append(self.childDevices[slotClientId])
				
				# process each of the clients found as a match...
				self.hostPlugin.logDebugMessage(u'Found ' + RPFramework.RPFrameworkUtils.to_unicode(len(clientsToProcess)) + u' clients to update', RPFramework.RPFrameworkPlugin.DEBUGLEVEL_MED)
				for clientDevice in clientsToProcess:
					self.hostPlugin.logDebugMessage(u'Found client device to update for machineID: ' + playerMachineId, RPFramework.RPFrameworkPlugin.DEBUGLEVEL_MED)
					clientDevice.indigoDevice.updateStateOnServer(key=u'clientConnectionStatus', value=session.playerInfo.get(u'state', u'connected'))
					clientDevice.indigoDevice.updateStateOnServer(key=u'currentUser', value=session.userInfo.get(u'title', u''))
					clientDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingMediaType', value=session.videoAttributes.get(u'type', u'unknown'))
					
					if clientDevice.indigoDevice.deviceTypeId == u'plexMediaClientSlot':
						clientDevice.indigoDevice.updateStateOnServer(key=u'clientId', value=playerMachineId)
					
					# the title will depend upon the type... show episodes need the show (parent) appended
					mediaTitle = session.videoAttributes.get(u'title', u'')
					if session.videoAttributes.get(u'type', u'unknown') == u'episode':
						grandparentTitle = session.videoAttributes.get(u'grandparentTitle', u'')
						if grandparentTitle != u'':
							grandparentTitle = grandparentTitle + u' : '
						mediaTitle = grandparentTitle + mediaTitle
					clientDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingTitle', value=mediaTitle)
					clientDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingSummary', value=session.videoAttributes.get(u'summary', u''))
					
					clientDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingArtUrl', value=session.videoAttributes.get(u'art', u''))
					clientDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingThumbnailUrl', value=session.videoAttributes.get(u'thumb', u''))
					clientDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingParentThumbnailUrl', value=session.videoAttributes.get(u'parentThumb', u''))
					clientDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingGrandparentArtUrl', value=session.videoAttributes.get(u'grandparentArt', u''))
					clientDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingGrandparentThumbnailUrl', value=session.videoAttributes.get(u'grandparentThumb', u''))
					clientDevice.indigoDevice.updateStateOnServer(key=u'currentlPlayingTitleYear', value=session.videoAttributes.get(u'year', u''))
					clientDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingStarRating', value=session.videoAttributes.get(u'rating', u''))
					clientDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingContentRating', value=session.videoAttributes.get(u'contentRating', u''))
					clientDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingContentResolution', value=session.mediaInfo.get(u'videoResolution', u''))
					
					contentDuration = int(session.videoAttributes.get(u'duration', u'0'))
					currentOffset = int(session.videoAttributes.get(u'viewOffset', u'0'))
					clientDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingContentLengthMS', value=contentDuration)
					clientDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingContentLengthDisplay', value=str(datetime.timedelta(seconds=contentDuration/1000)))
					clientDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingContentLengthOffset', value=currentOffset)
					clientDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingContentLengthOffsetDisplay', value=str(datetime.timedelta(seconds=currentOffset/1000)))
					if currentOffset == 0:
						percentComplete = 0.0
					else:
						percentComplete = int(((1.0 * currentOffset) / (1.0 * contentDuration)) * 100.0)
					clientDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingContentPercentComplete', value=percentComplete, uiValue='{0:f}%'.format(percentComplete))
					
					clientDevice.indigoDevice.updateStateOnServer(key=u'playerDeviceTitle', value=session.playerInfo.get(u'title', u''))
					
				else:
					self.hostPlugin.logDebugMessage(u'Found unknown client: ' + playerMachineId, RPFramework.RPFrameworkPlugin.DEBUGLEVEL_MED)
				
				# if the player is valid then add it to the currently-connected client list
				if playerMachineId != u'':
					newClientList.append((playerMachineId,playerName))
					connectedClientHash[playerMachineId] = True

			# we need to update the state of any clients NOT seen to "disconnected"
			for childDeviceKey, childDevice in self.childDevices.iteritems():
				if childDevice.indigoDevice.deviceTypeId == u'plexMediaClient':
					if childDevice.indigoDevice.states.get(u'clientConnectionStatus', u'') != u'disconnected' and not (childDevice.indigoDevice.pluginProps.get(u'plexClientId', u'') in connectedClientHash):
						# this device was not "seen" so we should mark it as being disconnected
						childDevice.indigoDevice.updateStateOnServer(key=u'clientConnectionStatus', value=u'disconnected')
						childDevice.indigoDevice.updateStateOnServer(key=u'currentUser', value=u'')
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingMediaType', value=u'unknown')
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingTitle', value=u'')
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingSummary', value=u'')
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingArtUrl', value=u'')
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingThumbnailUrl', value=u'')
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingParentThumbnailUrl', value=u'')
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingGrandparentArtUrl', value=u'')
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingGrandparentThumbnailUrl', value=u'')
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlPlayingTitleYear', value=u'')
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingStarRating', value=u'')
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingContentRating', value=u'')
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingContentResolution', value=u'')
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingContentLengthMS', value=0)
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingContentLengthOffset', value=0)
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingContentPercentComplete', value=0)
						childDevice.indigoDevice.updateStateOnServer(key=u'playerDeviceTitle', value=u'')
				elif childDevice.indigoDevice.deviceTypeId == u'plexMediaClientSlot':
					clientSlotNumStr = childDevice.indigoDevice.pluginProps.get('plexClientId', 'Slot 99')
					if clientSlotNumStr == u'':
						clientSlotNumStr = 'Slot 99'
					clientSlotNumInt = int(clientSlotNumStr[5:])
					
					if clientSlotNumInt > slotNum:
						childDevice.indigoDevice.updateStateOnServer(key=u'clientConnectionStatus', value=u'disconnected')
						childDevice.indigoDevice.updateStateOnServer(key=u'currentUser', value=u'')
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingMediaType', value=u'unknown')
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingTitle', value=u'')
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingSummary', value=u'')
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingArtUrl', value=u'')
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingThumbnailUrl', value=u'')
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingParentThumbnailUrl', value=u'')
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingGrandparentArtUrl', value=u'')
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingGrandparentThumbnailUrl', value=u'')
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlPlayingTitleYear', value=u'')
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingStarRating', value=u'')
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingContentRating', value=u'')
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingContentResolution', value=u'')
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingContentLengthMS', value=0)
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingContentLengthOffset', value=0)
						childDevice.indigoDevice.updateStateOnServer(key=u'currentlyPlayingContentPercentComplete', value=0)
						childDevice.indigoDevice.updateStateOnServer(key=u'playerDeviceTitle', value=u'')
			
			# update our list of currently connected clients
			self.hostPlugin.logDebugMessage(u'Updating current client list to: ' + RPFramework.RPFrameworkUtils.to_unicode(newClientList), RPFramework.RPFrameworkPlugin.DEBUGLEVEL_MED)
			self.currentClientList = newClientList
			self.indigoDevice.updateStateOnServer(key=u'connectedClientCount', value=len(newClientList))
			
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine should be overridden in individual device classes whenever they must
	# handle custom commands that are not already defined
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def handleUnmanagedCommandInQueue(self, deviceHTTPAddress, rpCommand):
		if rpCommand.commandName == u'obtainPlexSecurityToken':
			# we need to obtain a security token from the plex website in order to_unicode
			# access the plex server; if we already have a security token this may be skipped
			if self.plexSecurityToken == u'':
				plexHeaders = {u'X-Plex-Platform':u'Indigo', u'X-Plex-Platform-Version':indigo.server.apiVersion, u'X-Plex-Provides':u'controller', u'X-Plex-Client-Identifier':indigo.server.getDbName(), u'X-Plex-Product':u'Plex Media Server Manager', u'X-Plex-Version':self.hostPlugin.pluginVersion, u'X-Plex-Device':u'Indigo HA Server', u'X-Plex-Device-Name':u'Indigo Plugin'}
				
				responseObj = RPFramework.requests.post(u'https://plex.tv/users/sign_in.xml', headers=plexHeaders, auth=(self.indigoDevice.pluginProps.get(u'plexUsername', u''), self.indigoDevice.pluginProps.get(u'plexPassword', u'')))
				self.hostPlugin.logDebugMessage(u'Plex.tv Sign-In Response: [' + RPFramework.RPFrameworkUtils.to_unicode(responseObj.status_code) + u'] ' + RPFramework.RPFrameworkUtils.to_unicode(responseObj.text), RPFramework.RPFrameworkPlugin.DEBUGLEVEL_HIGH)
				self.hostPlugin.logDebugMessage(u'Plex.tv Sign-In Response Headers: ' + RPFramework.RPFrameworkUtils.to_unicode(responseObj.headers), RPFramework.RPFrameworkPlugin.DEBUGLEVEL_HIGH)
				
				# if successful, this should be a 201 response (Created)
				if responseObj.status_code == 201:
					# the response will be an XML return...
					authenticationXml = xml.etree.ElementTree.fromstring(RPFramework.RPFrameworkUtils.to_str(responseObj.text))
					authTokenNode = authenticationXml.find(u'authentication-token')
					self.plexSecurityToken = authTokenNode.text
					self.hostPlugin.logDebugMessage(u'Successfully obtained plex.tv authentication token', RPFramework.RPFrameworkPlugin.DEBUGLEVEL_LOW)
				else:
					self.plexSecurityToken = u''
					indigo.server.log(u'Failed to obtain authentication token from plex.tv site.', isError=True)
					
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will be called prior to any network operation to allow the addition
	# of custom headers to the request (does not include file download)
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def addCustomHTTPHeaders(self, httpRequestHeaders):
		if self.plexSecurityToken != u'':
			httpRequestHeaders[u'X-Plex-Token'] = self.plexSecurityToken
			self.hostPlugin.logDebugMessage(u'Added authentication token to request', RPFramework.RPFrameworkPlugin.DEBUGLEVEL_HIGH)
			
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will handle an error as thrown by the REST call... it allows 
	# descendant classes to do their own processing
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-		
	def handleRESTfulError(self, rpCommand, err, response=None):
		if rpCommand != None and rpCommand.commandName == u'updateServerStatusFull' and not response is None:
			# this could be an authorization issue...
			if response.status_code == 401 and self.plexSecurityToken != u'':
				self.plexSecurityToken = u''
				self.hostPlugin.logDebugMessage(u'Invalidating security token due to unauthorized response from status request', RPFramework.RPFrameworkPlugin.DEBUGLEVEL_LOW)
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
		
		self.upgradedDeviceStates.append(u'currentlyPlayingParentThumbnailUrl')
		self.upgradedDeviceStates.append(u'currentlyPlayingGrandparentArtUrl')
		self.upgradedDeviceStates.append(u'currentlyPlayingSummary')
		self.upgradedDeviceStates.append(u'playerDeviceTitle')
		self.upgradedDeviceStates.append(u'currentlyPlayingContentLengthDisplay')
		self.upgradedDeviceStates.append(u'currentlyPlayingContentLengthOffsetDisplay')
		