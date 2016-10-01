#! /usr/bin/env python
# -*- coding: utf-8 -*-
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
# Plex Server Manager by RogueProeliator <adam.d.ashe@gmail.com>
# 	Indigo plugin designed to allow full control of Plex Media Servers and clients
#	
#	Command structure based on the PMS published API, available here:
#		https://code.google.com/p/plex-api/wiki/MediaContainer
#
#	This plugin is released under an MIT license - this is a very simple and permissive
#	license and may be found in the LICENSE.txt file found in the root of this plugin's
#	GitHub repository:
#		https://github.com/RogueProeliator/IndigoPlugins-Plex-Server-Manager-Plugin
#
#	Version 0.0.1:
#		Initial Release
#	Version 0.8.17:
#		Added unicode support
#		Added support for secure (SSL) connection to server
#	Version 1.0.17:
#		Fixed bug where grandparent art URL was not cleared when client slots disconnected
#		Added Currently Playing Summary state - description of the show
#		Added Device Title state
#		Added art download action for Slot devices
#	Version 2.0.1:
#		Updated API to use Indigo 7 API calls
#		Consolidated server state updates into new mass-update API calls
#
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////


#/////////////////////////////////////////////////////////////////////////////////////////
# Python imports
#/////////////////////////////////////////////////////////////////////////////////////////
import operator
import re
import requests
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
		super(Plugin, self).__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs, managedDeviceClassModule=plexMediaServerDevices)
	
	
	#/////////////////////////////////////////////////////////////////////////////////////
	# Configuration and Action Dialog Callbacks
	#/////////////////////////////////////////////////////////////////////////////////////
	def getDeviceConfigUiValues(self, pluginProps, typeId, devId):
		valuesDict = indigo.Dict(pluginProps)
		errorsDict = indigo.Dict()
      
		if typeId == u'plexMediaClient' and len(self.managedDevices) > 0:
			# if the device does not define a media server, we should grab the first
			# available server that we find
			for dev in indigo.devices.iter(u'self'):
				if dev.deviceTypeId == u'plexMediaServer':
					valuesDict[u'mediaServer'] = str(dev.id)
					break
		return (valuesDict, errorsDict)
	
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This callback from a ConfigUI dialog should return the list of clients available for
	# the selected media server
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def getConnectedClients(self, filter=u'', valuesDict=None, typeId=u'', targetId=0):
		mediaServerId = valuesDict.get(u'mediaServer', u'')
		self.logger.threaddebug(u'Retrieving clients for device of type ' + typeId)
		if mediaServerId == u'':
			self.logger.debug(u'Cannot retrieve connected clients for dialog menu - no media server specified.')
			return list()
		elif typeId == u'plexMediaClientSlot':
			return self.managedDevices[int(mediaServerId)].retrieveCurrentClientSlotMenu()
		else:
			return self.managedDevices[int(mediaServerId)].retrieveCurrentClientMenu(valuesDict.get(u'plexClientId', u''))
			
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This "dummy" routine simply allows the dialog to refresh the dynamic menus on
	# the form upon user request
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def reloadConnectedClientsList(self, filter=u'', valuesDict=None, typeId=u'', targetId=0):
		pass
		
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will be called to validate the information entered into the Device
	# configuration GUI from within Indigo (it will only validate registered params)
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def validateDeviceConfigUi(self, valuesDict, deviceTypeId, devId):
		baseValidation = super(Plugin, self).validateDeviceConfigUi(valuesDict, deviceTypeId, devId)
		if deviceTypeId == u'plexMediaServer' and baseValidation[0] == True:
			# clear out the username and password if the device is set to no authentication
			if RPFramework.RPFrameworkUtils.to_unicode(valuesDict[u'loginRequired']).lower() == u'false':
				baseValidation[1][u'plexUsername'] = u''
				baseValidation[1][u'plexPassword'] = u''
		return baseValidation
		
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
			self.logger.error(u'Invalid values sent for action "Download Currently Playing Art for Slot"; the following errors were found:')
			self.logger.error(RPFramework.RPFrameworkUtils.to_unicode(validationResults[2]))
			return
			
		# the first thing that is required is that we have art to download... this can come from the
		# state of the devices
		plexClientDevice = self.managedDevices[pluginAction.deviceId]
		destinationFN = paramValues.get(u'saveToFilename', u'')
		artUrlPath = u''
		if paramValues.get(u'artElement', u'') == u'thumb':
			artUrlPath = plexClientDevice.indigoDevice.states.get(u'currentlyPlayingThumbnailUrl', u'')
		elif paramValues.get(u'artElement', u'') == u'art':
			artUrlPath = plexClientDevice.indigoDevice.states.get(u'currentlyPlayingArtUrl', u'')
		elif paramValues.get(u'artElement', u'') == u'parentThumb':
			artUrlPath = plexClientDevice.indigoDevice.states.get(u'currentlyPlayingParentThumbnailUrl', u'')
		elif paramValues.get(u'artElement', u'') == u'grandparentArt':
			artUrlPath = plexClientDevice.indigoDevice.states.get(u'currentlyPlayingGrandparentArtUrl', u'')
		elif paramValues.get(u'artElement', u'') == u'grandparentThumb':
			artUrlPath = plexClientDevice.indigoDevice.states.get(u'currentlyPlayingGrandparentThumbnailUrl', u'')
			
		# we only download the art if a valid URL was found...
		if artUrlPath == u'':
			# log the "event"
			self.logger.debug(u'No art found for download: ' + paramValues.get(u'artElement', u'') + u' for clientId: ' + RPFramework.RPFrameworkUtils.to_unicode(pluginAction.deviceId))
			
			# determine if we need to copy a placeholder image over to the destination
			placeholderImageFN = paramValues.get(u'noArtworkFilename', u'')
			if placeholderImageFN != u'':
				try:
					shutil.copy2(RPFramework.RPFrameworkUtils.to_str(placeholderImageFN), RPFramework.RPFrameworkUtils.to_str(destinationFN))
				except:
					self.logger.error(u'Error copying No Artwork file to destination');
		else:
			# we found art to download... we just need to queue this download as a normal file download
			# command for the client
			plexServerDevice = self.managedDevices[int(plexClientDevice.indigoDevice.pluginProps[u'mediaServer'])]
			httpMethod = plexServerDevice.indigoDevice.pluginProps.get(u'requestMethod', u'http')
			authType = u'none'
			authUsername = u'' 
			authPassword =  u''
			
			if RPFramework.RPFrameworkUtils.to_unicode(plexServerDevice.indigoDevice.pluginProps.get(u'loginRequired', u'False')).lower() == u'true':
				authType = u'digest'
				authUsername = plexServerDevice.indigoDevice.pluginProps.get(u'plexUsername', u'False')
				authPassword = plexServerDevice.indigoDevice.pluginProps.get(u'plexPassword', u'False')
			
			# if the user has opted to resize the image, this will be done as an image resize action and we must add
			# in the dimensions
			resizeWidth = 0
			resizeHeight = 0
			resizeMethod = paramValues.get(u'resizeMode', u'none')
			if resizeMethod == u'exact':
				resizeWidth = int(paramValues.get(u'imageResizeWidth', '0'))
				resizeHeight = int(paramValues.get(u'imageResizeHeight', '0'))
			elif resizeMethod == u'max':
				resizeWidth = int(paramValues.get(u'imageResizeMaxDimension', '0'))
			
			self.logger.debug(u'Scheduling download of art at ' + artUrlPath)
			plexServerDevice.queueDeviceCommand(RPFramework.RPFrameworkCommand.RPFrameworkCommand(RPFramework.RPFrameworkRESTfulDevice.CMD_DOWNLOADIMAGE, commandPayload=(httpMethod, artUrlPath, u'', u'', u'', destinationFN, resizeWidth, resizeHeight), parentAction=rpAction))
			
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This callback will handle actions which send a command directly to a client in order
	# to directly control the client (navigation, playback, etc.)
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def sendClientPlaybackCommand(self, pluginAction):
		# retrieve the action from the list of actions so that we can validate the parameters...
		rpAction = self.indigoActions[pluginAction.pluginTypeId]
		paramValues = pluginAction.props
		validationResults = rpAction.validateActionValues(paramValues)
		if validationResults[0] == False:
			self.logger.error(u'Invalid values sent for action "Send Playback Command"; the following errors were found:')
			self.logger.error(RPFramework.RPFrameworkUtils.to_unicode(validationResults[2]))
			return
			
		# obtain our instance of the client device and ensure that we have all the information necessary
		# to execute the request
		plexClientDevice = self.managedDevices[pluginAction.deviceId]
		clientAddress = plexClientDevice.indigoDevice.states.get(u'clientAddress', u'')
		clientPort = int(plexClientDevice.indigoDevice.states.get(u'clientPort', u'0'))
		if plexClientDevice.indigoDevice.deviceTypeId == u'plexMediaClientSlot':
			plexClientMachineId = plexClientDevice.indigoDevice.states.get(u'clientId', u'')
		else:
			plexClientMachineId = plexClientDevice.indigoDevice.pluginProps.get(u'address', u'')
		mediaServer = int(plexClientDevice.indigoDevice.pluginProps.get(u'mediaServer', u'0'))
		
		if clientAddress == u'' or clientPort <= 0 or plexClientMachineId == u'':
			self.logger.error(u'Cannot send client playback command since the client address has not yet been determined.')
			return
		elif mediaServer == 0:
			self.logger.error(u'Plex Client Indigo Device is not assigned to a Plex Media Server; please edit the device and select the associated server.')
			return
			
		# the server must be authenticated properly or else the command may be rejected
		plexServerDevice = self.managedDevices[int(mediaServer)]
		plexServerDevice.retrieveSecurityToken()
		
		# a media type may or may not be specified
		selectedMediaType = paramValues.get(u'mediaType', u'')
		if selectedMediaType == u'':
			mediaTypeParam = ''
		else:
			mediaTypeParam = u'&mtype=' + selectedMediaType
		
		# execute the request to the client...
		targetUrl = u'http://' + clientAddress + u':' + str(clientPort) + u'/player/' + paramValues.get(u'commandToSend').replace(u'-', u'/') + u'?commandID=' + str(plexClientDevice.getClientCommandID()) + mediaTypeParam
		plexHeaders = {u'X-Plex-Platform':u'Indigo', u'X-Plex-Platform-Version':indigo.server.apiVersion, u'X-Plex-Provides':u'controller', u'X-Plex-Client-Identifier':indigo.server.getDbName(), u'X-Plex-Product':u'PlexAPI', u'X-Plex-Version':self.pluginVersion, u'X-Plex-Device':u'Indigo HA Server', u'X-Plex-Device-Name':u'Indigo Plugin', u'X-Plex-Token':plexServerDevice.plexSecurityToken, u'X-Plex-Target-Client-Identifier':plexClientMachineId}
		self.logger.threaddebug(u'Sending client playback command: ' + targetUrl + ' with headers: ' + RPFramework.RPFrameworkUtils.to_unicode(plexHeaders))
		responseObj = requests.get(targetUrl, headers=plexHeaders)
		
		self.logger.debug(u'Client Command Response: [' + unicode(responseObj.status_code) + u'] ' + responseObj.text)
		