#! /usr/bin/env python
# -*- coding: utf-8 -*-
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
# Plex Server Manager by RogueProeliator <rp@rogueproeliator.com>
# 	Indigo plugin designed to allow full control of Plex Media Servers and clients
#	
#	Command structure based on the PMS published API, available here:
#		https://code.google.com/p/plex-api/wiki/MediaContainer
#
#	Version 0.0.1:
#
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////


#/////////////////////////////////////////////////////////////////////////////////////////
# Python imports
#/////////////////////////////////////////////////////////////////////////////////////////
import operator
import re
import shutil
import socket
import string

import RPFramework
import plexMediaServerDevices


#/////////////////////////////////////////////////////////////////////////////////////////
# Constants and configuration variables
#/////////////////////////////////////////////////////////////////////////////////////////


#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
# Plugin
#	Primary Indigo plugin class for the PMS plugin
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
class Plugin(RPFramework.RPFrameworkPlugin.RPFrameworkPlugin):
	
	#/////////////////////////////////////////////////////////////////////////////////////
	# Class construction and destruction methods
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# Constructor called once upon plugin class creation; setup the device tracking
	# variables for later use
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		# RP framework base class's init method
		super(Plugin, self).__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs, "http://www.duncanware.com/Downloads/IndigoHomeAutomation/Plugins/PlexMediaServerManager/PlexMediaServerManagerVersionInfo.html", managedDeviceClassModule=plexMediaServerDevices)
	
	
	#/////////////////////////////////////////////////////////////////////////////////////
	# Configuration and Action Dialog Callbacks
	#/////////////////////////////////////////////////////////////////////////////////////
	def getDeviceConfigUiValues(self, pluginProps, typeId, devId):
		valuesDict = indigo.Dict(pluginProps)
		errorsDict = indigo.Dict()
      
		if typeId == "plexMediaClient" and len(self.managedDevices) > 0:
			# if the device does not define a media server, we should grab the first
			# available server that we find
			for dev in indigo.devices.iter("self"):
				if dev.deviceTypeId == "plexMediaServer":
					valuesDict["mediaServer"] = str(dev.id)
					break
		return (valuesDict, errorsDict)
	
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This callback from a ConfigUI dialog should return the list of clients available for
	# the selected media server
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def getConnectedClients(self, filter="", valuesDict=None, typeId="", targetId=0):
		mediaServerId = valuesDict.get("mediaServer", "")
		if mediaServerId == "":
			self.logDebugMessage("Cannot retrieve connected clients for dialog menu - no media server specified." + mediaServerId, RPFramework.RPFrameworkPlugin.DEBUGLEVEL_MED)
			return list()
		else:
			return self.managedDevices[int(mediaServerId)].retrieveCurrentClientMenu(valuesDict.get("plexClientId", ""))
			
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This "dummy" routine simply allows the dialog to refresh the dynamic menus on
	# the form upon user request
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def reloadConnectedClientsList(self, filter="", valuesDict=None, typeId="", targetId=0):
		pass
		
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This callback will be executed whenever the user has run an action to download the
	# currently playing artwork for a Plex Client device
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def downloadCurrentlyPlayingArt(self, pluginAction):
		# retrieve the action from the list of actions so that we can validate the parameters...
		rpAction = self.indigoActions[pluginAction.pluginTypeId]
		paramValues = pluginAction.props
		validationResults = rpAction.validateActionValues(paramValues)
		if validationResults[0] == False:
			indigo.server.log("Invalid values sent for action 'Download Currently Playing Art'; the following errors were found:")
			indigo.server.log(str(validationResults[2]))
			return
			
		# the first thing that is required is that we have art to download... this can come from the
		# state of the devices
		plexClientDevice = self.managedDevices[pluginAction.deviceId]
		destinationFN = paramValues.get("saveToFilename", "")
		artUrlPath = ""
		if paramValues.get("artElement", "") == "thumb":
			artUrlPath = plexClientDevice.indigoDevice.states.get("currentlyPlayingThumbnailUrl", "")
		elif paramValues.get("artElement", "") == "art":
			artUrlPath = plexClientDevice.indigoDevice.states.get("currentlyPlayingArtUrl", "")
		elif paramValues.get("artElement", "") == "parentThumb":
			artUrlPath = plexClientDevice.indigoDevice.states.get("currentlyPlayingParentThumbnailUrl", "")
		elif paramValues.get("artElement", "") == "grandparentArt":
			artUrlPath = plexClientDevice.indigoDevice.states.get("currentlyPlayingGrandparentArtUrl", "")
		elif paramValues.get("artElement", "") == "grandparentThumb":
			artUrlPath = plexClientDevice.indigoDevice.states.get("currentlyPlayingGrandparentThumbnailUrl", "")
			
		# we only download the art if a valid URL was found...
		if artUrlPath == "":
			# log the "event"
			self.logDebugMessage("No art found for download: " + paramValues.get("artElement", "") + " for clientId: " + str(pluginAction.deviceId), RPFramework.RPFrameworkPlugin.DEBUGLEVEL_MED)
			
			# determine if we need to copy a placeholder image over to the destination
			placeholderImageFN = paramValues.get("noArtworkFilename", "")
			if placeholderImageFN != "":
				try:
					shutil.copy2(placeholderImageFN, destinationFN)
				except:
					self.exceptionLog();
		else:
			# we found art to download... we just need to queue this download as a normal file download
			# command for the client
			plexServerDevice = self.managedDevices[int(plexClientDevice.indigoDevice.pluginProps["mediaServer"])]
			fullDownloadUrl = "http://" + plexServerDevice.indigoDevice.pluginProps.get("httpAddress", "") + ":" + plexServerDevice.indigoDevice.pluginProps.get("httpPort", "") + artUrlPath
			self.logDebugMessage("Scheduling download of art at " + fullDownloadUrl, RPFramework.RPFrameworkPlugin.DEBUGLEVEL_MED)
			plexServerDevice.queueDeviceCommand(RPFramework.RPFrameworkCommand.RPFrameworkCommand(RPFramework.RPFrameworkRESTfulDevice.CMD_DOWNLOADFILE, commandPayload=(fullDownloadUrl, destinationFN, "", "", ""), parentAction=rpAction))
			
	