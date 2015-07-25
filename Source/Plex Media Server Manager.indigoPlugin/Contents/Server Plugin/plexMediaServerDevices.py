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
import indigo
import RPFramework
import plexMediaContainer 


#/////////////////////////////////////////////////////////////////////////////////////////
# Constants and Enumerations
#/////////////////////////////////////////////////////////////////////////////////////////
PLEX_CMD_DOWNLOAD_CURRENT_ART = "downloadCurrentlyPlayingArt"


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
		
		
	#/////////////////////////////////////////////////////////////////////////////////////
	# RESTful device overloads
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine should return the HTTP address that will be used to connect to the
	# RESTful device. It may connect via IP address or a host name
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def getRESTfulDeviceAddress(self):
		return (self.indigoDevice.pluginProps.get("httpAddress", ""), int(self.indigoDevice.pluginProps.get("httpPort", "80")))
		
		
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
		plexContainer = plexMediaContainer.PlexMediaContainer(responseObj, rpCommand.commandPayload)
		self.hostPlugin.logDebugMessage("MediaContainer Information: " + str(plexContainer.containerAttributes), RPFramework.RPFrameworkPlugin.DEBUGLEVEL_MED)
		
		# assuming this is the primary command then we need to update the current state information
		# of this device
		if plexContainer.containerType == plexMediaContainer.MEDIACONTAINERTYPE_SERVERNODE:
			self.indigoDevice.updateStateOnServer(key="connectionState", value="Connected")
			self.indigoDevice.updateStateOnServer(key="serverVersion", value=plexContainer.containerAttributes["version"])
			self.indigoDevice.updateStateOnServer(key="transcoderActiveVideoSessions", value=plexContainer.containerAttributes["transcoderActiveVideoSessions"])
		elif plexContainer.containerType == plexMediaContainer.MEDIACONTAINERTYPE_CLIENTLIST:
			pass
		elif plexContainer.containerType == plexMediaContainer.MEDIACONTAINERTYPE_SESSIONLIST:
			self.indigoDevice.updateStateOnServer(key="activeSessionsCount", value=int(plexContainer.containerAttributes["size"]))
			self.hostPlugin.logDebugMessage("Found " + str(len(plexContainer.videoSessions)) + " active video sessions", RPFramework.RPFrameworkPlugin.DEBUGLEVEL_MED)
			
			# update the status of any child client devices that are currently streaming; we also need to update
			# the list of available clients for the config dialog boxes
			newClientList = list()
			connectedClientHash = dict()
			for session in plexContainer.videoSessions:
				# output debug information
				self.hostPlugin.logDebugMessage("MediaContainer Media Information: " + str(session.mediaInfo), RPFramework.RPFrameworkPlugin.DEBUGLEVEL_MED)
				self.hostPlugin.logDebugMessage("MediaContainer Player Information: " + str(session.playerInfo), RPFramework.RPFrameworkPlugin.DEBUGLEVEL_MED)
			
				# retrieve the basic identification information about the player which is
				# connected for this session
				playerMachineId = session.playerInfo.get("machineIdentifier", "")
				playerName = session.playerInfo.get("title", playerMachineId)
				
				# we only have to update state information if this client is a defined Indigo device
				if playerMachineId in self.childDevices:
					clientDevice = self.childDevices[playerMachineId]
					self.hostPlugin.logDebugMessage("Found client device to update for machineID: " + playerMachineId, RPFramework.RPFrameworkPlugin.DEBUGLEVEL_MED)
					clientDevice.indigoDevice.updateStateOnServer(key="clientConnectionStatus", value=session.playerInfo.get("state", "connected"))
					clientDevice.indigoDevice.updateStateOnServer(key="currentUser", value=session.userInfo.get("title", ""))
					clientDevice.indigoDevice.updateStateOnServer(key="currentlyPlayingMediaType", value=session.videoAttributes.get("type", "unknown"))
					
					# the title will depend upon the type... show episodes need the show (parent) appended
					mediaTitle = session.videoAttributes.get("title", "")
					if session.videoAttributes.get("type", "unknown") == "episode":
						grandparentTitle = session.videoAttributes.get("grandparentTitle", "")
						if grandparentTitle != "":
							grandparentTitle = grandparentTitle + " : "
						mediaTitle = grandparentTitle + mediaTitle
					clientDevice.indigoDevice.updateStateOnServer(key="currentlyPlayingTitle", value=mediaTitle)
					
					clientDevice.indigoDevice.updateStateOnServer(key="currentlyPlayingArtUrl", value=session.videoAttributes.get("art", ""))
					clientDevice.indigoDevice.updateStateOnServer(key="currentlyPlayingThumbnailUrl", value=session.videoAttributes.get("thumb", ""))
					clientDevice.indigoDevice.updateStateOnServer(key="currentlyPlayingParentThumbnailUrl", value=session.videoAttributes.get("parentThumb", ""))
					clientDevice.indigoDevice.updateStateOnServer(key="currentlyPlayingGrandparentArtUrl", value=session.videoAttributes.get("grandparentArt", ""))
					clientDevice.indigoDevice.updateStateOnServer(key="currentlyPlayingGrandparentThumbnailUrl", value=session.videoAttributes.get("grandparentThumb", ""))
					clientDevice.indigoDevice.updateStateOnServer(key="currentlPlayingTitleYear", value=session.videoAttributes.get("year", ""))
					clientDevice.indigoDevice.updateStateOnServer(key="currentlyPlayingStarRating", value=session.videoAttributes.get("rating", ""))
					clientDevice.indigoDevice.updateStateOnServer(key="currentlyPlayingContentRating", value=session.videoAttributes.get("contentRating", ""))
					clientDevice.indigoDevice.updateStateOnServer(key="currentlyPlayingContentResolution", value=session.mediaInfo.get("videoResolution", ""))
					
					contentDuration = int(session.videoAttributes.get("duration", "0"))
					currentOffset = int(session.videoAttributes.get("viewOffset", "0"))
					clientDevice.indigoDevice.updateStateOnServer(key="currentlyPlayingContentLengthMS", value=contentDuration)
					clientDevice.indigoDevice.updateStateOnServer(key="currentlyPlayingContentLengthOffset", value=currentOffset)
					if currentOffset == 0:
						percentComplete = 0.0
					else:
						percentComplete = int(((1.0 * currentOffset) / (1.0 * contentDuration)) * 100.0)
					clientDevice.indigoDevice.updateStateOnServer(key="currentlyPlayingContentPercentComplete", value=percentComplete)
					
				else:
					self.hostPlugin.logDebugMessage("Found unknown client: " + playerMachineId, RPFramework.RPFrameworkPlugin.DEBUGLEVEL_MED)
				
				# if the player is valid then add it to the currently-connected client list
				if playerMachineId != "":
					newClientList.append((playerMachineId,playerName))
					connectedClientHash[playerMachineId] = True

			# we need to update the state of any clients NOT seen to "disconnected"
			for childDeviceKey, childDevice in self.childDevices.iteritems():
				if childDevice.indigoDevice.deviceTypeId == "plexMediaClient":
					if childDevice.indigoDevice.states.get("clientConnectionStatus", "") != "disconnected" and not (childDevice.indigoDevice.pluginProps.get("plexClientId", "") in connectedClientHash):
						# this device was not "seen" so we should mark it as being disconnected
						childDevice.indigoDevice.updateStateOnServer(key="clientConnectionStatus", value="disconnected")
						childDevice.indigoDevice.updateStateOnServer(key="currentUser", value="")
						childDevice.indigoDevice.updateStateOnServer(key="currentlyPlayingMediaType", value="unknown")
						childDevice.indigoDevice.updateStateOnServer(key="currentlyPlayingTitle", value="")
						childDevice.indigoDevice.updateStateOnServer(key="currentlyPlayingArtUrl", value="")
						childDevice.indigoDevice.updateStateOnServer(key="currentlyPlayingThumbnailUrl", value="")
						childDevice.indigoDevice.updateStateOnServer(key="currentlPlayingTitleYear", value="")
						childDevice.indigoDevice.updateStateOnServer(key="currentlyPlayingStarRating", value="")
						childDevice.indigoDevice.updateStateOnServer(key="currentlyPlayingContentRating", value="")
						childDevice.indigoDevice.updateStateOnServer(key="currentlyPlayingContentResolution", value="")
						childDevice.indigoDevice.updateStateOnServer(key="currentlyPlayingContentLengthMS", value=0)
						childDevice.indigoDevice.updateStateOnServer(key="currentlyPlayingContentLengthOffset", value=0)
						childDevice.indigoDevice.updateStateOnServer(key="currentlyPlayingContentPercentComplete", value=0)
			
			# update our list of currently connected clients
			self.hostPlugin.logDebugMessage("Updating current client list to: " + str(newClientList), RPFramework.RPFrameworkPlugin.DEBUGLEVEL_MED)
			self.currentClientList = newClientList
			self.indigoDevice.updateStateOnServer(key="connectedClientCount", value=len(newClientList))
			
	
	#/////////////////////////////////////////////////////////////////////////////////////
	# Utility Routines
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will gather a list of all of the clients connected to the media server
	# for use in a menu / config dialog. It will ensure the passed-in value is always
	# present
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def retrieveCurrentClientMenu(self, selectedClient = ""):
		# retrieve the last set of connected clients that were retrieved from the Plex server
		currentClients = self.currentClientList
		
		# ensure that the selected client ID was found
		if selectedClient != "":
			selectedClientFound = False
			for client in currentClients:
				if client[0] == selectedClient:
					selectedClientFound = True
							
			if selectedClientFound == False:
				currentClients.append((selectedClient, selectedClient))
		
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
		
		self.upgradedDeviceStates.append("currentlyPlayingParentThumbnailUrl")
		self.upgradedDeviceStates.append("currentlyPlayingGrandparentArtUrl")
		self.upgradedDeviceStates.append("currentlyPlayingParentThumbnailUrl")