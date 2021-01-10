#! /usr/bin/env python
# -*- coding: utf-8 -*-
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
# RPFrameworkPlugin by RogueProeliator <adam.d.ashe@gmail.com>
# 	Base class for all RogueProeliator's plugins for Perceptive Automation's Indigo
#	home automation software.
#	
#	THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# 	IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# 	FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# 	AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# 	LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# 	OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# 	SOFTWARE.
#
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////

#/////////////////////////////////////////////////////////////////////////////////////////
# Python imports
#/////////////////////////////////////////////////////////////////////////////////////////
import indigo
import os
import re
import requests
import RPFrameworkCommand
from RPFrameworkIndigoAction import RPFrameworkIndigoActionDfn
import RPFrameworkDeviceResponse 
import RPFrameworkIndigoParam
import RPFrameworkNetworkingUPnP
from dataAccess import indigosql
import Queue
import shutil
import socket
from subprocess import call
import time
from urllib2 import urlopen
import xml.etree.ElementTree
import threading
import RPFrameworkUtils
import ConfigParser
import logging
from distutils.version import LooseVersion

#/////////////////////////////////////////////////////////////////////////////////////////
# Constants and configuration variables
#/////////////////////////////////////////////////////////////////////////////////////////
GUI_CONFIG_PLUGINSETTINGS                        = u'plugin'
GUI_CONFIG_PLUGIN_COMMANDQUEUEIDLESLEEP          = u'pluginCommandQueueIdleSleep'
GUI_CONFIG_PLUGIN_DEBUG_SHOWUPNPOPTION           = u'showUPnPDebug'
GUI_CONFIG_PLUGIN_DEBUG_UPNPOPTION_SERVICEFILTER = u'UPnPDebugServiceFilter'

GUI_CONFIG_ADDRESSKEY = u'deviceAddressFormat'

GUI_CONFIG_UPNP_SERVICE                   = u'deviceUPNPServiceId'
GUI_CONFIG_UPNP_CACHETIMESEC              = u'deviceUPNPSeachCacheTime'
GUI_CONFIG_UPNP_ENUMDEVICESFIELDID        = u'deviceUPNPDeviceFieldId'
GUI_CONFIG_UPNP_DEVICESELECTTARGETFIELDID = u'deviceUPNPDeviceSelectedFieldId'

GUI_CONFIG_ISCHILDDEVICEID            = u'deviceIsChildDevice'
GUI_CONFIG_PARENTDEVICEIDPROPERTYNAME = u'deviceParentIdProperty'
GUI_CONFIG_CHILDDICTIONARYKEYFORMAT   = u'childDeviceDictionaryKeyFormat'

GUI_CONFIG_RECONNECTIONATTEMPT_LIMIT          = u'reconnectAttemptLimit'
GUI_CONFIG_RECONNECTIONATTEMPT_DELAY          = u'reconnectAttemptDelay'
GUI_CONFIG_RECONNECTIONATTEMPT_SCHEME         = u'reconnectAttemptScheme'
GUI_CONFIG_RECONNECTIONATTEMPT_SCHEME_FIXED   = u'fixed'
GUI_CONFIG_RECONNECTIONATTEMPT_SCHEME_REGRESS = u'regress'

GUI_CONFIG_DATABASE_CONN_ENABLED = u'databaseConnectionEnabled'
GUI_CONFIG_DATABASE_CONN_TYPE    = u'databaseConnectionType'
GUI_CONFIG_DATABASE_CONN_DBNAME  = u'databaseConnectionDBName'

DEBUGLEVEL_NONE = 0		# no .debug() logs will be shown in the Indigo log
DEBUGLEVEL_LOW  = 1		# show .debug() logs in the Indigo log
DEBUGLEVEL_HIGH = 2		# show .ThreadDebug() log calls in the Indigo log


#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
# RPFrameworkPlugin
#	Base class for Indigo plugins that provides standard functionality such as version
#	checking and validation functions
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
class RPFrameworkPlugin(indigo.PluginBase):
	
	#/////////////////////////////////////////////////////////////////////////////////////
	# Class construction and destruction methods
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# Constructor called once upon plugin class creation; setup the basic functionality
	# common to all plugins based on the framework
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs, daysBetweenUpdateChecks=1, managedDeviceClassModule=None, pluginSupportsUPNP=False):
		# flag the plugin as undergoing initialization so that we know the full
		# indigo plugin is not yet available
		self.pluginIsInitializing = True
		self.pluginSupportsUPNPDebug = pluginSupportsUPNP
		
		# call the base class' initialization to begin setup...
		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
				
		# setup a custom logging format to make it easier to look through (this applies only to the plugin's
		# individual file handler
		loggingFormatString = logging.Formatter('%(asctime)s.%(msecs)03d\t%(levelname)-12s\t%(name)s.%(funcName)-25s %(msg)s', datefmt='%Y-%m-%d %H:%M:%S')
		self.plugin_file_handler.setFormatter(loggingFormatString)
				
		# determine what the user has set for the debug level; this will determine how we set
		# the python logging to show in the event log
		try:
			self.debugLevel = int(pluginPrefs.get(u'debugLevel', DEBUGLEVEL_NONE))
			if self.debugLevel < 0 or self.debugLevel > 2:
				self.debugLevel = DEBUGLEVEL_NONE
		except:
			self.debugLevel = DEBUGLEVEL_NONE
		
		# setup the logging level of the INDIGO logging handler to the selected level
		if self.debugLevel == DEBUGLEVEL_LOW:
			self.indigo_log_handler.setLevel(logging.DEBUG)
		elif self.debugLevel == DEBUGLEVEL_HIGH:
			self.indigo_log_handler.setLevel(logging.THREADDEBUG)
		else:
			self.indigo_log_handler.setLevel(logging.INFO)
			
		# show the debug message since we are in the middle of initializing the plugin base class
		self.logger.threaddebug(u'Initializing RPFrameworkPlugin')
		
		# create the generic device dictionary which will store a reference to each device that
		# is defined in indigo; the ID mapping will map the deviceTypeId to a class name
		self.managedDevices = dict()
		self.managedDeviceClassModule = managedDeviceClassModule
		self.managedDeviceClassMapping = dict()
		self.managedDeviceParams = dict()
		self.managedDeviceGUIConfigs = dict()
		
		# create a list of actions that are known to the base plugin (these will be processed
		# automatically when possible by the base classes alone)
		self.indigoActions = dict()
		self.deviceResponseDefinitions = dict()
		
		# the plugin defines the Events processing so that we can handle the update trigger,
		# if it exists
		self.indigoEvents = dict()
		
		# this list stores a list of enumerated devices for those devices which support
		# enumeration via uPNP
		self.enumeratedDevices = []
		self.lastDeviceEnumeration = time.time() - 9999
		
		# create the command queue that will be used at the device level
		self.pluginCommandQueue = Queue.Queue()
		
		# create plugin-level configuration variables
		self.pluginConfigParams = []
		
		# parse the RPFramework plugin configuration XML provided for this plugin,
		# if it is present
		self.parseRPFrameworkConfig(pluginDisplayName.replace(u' Plugin', u''))
		
		# perform any upgrade steps if the plugin is running for the first time after
		# an upgrade
		oldPluginVersion = pluginPrefs.get(u'loadedPluginVersion', u'')
		if oldPluginVersion != RPFrameworkUtils.to_unicode(pluginVersion):
			self.performPluginUpgradeMaintenance(oldPluginVersion, RPFrameworkUtils.to_unicode(pluginVersion))
		
		# initialization is complete...
		self.pluginIsInitializing = False
	
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will parse the RPFrameworkConfig.xml file that is present in the
	# plugin's directory, if it is present
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def parseRPFrameworkConfig(self, pluginName):
		pluginBasePath = os.getcwd()
		pluginConfigPath = os.path.join(pluginBasePath, "RPFrameworkConfig.xml")
		
		if os.path.exists(pluginConfigPath):
			self.logger.debug(u'Beginning processing of RPFrameworkConfig.xml file')
			try:
				# read in the XML using the XML ElementTree implementation/module
				configDom = xml.etree.ElementTree.parse(pluginConfigPath)
				pluginConfigNode = configDom.getroot().find("pluginConfig")
				
				# read in any plugin-level parameter definitions
				pluginParamNode = pluginConfigNode.find("pluginParams")
				if pluginParamNode != None:
					for pluginParam in pluginParamNode:
						rpPluginParam = self.readIndigoParamNode(pluginParam)
						self.pluginConfigParams.append(rpPluginParam)
						self.logger.threaddebug(u'Found plugin param: {0}'.format(rpPluginParam.indigoId))
				
				# read in any plugin-level guiConfigSettings
				pluginGuiConfigNode = pluginConfigNode.find("guiConfiguration")
				if pluginGuiConfigNode != None:
					for guiConfigSetting in pluginGuiConfigNode:
						self.logger.threaddebug(u'Found plugin setting: {0} = {1}'.format(guiConfigSetting.tag, guiConfigSetting.text))
						self.putGUIConfigValue(GUI_CONFIG_PLUGINSETTINGS, guiConfigSetting.tag, guiConfigSetting.text)
				
				# determine if any device mappings are present
				deviceMappings = pluginConfigNode.find("deviceMapping")
				if deviceMappings != None:
					for deviceMapping in deviceMappings.findall("device"):
						indigoId = RPFrameworkUtils.to_unicode(deviceMapping.get('indigoId'))
						className = RPFrameworkUtils.to_unicode(deviceMapping.get('className'))
						self.managedDeviceClassMapping[indigoId] = className
						self.logger.threaddebug(u'Found device mapping; id: {0} to class: {1}'.format(indigoId, className))
				else:
					self.logger.threaddebug(u'No device mappings found')
					
				# read in any device definition information such as device properties for
				# validation and retrieval
				devicesNode = pluginConfigNode.find("devices")
				if devicesNode != None:
					for deviceDfn in devicesNode.findall("device"):
						indigoDeviceId = RPFrameworkUtils.to_unicode(deviceDfn.get("indigoId"))
						
						# process all of the parameters for this device
						deviceParamsNode = deviceDfn.find("params")
						if deviceParamsNode != None:
							paramsList = list()
							for deviceParam in deviceParamsNode.findall("param"):
								rpDevParam = self.readIndigoParamNode(deviceParam)
								self.logger.threaddebug(u'Created device parameter for managed device "{0}": {1}'.format(indigoDeviceId, rpDevParam.indigoId))
								paramsList.append(rpDevParam)
							self.managedDeviceParams[indigoDeviceId] = paramsList
							
						# process any GUI configurations -- these are settings that affect how the
						# plugin appears to Indigo users
						guiConfigNode = deviceDfn.find("guiConfiguration")
						if guiConfigNode != None:
							for guiConfigSetting in guiConfigNode:
								self.logger.threaddebug(u'Found device setting: {0}={1}'.format(guiConfigSetting.tag, guiConfigSetting.text))
								self.putGUIConfigValue(indigoDeviceId, guiConfigSetting.tag, guiConfigSetting.text)
								
						# process any device response definitions... these define what the plugin will do
						# when a response is received from the device (definition is agnostic of type of device,
						# though they may be handled differently in code)
						deviceResponsesNode = deviceDfn.find("deviceResponses")
						if deviceResponsesNode != None:
							for devResponse in deviceResponsesNode.findall("response"):
								responseId = RPFrameworkUtils.to_unicode(devResponse.get("id"))
								responseToActionId = RPFrameworkUtils.to_unicode(devResponse.get("respondToActionId"))
								criteriaFormatString = RPFrameworkUtils.to_unicode(devResponse.find("criteriaFormatString").text)
								matchExpression = RPFrameworkUtils.to_unicode(devResponse.find("matchExpression").text)
								self.logger.threaddebug(u'Found device response: {0}'.format(responseId))
									
								# create the object so that effects may be added from child nodes
								devResponseDefn = RPFrameworkDeviceResponse.RPFrameworkDeviceResponse(responseId, criteriaFormatString, matchExpression, responseToActionId)
								
								# add in any effects that are defined
								effectsListNode = devResponse.find("effects")
								if effectsListNode != None:
									for effectDefn in effectsListNode.findall("effect"):
										effectType = eval(u'RPFrameworkDeviceResponse.{0}'.format(effectDefn.get("effectType")))
										effectUpdateParam = RPFrameworkUtils.to_unicode(effectDefn.find("updateParam").text)
										effectValueFormat = RPFrameworkUtils.to_unicode(effectDefn.find("updateValueFormat").text)
										
										effectValueFormatExVal = u''
										effectValueFormatExNode = effectDefn.find("updateValueExFormat")
										if effectValueFormatExNode != None:
											effectValueFormatExVal = RPFrameworkUtils.to_unicode(effectValueFormatExNode.text)
										
										effectValueEvalResult = RPFrameworkUtils.to_unicode(effectDefn.get("evalResult")).lower() == "true"
										
										effectExecCondition = u''
										effectExecConditionNode = effectDefn.find("updateExecCondition")
										if effectExecConditionNode != None:
											effectExecCondition = RPFrameworkUtils.to_unicode(effectExecConditionNode.text)
										
										self.logger.threaddebug(u'Found response effect: Type={0}; Param: {1}; ValueFormat={2}; ValueFormatEx={3}; Eval={4}; Condition={5}'.format(effectType, effectUpdateParam, effectValueFormat, effectValueFormatExVal, effectValueEvalResult, effectExecCondition))
										devResponseDefn.addResponseEffect(RPFrameworkDeviceResponse.RPFrameworkDeviceResponseEffect(effectType, effectUpdateParam, effectValueFormat, effectValueFormatExVal, effectValueEvalResult, effectExecCondition))
								
								# add the definition to the plugin's list of response definitions
								self.addDeviceResponseDefinition(indigoDeviceId, devResponseDefn)
						
				# attempt to read any actions that will be automatically processed by
				# the framework
				managedActions = pluginConfigNode.find("actions")
				if managedActions != None:
					for managedAction in managedActions.findall("action"):
						indigoActionId = RPFrameworkUtils.to_unicode(managedAction.get('indigoId'))
						rpAction = RPFrameworkIndigoActionDfn(indigoActionId)
						self.logger.threaddebug(u'Found managed action: ' + indigoActionId)
						
						# process/add in the commands for this action
						commandListNode = managedAction.find("commands")
						if commandListNode != None:
							for commandDefn in commandListNode.findall("command"):
								commandNameNode         = commandDefn.find("commandName")
								commandFormatStringNode = commandDefn.find("commandFormat")
								
								commandExecuteCondition = u''
								commandExecuteConditionNode = commandDefn.find("commandExecCondition")
								if commandExecuteConditionNode != None:
									commandExecuteCondition = RPFrameworkUtils.to_unicode(commandExecuteConditionNode.text)
								
								commandRepeatCount = u''
								commandRepeatCountNode = commandDefn.find("commandRepeatCount")
								if commandRepeatCountNode != None:
									commandRepeatCount = RPFrameworkUtils.to_unicode(commandRepeatCountNode.text)
									
								commandRepeatDelay = u''
								commandRepeatDelayNode = commandDefn.find("commandRepeatDelay")
								if commandRepeatDelayNode != None:
									commandRepeatDelay = RPFrameworkUtils.to_unicode(commandRepeatDelayNode.text)
								
								rpAction.addIndigoCommand(RPFrameworkUtils.to_unicode(commandNameNode.text), RPFrameworkUtils.to_unicode(commandFormatStringNode.text), commandRepeatCount, commandRepeatDelay, commandExecuteCondition)
							
						paramsNode = managedAction.find("params")
						if paramsNode != None:
							self.logger.threaddebug(u'Processing {0} params for action'.format(len(paramsNode)))
							for actionParam in paramsNode.findall("param"):
								rpParam = self.readIndigoParamNode(actionParam)
								self.logger.threaddebug(u'Created parameter for managed action "{0}": {1}'.format(rpAction.indigoActionId, rpParam.indigoId))
								rpAction.addIndigoParameter(rpParam)
						self.addIndigoAction(rpAction)
				self.logger.debug(u'Successfully completed processing of RPFrameworkConfig.xml file')
			except:
				self.logger.critical(u'Plugin Config: Error reading RPFrameworkConfig.xml file at: {0}'.format(pluginConfigPath))
		else:
			self.logger.warning(u'RPFrameworkConfig.xml not found at {0}, skipping processing'.format(pluginConfigPath))
			
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will read in a parameter definition from the given XML node, returning
	# a RPFrameworkIndigoParam object fully filled in from the node
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def readIndigoParamNode(self, paramNode):
		paramIndigoId = RPFrameworkUtils.to_unicode(paramNode.get("indigoId"))
		paramType = eval(u'RPFrameworkIndigoParam.{0}'.format(paramNode.get('paramType')))
		paramIsRequired = (paramNode.get("isRequired").lower() == "true")
		rpParam = RPFrameworkIndigoParam.RPFrameworkIndigoParamDefn(paramIndigoId, paramType, isRequired=paramIsRequired)
		
		minValueNode = paramNode.find("minValue")
		if minValueNode != None:
			minValueString = minValueNode.text
			if rpParam.paramType == RPFrameworkIndigoParam.ParamTypeFloat:
				rpParam.minValue = float(minValueString)
			else:
				rpParam.minValue = int(minValueString)
		
		maxValueNode = paramNode.find("maxValue")
		if maxValueNode != None:
			maxValueString = maxValueNode.text
			if rpParam.paramType == RPFrameworkIndigoParam.ParamTypeFloat:
				rpParam.maxValue = float(maxValueString)
			else:
				rpParam.maxValue = int(maxValueString)
				
		validationExpressionNode = paramNode.find("validationExpression")
		if validationExpressionNode != None:
			rpParam.validationExpression = RPFrameworkUtils.to_unicode(validationExpressionNode.text)
				
		defaultValueNode = paramNode.find("defaultValue")
		if defaultValueNode != None:
			if rpParam.paramType == RPFrameworkIndigoParam.ParamTypeFloat:
				rpParam.defaultValue = float(defaultValueNode.text)
			elif rpParam.paramType == RPFrameworkIndigoParam.ParamTypeInteger:
				rpParam.defaultValue = int(defaultValueNode.text)
			elif rpParam.paramType == RPFrameworkIndigoParam.ParamTypeBoolean:
				rpParam.defaultValue = (defaultValueNode.text.lower() == "true")
			else:
				rpParam.defaultValue = defaultValueNode.text
				
		invalidMessageNode = paramNode.find("invalidValueMessage")
		if invalidMessageNode != None:
			rpParam.invalidValueMessage = RPFrameworkUtils.to_unicode(invalidMessageNode.text)
	
		return rpParam
	
	
	
	#/////////////////////////////////////////////////////////////////////////////////////
	# Indigo control methods
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# startup is called by Indigo whenever the plugin is first starting up (by a restart
	# of Indigo server or the plugin or an update
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def startup(self):
		pass
		
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# shutdown is called by Indigo whenever the entire plugin is being shut down from
	# being disabled, during an update process or if the server is being shut down
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def shutdown(self):
		pass
		
		
		
	#/////////////////////////////////////////////////////////////////////////////////////
	# Indigo device life-cycle call-back routines
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine is called whenever the plugin should be connecting / communicating with
	# the physical device... here is where we will begin tracking the device as well
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def deviceStartComm(self, dev):
		self.logger.debug(u'Entering deviceStartComm for {0}; ID={1}'.format(dev.name, dev.id))
		
		# create the plugin device object and add it to the managed list
		newDeviceObject = self.createDeviceObject(dev)
		self.managedDevices[dev.id] = newDeviceObject
		newDeviceObject.initiateCommunications()
		
		# this object may be a child object... if it is then we need to see if its
		# parent has already been created (and if so add it to that parent)
		isChildDeviceType = self.getGUIConfigValue(dev.deviceTypeId, GUI_CONFIG_ISCHILDDEVICEID, u'false').lower() == 'true'
		if isChildDeviceType == True:
			self.logger.threaddebug(u'Device is child object, attempting to find parent')
			parentDeviceId = int(dev.pluginProps[self.getGUIConfigValue(dev.deviceTypeId, GUI_CONFIG_PARENTDEVICEIDPROPERTYNAME, u'')])
			self.logger.threaddebug(u'Found parent ID of device {0}: {1}'.format(dev.id, parentDeviceId))
			if parentDeviceId in self.managedDevices:
				self.logger.threaddebug(u'Parent object found, adding this child device now')
				self.managedDevices[parentDeviceId].addChildDevice(newDeviceObject)
				
		# this object could be a parent object whose children have already been created; we need to add those children
		# to this parent object now
		for foundDeviceId in self.managedDevices:
			foundDevice = self.managedDevices[foundDeviceId]
			if self.getGUIConfigValue(foundDevice.indigoDevice.deviceTypeId, GUI_CONFIG_ISCHILDDEVICEID, u'false').lower() == u'true' and int(foundDevice.indigoDevice.pluginProps[self.getGUIConfigValue(foundDevice.indigoDevice.deviceTypeId, GUI_CONFIG_PARENTDEVICEIDPROPERTYNAME, u'')]) == dev.id:
				self.logger.threaddebug(u'Found previously-created child object for parent; child ID: {0}'.format(foundDevice.indigoDevice.id))
				newDeviceObject.addChildDevice(foundDevice)

		self.logger.debug(u'Exiting deviceStartComm for {0}'.format(dev.name))
		
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine must be implemented in ancestor classes in order to return the device
	# object that is to be created/managed
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def createUnManagedDeviceObject(self, device):
		raise u'createUnManagedDeviceObject not implemented'
	def createDeviceObject(self, device):
		if not (self.managedDeviceClassModule == None) and device.deviceTypeId in self.managedDeviceClassMapping:
			deviceClass = getattr(self.managedDeviceClassModule, self.managedDeviceClassMapping[device.deviceTypeId])
			return deviceClass(self, device)
		else:
			return self.createUnManagedDeviceObject(device)
		
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine is called whenever the plugin should cease communicating with the
	# hardware, breaking the connection
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def deviceStopComm(self, dev):
		self.logger.debug(u'Entering deviceStopComm for {0}; ID={1}'.format(dev.name, dev.id))
		
		# dequeue any pending reconnection attempts...
		
		# first remove the device from the parent if this is a child device...
		isChildDeviceType = self.getGUIConfigValue(dev.deviceTypeId, GUI_CONFIG_ISCHILDDEVICEID, u'false').lower() == u'true'
		if isChildDeviceType == True:
			self.logger.threaddebug(u'Device is child object, attempting to remove from parent...')
			parentDeviceId = int(dev.pluginProps[self.getGUIConfigValue(dev.deviceTypeId, GUI_CONFIG_PARENTDEVICEIDPROPERTYNAME, u'')])
			if parentDeviceId in self.managedDevices:
				self.logger.threaddebug(u'Removing device from parent ID: {0}'.format(parentDeviceId))
				self.managedDevices[parentDeviceId].removeChildDevice(self.managedDevices[dev.id])
		
		# remove the primary managed object
		self.managedDevices[dev.id].terminateCommunications()
		del self.managedDevices[dev.id]			
		
		self.logger.debug(u'Exiting deviceStopComm for {0}'.format(dev.name))
		
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine is called whenever the server is defining an event / trigger setup
	# by the user
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def triggerStartProcessing(self, trigger):
		self.logger.threaddebug(u'Registering trigger: {0}'.format(trigger.id))
		
		# if the descendent class does not handle the trigger then we process it by
		# storing it against the trigger type
		if self.registerCustomTrigger(trigger) == False:
			triggerType = trigger.pluginTypeId
			if not (triggerType in self.indigoEvents):
				self.indigoEvents[triggerType] = dict()
			self.indigoEvents[triggerType][trigger.id] = trigger
			
		self.logger.debug(u'Registered trigger: {0}'.format(trigger.id))
		
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine gives descendant plugins the chance to process the event
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def registerCustomTrigger(self, trigger):
		return False
		
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine is called whenever the server is un-registering a trigger
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def triggerStopProcessing(self, trigger):
		self.logger.threaddebug(u'Stopping trigger: {0}'.format(trigger.id))
		
		# if the descendent class does not handle the unregistration then we process it by
		# removing it from the dictionary
		if self.registerCustomTrigger(trigger) == False:
			triggerType = trigger.pluginTypeId
			if triggerType in self.indigoEvents:
				if trigger.id in self.indigoEvents[triggerType]:
					del self.indigoEvents[triggerType][trigger.id]
		
		self.logger.debug(u'Stopped trigger: {0}'.format(trigger.id))
		
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine gives descendant plugins the chance to unregister the event
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def unRegisterCustomTrigger(self, trigger):
		return False
		
		
	
	#/////////////////////////////////////////////////////////////////////////////////////
	# Asynchronous processing routines
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will run the concurrent processing thread used at the plugin (not
	# device) level - such things as update checks and device reconnections
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def runConcurrentThread(self):
		try:
			# read in any configuration values necessary...
			emptyQueueProcessingThreadSleepTime = float(self.getGUIConfigValue(GUI_CONFIG_PLUGINSETTINGS, GUI_CONFIG_PLUGIN_COMMANDQUEUEIDLESLEEP, u'20'))
			
			while True:
				# process pending commands now...
				reQueueCommandsList = list()
				while not self.pluginCommandQueue.empty():
					lenQueue = self.pluginCommandQueue.qsize()
					self.logger.threaddebug(u'Plugin Command queue has {0} command(s) waiting'.format(lenQueue))
					
					# the command name will identify what action should be taken...
					reQueueCommand = False
					command = self.pluginCommandQueue.get()
					if command.commandName == RPFrameworkCommand.CMD_DEVICE_RECONNECT:
						# the command payload will be in the form of a tuple:
						#	(DeviceID, DeviceInstanceIdentifier, ReconnectTime)
						#	ReconnectTime is the datetime where the next reconnection attempt should occur
						timeNow = time.time()
						if timeNow > command.commandPayload[2]:
							if command.commandPayload[0] in self.managedDevices:
								if self.managedDevices[command.commandPayload[0]].deviceInstanceIdentifier == command.commandPayload[1]:
									self.logger.debug(u'Attempting reconnection to device {0}'.format(command.commandPayload[0]))
									self.managedDevices[command.commandPayload[0]].initiateCommunications()
								else:
									self.logger.threaddebug(u'Ignoring reconnection command for device {0}; new instance detected'.format(command.commandPayload[0]))
							else:
								self.logger.debug(u'Ignoring reconnection command for device {0}; device not created'.format(command.commandPayload[0]))
						else:
							reQueueCommand = True
					
					elif command.commandName == RPFrameworkCommand.CMD_DEBUG_LOGUPNPDEVICES:
						# kick off the UPnP discovery and logging now
						self.logUPnPDevicesFoundProcessing()
					
					else:
						# allow a base class to process the command
						self.handleUnknownPluginCommand(command, reQueueCommandsList)
					
					# complete the dequeuing of the command, allowing the next
					# command in queue to rise to the top
					self.pluginCommandQueue.task_done()
					if reQueueCommand == True:
						self.logger.threaddebug(u'Plugin command queue not yet ready; requeuing for future execution')
						reQueueCommandsList.append(command)	
							
				# any commands that did not yet execute should be placed back into the queue
				for commandToRequeue in reQueueCommandsList:
					self.pluginCommandQueue.put(commandToRequeue)
				
				# sleep on an empty queue... note that this should not normally be as granular
				# as a device's communications! (value is in seconds)
				self.sleep(emptyQueueProcessingThreadSleepTime)
				
		except self.StopThread:
			# this exception is simply shutting down the thread... there is nothing
			# that we need to process
			pass
			
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will be called to handle any unknown commands at the plugin level; it
	# can/should be overridden in the plugin implementation (if needed)
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def handleUnknownPluginCommand(self, rpCommand, reQueueCommandsList):
		pass


	
	#/////////////////////////////////////////////////////////////////////////////////////
	# Indigo definitions helper functions
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will add a new action to the managed actions of the plugin
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def addIndigoAction(self, indigoAction):
		self.indigoActions[indigoAction.indigoActionId] = indigoAction
		
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will add a new device response to the list of responses that the plugin
	# can automatically handle
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def addDeviceResponseDefinition(self, deviceTypeId, responseDfn):
		if not (deviceTypeId in self.deviceResponseDefinitions):
			self.deviceResponseDefinitions[deviceTypeId] = list()
		self.deviceResponseDefinitions[deviceTypeId].append(responseDfn)
				
	
	
	#/////////////////////////////////////////////////////////////////////////////////////
	# Data Validation functions... these functions allow the plugin or devices to validate
	# user input
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will be called to validate the information entered into the Plugin
	# configuration file
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def validatePrefsConfigUi(self, valuesDict):
		# create an error message dictionary to hold validation issues foundDevice
		errorMessages = indigo.Dict()
		
		# check each defined parameter, if any exist...
		for param in self.pluginConfigParams:
			if param.indigoId in valuesDict:
				# a value is present for this parameter - validate it
				if param.isValueValid(valuesDict[param.indigoId]) == False:
					errorMessages[param.indigoId] = param.invalidValueMessage
					
		# return the validation results...
		if len(errorMessages) == 0:
			return (True, valuesDict)
		else:
			return (False, valuesDict, errorMessages)
	
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will be called when the user has closed the preference dialog
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def closedPrefsConfigUi(self, valuesDict, userCancelled):
		if not userCancelled:
			try:
				self.debugLevel = int(valuesDict.get(u'debugLevel', DEBUGLEVEL_NONE))
			except:
				self.debugLevel = DEBUGLEVEL_NONE
				
			# setup the logging level of the INDIGO logging handler to the selected level
			if self.debugLevel == DEBUGLEVEL_LOW:
				self.indigo_log_handler.setLevel(logging.DEBUG)
			elif self.debugLevel == DEBUGLEVEL_HIGH:
				self.indigo_log_handler.setLevel(logging.THREADDEBUG)
			else:
				self.indigo_log_handler.setLevel(logging.INFO)
			
			self.logger.debug(u'Plugin preferences updated')
			if self.debugLevel == DEBUGLEVEL_NONE:
				self.logger.info(u'Debugging disabled')
			else:
				self.logger.info(u'Debugging enabled... remember to turn off when done!')
			
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine is called in order to get the initial values for the menu actions
	# defined in MenuItems.xml. The default (as per the base) just returns a values and
	# error dictionary, both blank
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def getMenuActionConfigUiValues(self, menuId):
		valuesDict = indigo.Dict()
		errorMsgDict = indigo.Dict()
		
		if menuId == u'checkForUpdateImmediate':
			# we need to run the update during the launch and then show the results to the
			# user... watch for failures and do not let this go on (must time out) since
			# the dialog could get killed
			updateAvailable              = self.checkVersionNow()
			valuesDict["currentVersion"] = RPFrameworkUtils.to_unicode(self.pluginVersion)
			valuesDict["latestVersion"]  = self.latestReleaseFound
			
			# give the user a "better" message about the current status
			if self.latestReleaseFound == u'':
				valuesDict["versionCheckResults"] = u'3'
			elif updateAvailable == True:
				valuesDict["versionCheckResults"] = u'1'
			else:
				valuesDict["versionCheckResults"] = u'2'
		
		return (valuesDict, errorMsgDict)
		
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will be called to validate the information entered into the Device
	# configuration GUI from within Indigo (it will only validate registered params)
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def validateDeviceConfigUi(self, valuesDict, deviceTypeId, devId):
		# create an error message dictionary to hold any validation issues
		# (and their messages) that we find	
		errorMessages = indigo.Dict()
		
		# loop through each parameter for this device and validate one-by-one
		if deviceTypeId in self.managedDeviceParams:
			for param in self.managedDeviceParams[deviceTypeId]:
				if param.indigoId in valuesDict:
					# a parameter value is present, validate it now
					if param.isValueValid(valuesDict[param.indigoId]) == False:
						errorMessages[param.indigoId] = param.invalidValueMessage
					
				elif param.isRequired == True:
					errorMessages[param.indigoId] = param.invalidValueMessage
				
		# return the validation results...
		if len(errorMessages) == 0:
			# process any hidden variables that are used to show state information in
			# indigo or as a RPFramework config/storage
			valuesDict["address"] = self.substituteIndigoValues(self.getGUIConfigValue(deviceTypeId, GUI_CONFIG_ADDRESSKEY, u''), None, valuesDict)
			self.logger.threaddebug(u'Setting address of {0} to {1}'.format(devId, valuesDict["address"]))
			
			return self.validateDeviceConfigUiEx(valuesDict, deviceTypeId, devId)
		else:
			return (False, valuesDict, errorMessages)
	
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will be called to validate any parameters not known to the plugin (not
	# automatically handled and validated); this will only be called once all known
	# parameters have been validated and it MUST return a valid tuple
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def validateDeviceConfigUiEx(self, valuesDict, deviceTypeId, devId):
		return (True, valuesDict)
	
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will validate an action Config UI popup when it is being edited from
	# within the Indigo client; if the action being validated is not a known action then
	# a callback to the plugin implementation will be made
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def validateActionConfigUi(self, valuesDict, typeId, actionId):	
		self.logger.threaddebug(u'Call to validate action: {0}'.format(typeId))
		if typeId in self.indigoActions:
			actionDefn = self.indigoActions[typeId]
			managedActionValidation = actionDefn.validateActionValues(valuesDict)
			if managedActionValidation[0] == False:
				self.logger.threaddebug(u'Managed validation failed: {0}{1}'.format(managedActionValidation[1], managedActionValidation[2]))
			return managedActionValidation
		else:
			return self.validateUnRegisteredActionConfigUi(valuesDict, typeId, actionId)
			
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine is called to retrieve a dynamic list of elements for an action (or
	# other ConfigUI based) routine
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def getConfigDialogMenu(self, filter=u'', valuesDict=None, typeId="", targetId=0):
		# the routine is designed to pass the call along to the device since most of the
		# time this is device-specific (such as inputs)
		self.logger.threaddebug(u'Dynamic menu requested for Device ID: {0}'.format(targetId))
		if targetId in self.managedDevices:
			return self.managedDevices[targetId].getConfigDialogMenuItems(filter, valuesDict, typeId, targetId)
		else:
			self.logger.debug(u'Call to getConfigDialogMenu for device not managed by this plugin')
			return []
		
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine is called to retrieve a dynamic list of devices that are found on the
	# network matching the service given by the filter
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-	
	def getConfigDialogUPNPDeviceMenu(self, filter=u'', valuesDict=None, typeId=u'', targetId=0):
		self.updateUPNPEnumerationList(typeId)
		return self.parseUPNPDeviceList(self.enumeratedDevices)
		
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine is called whenever the user clicks the "Select" button on a device
	# dialog that asks for selecting from an list of enumerated devices
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-	
	def selectUPNPEnumeratedDeviceForUse(self, valuesDict, typeId, devId):
		menuFieldId   = self.getGUIConfigValue(typeId, GUI_CONFIG_UPNP_ENUMDEVICESFIELDID, u'upnpEnumeratedDevices')
		targetFieldId = self.getGUIConfigValue(typeId, GUI_CONFIG_UPNP_DEVICESELECTTARGETFIELDID, u'httpAddress')
		if valuesDict[menuFieldId] != u'':
			# the target field may be just the address or may be broken up into multiple parts, separated
			# by a colon (in which case the menu ID value must match!)
			fieldsToUpdate = targetFieldId.split(u':')
			valuesSelected = valuesDict[menuFieldId].split(u':')
			
			fieldIdx = 0
			for field in fieldsToUpdate:
				valuesDict[field] = valuesSelected[fieldIdx]
				fieldIdx += 1
				
		return valuesDict
			
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine is called to parse out a uPNP search results list in order to createDeviceObject
	# an indigo-friendly menu; usually will be overridden in plugin descendants
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-	
	def parseUPNPDeviceList(self, deviceList):
		try:
			menuItems = []
			for networkDevice in deviceList:
				self.logger.threaddebug(u'Found uPnP Device: {0}'.format(networkDevice))
				menuItems.append((networkDevice.location, networkDevice.server))
			return menuItems
		except:
			self.logger.warning(u'Error parsing UPNP devices found on the network')
			return []
	
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine should be overridden and should validate any actions which are not
	# already defined within the plugin class
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def validateUnRegisteredActionConfigUi(self, valuesDict, typeId, actionId):
		return (True, valuesDict)
	
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will validate whether or not an IP address is valid as a IPv4 addr
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def isIPv4Valid(self, ip):
		# Make sure a value was entered for the address... an IPv4 should require at least
		# 7 characters (0.0.0.0)
		ip = RPFrameworkUtils.to_unicode(ip)
		if len(ip) < 7:
			return False
			
		# separate the IP address into its components... this limits the format for the
		# user input but is using a fairly standard notation so acceptable
		addressParts = ip.split(u'.')	
		if len(addressParts) != 4:
			return False
				
		for part in addressParts:
			try:
				part = int(part)
				if part < 0 or part > 255:
					return False
			except ValueError:
				return False
				
		# if we make it here, the input should be valid
		return True
		
	
	#/////////////////////////////////////////////////////////////////////////////////////
	# Action execution routines... these allow automatic processing of actions that are
	# known/managed/defined
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will do the work of processing/executing an action; it is assumed that
	# the plugin developer will only assign the action callback to this routine if it
	# should be handled
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def executeAction(self, pluginAction, indigoActionId=u'', indigoDeviceId=u'', paramValues=None):
		# ensure that the actionID specified by the action is a managed action that
		# we can automatically handle
		if pluginAction != None:
			indigoActionId = pluginAction.pluginTypeId
			indigoDeviceId = pluginAction.deviceId
			paramValues = pluginAction.props
		
		# ensure that action and device are both managed... if so they will each appear in
		# the respective member variable dictionaries
		if not indigoActionId in self.indigoActions:
			self.logger.error(u'Execute action called for non-managed action id: {0}'.format(indigoActionId))
			return
		if not indigoDeviceId in self.managedDevices:
			self.logger.error(u'Execute action called for non-managed device id: {0}'.format(indigoDeviceId))
			return
			
		# if execution made it this far then we have the action & device and can execute
		# that action now...
		self.indigoActions[indigoActionId].generateActionCommands(self, self.managedDevices[indigoDeviceId], paramValues)
		
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will toggled the debug setting on all devices managed... it is used to
	# allow setting the debug status w/o restarting the plugin
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def toggleDebugEnabled(self):
		if self.debugLevel == DEBUGLEVEL_NONE:
			self.debugLevel = DEBUGLEVEL_LOW
			self.indigo_log_handler.setLevel(logging.DEBUG)
			self.pluginPrefs["debugLevel"] = DEBUGLEVEL_LOW
			self.logger.info(u'Debug enabled (on Low) by user')
		else:
			self.debugLevel = DEBUGLEVEL_NONE
			self.indigo_log_handler.setLevel(logging.INFO)
			self.pluginPrefs["debugLevel"] = DEBUGLEVEL_NONE
			self.logger.info(u'Debug disabled by user')
		
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will be called when the user has created a request to log the UPnP
	# debug information to the Indigo log
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def logUPnPDevicesFound(self, valuesDict, typeId):
		# perform validation here... only real requirement is to have a "type" selected
		# and this should always be the case...
		errorsDict = indigo.Dict()
		
		# add a new command to the plugin's command queue for processing on a background
		# thread (required to avoid Indigo timing out the operation!)
		self.pluginCommandQueue.put(RPFrameworkCommand.RPFrameworkCommand(RPFrameworkCommand.CMD_DEBUG_LOGUPNPDEVICES, commandPayload=None))
		self.logger.info(u'Scheduled UPnP Device Search')
		
		# return back to the dialog to allow it to close
		return (True, valuesDict, errorsDict)
	
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine processing the logging of the UPnP devices once the plugin spools the
	# command on the background thread
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def logUPnPDevicesFoundProcessing(self):		
		try:
			# perform the UPnP search and logging now...
			self.logger.debug(u'Beginning UPnP Device Search')
			serviceTarget = u'ssdp:all'
			discoveryStarted = time.time()
			discoveredDeviceList = RPFrameworkNetworkingUPnP.uPnPDiscover(serviceTarget, timeout=6)
			
			# create an HTML file that contains the details for all of the devices found on the network
			self.logger.debug(u'UPnP Device Search completed... creating output HTML')
			deviceHtml = u'<html><head><title>UPnP Devices Found</title><style type="text/css">html,body { margin: 0px; padding: 0px; width: 100%; height: 100%; }\n.upnpDevice { margin: 10px 0px 8px 5px; border-bottom: solid 1px #505050; }\n.fieldLabel { width: 140px; display: inline-block; }</style></head><body>'
			deviceHtml += u"<div style='background-color: #3f51b5; width: 100%; height: 50px; border-bottom: solid 2px black;'><span style='color: #a1c057; font-size: 25px; font-weight: bold; line-height: 49px; padding-left: 3px;'>RogueProeliator's RPFramework UPnP Discovery Report</span></div>"
			deviceHtml += u"<div style='border-bottom: solid 2px black; padding: 8px 3px;'><span class='fieldLabel'><b>Requesting Plugin:</b></span>" + self.pluginDisplayName + u"<br /><span class='fieldLabel'><b>Service Query:</b></span>" + serviceTarget + u"<br /><span class='fieldLabel'><b>Date Run:</b></span>" + RPFrameworkUtils.to_unicode(discoveryStarted) + "</div>"	
		
			# loop through each device found...
			for device in discoveredDeviceList:
				deviceHtml += u"<div class='upnpDevice'><span class='fieldLabel'>Location:</span><a href='" + RPFrameworkUtils.to_unicode(device.location) + u"' target='_blank'>" + RPFrameworkUtils.to_unicode(device.location) + u"</a><br /><span class='fieldLabel'>USN:</span>" + RPFrameworkUtils.to_unicode(device.usn) + u"<br /><span class='fieldLabel'>ST:</span>" + RPFrameworkUtils.to_unicode(device.st) + u"<br /><span class='fieldLabel'>Cache Time:</span>" + RPFrameworkUtils.to_unicode(device.cache) + u"s"
				for header in device.allHeaders:
					headerKey = RPFrameworkUtils.to_unicode(header[0])
					if headerKey != u'location' and headerKey != u'usn' and headerKey != u'cache-control' and headerKey != u'st' and headerKey != u'ext':
						deviceHtml += u"<br /><span class='fieldLabel'>" + RPFrameworkUtils.to_unicode(header[0]) + u":</span>" + RPFrameworkUtils.to_unicode(header[1])
				deviceHtml += u"</div>"
		
			deviceHtml += u"</body></html>"
		
			# write out the file...
			self.logger.threaddebug(u"Writing UPnP Device Search HTML to file")
			tempFilename = self.getPluginDirectoryFilePath("tmpUPnPDiscoveryResults.html")
			upnpResultsHtmlFile = open(tempFilename, 'w')
			upnpResultsHtmlFile.write(RPFrameworkUtils.to_str(deviceHtml))
			upnpResultsHtmlFile.close()
		
			# launch the file in a browser window via the command line
			call(["open", tempFilename])
			self.logger.info(u'Created UPnP results temporary file at ' + RPFrameworkUtils.to_unicode(tempFilename))
		except:
			self.logger.error(u'Error generating UPnP report')
	
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will be called whenever the user has chosen to dump the device details
	# to the event log via the menuitem action
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def dumpDeviceDetailsToLog(self, valuesDict, typeId):
		errorsDict = indigo.Dict()
		devicesToDump = valuesDict.get(u'devicesToDump', None)
		
		if devicesToDump is None or len(devicesToDump) == 0:
			errorsDict[u'devicesToDump'] = u'Please select one or more devices'
			return (False, valuesDict, errorsDict)
		else:
			for deviceId in devicesToDump:
				self.logger.info(u'Dumping details for DeviceID: {0}'.format(deviceId))
				dumpDev = indigo.devices[int(deviceId)]
				self.logger.info(RPFrameworkUtils.to_unicode(dumpDev))
			return (True, valuesDict, errorsDict)
		
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine provides the callback for devices based off a Dimmer... since the call
	# comes into the plugin we will pass it off the device now
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def actionControlDimmerRelay(self, action, dev):
		# transform this action into our standard "executeAction" parameters so that the
		# action is processed in a standard way
		indigoActionId = RPFrameworkUtils.to_unicode(action.deviceAction)
		if indigoActionId == u'11':
			indigoActionId = u'StatusRequest'
		
		indigoDeviceId = dev.id
		paramValues = dict()
		paramValues["actionValue"] = RPFrameworkUtils.to_unicode(action.actionValue)
		self.logger.debug(u'Dimmer Command: ActionId={0}; Device={1}; actionValue={2}'.format(indigoActionId, indigoDeviceId, paramValues["actionValue"]))
		
		self.executeAction(None, indigoActionId, indigoDeviceId, paramValues)
		
	
	
	#/////////////////////////////////////////////////////////////////////////////////////
	# Helper routines
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will perform a substitution on a string for all Indigo-values that
	# may be substituted (variables, devices, states, parameters, etc.)
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def substituteIndigoValues(self, input, rpDevice, actionParamValues):
		substitutedString = input
		if substitutedString is None:
			substitutedString = u''
		
		# substitute each parameter value called for in the string; this is done first so that
		# the parameter could call for a substitution
		apMatcher = re.compile(r'%ap:([a-z\d]+)%', re.IGNORECASE)
		for match in apMatcher.finditer(substitutedString):
			substitutedString = substitutedString.replace(RPFrameworkUtils.to_unicode(match.group(0)), RPFrameworkUtils.to_unicode(actionParamValues[match.group(1)]))
			
		# substitute device properties since the substitute method below handles states...
		dpMatcher = re.compile(r'%dp:([a-z\d]+)%', re.IGNORECASE)
		for match in dpMatcher.finditer(substitutedString):
			if type(rpDevice.indigoDevice.pluginProps.get(match.group(1), None)) is indigo.List:
				substitutedString = substitutedString.replace(RPFrameworkUtils.to_unicode(match.group(0)), u"'" + u','.join(rpDevice.indigoDevice.pluginProps.get(match.group(1))) + u"'")
			else:
				substitutedString = substitutedString.replace(RPFrameworkUtils.to_unicode(match.group(0)), RPFrameworkUtils.to_unicode(rpDevice.indigoDevice.pluginProps.get(match.group(1), u'')))
			
		# handle device states for any where we do not specify a device id
		dsMatcher = re.compile(r'%ds:([a-z\d]+)%', re.IGNORECASE)
		for match in dsMatcher.finditer(substitutedString):
			substitutedString = substitutedString.replace(RPFrameworkUtils.to_unicode(match.group(0)), RPFrameworkUtils.to_unicode(rpDevice.indigoDevice.states.get(match.group(1), u'')))
			
		# handle parent device properties (for child devices)
		if rpDevice != None:
			if self.getGUIConfigValue(rpDevice.indigoDevice.deviceTypeId, GUI_CONFIG_ISCHILDDEVICEID, u'false').lower() == 'true':
				parentDeviceId = int(rpDevice.indigoDevice.pluginProps[self.getGUIConfigValue(rpDevice.indigoDevice.deviceTypeId, GUI_CONFIG_PARENTDEVICEIDPROPERTYNAME, u'')])
				if parentDeviceId in self.managedDevices:
					parentRPDevice = self.managedDevices[parentDeviceId]
					pdpMatcher = re.compile(r'%pdp:([a-z\d]+)%', re.IGNORECASE)
					for match in pdpMatcher.finditer(substitutedString):
						if type(parentRPDevice.indigoDevice.pluginProps.get(match.group(1), None)) is indigo.List:
							substitutedString = substitutedString.replace(RPFrameworkUtils.to_unicode(match.group(0)), u"'" + u','.join(parentRPDevice.indigoDevice.pluginProps.get(match.group(1))) + u"'")
						else:
							substitutedString = substitutedString.replace(RPFrameworkUtils.to_unicode(match.group(0)), RPFrameworkUtils.to_unicode(parentRPDevice.indigoDevice.pluginProps.get(match.group(1), u'')))
			
		# handle plugin preferences
		ppMatcher = re.compile(r'%pp:([a-z\d]+)%', re.IGNORECASE)
		for match in ppMatcher.finditer(substitutedString):
			substitutedString = substitutedString.replace(RPFrameworkUtils.to_unicode(match.group(0)), RPFrameworkUtils.to_unicode(self.pluginPrefs.get(match.group(1), u'')))
			
		# perform the standard indigo values substitution...
		substitutedString = self.substitute(substitutedString)
		
		# return the new string to the caller
		return substitutedString
		
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will set a GUI configuration value given the device type, the key and
	# the value for the device
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def putGUIConfigValue(self, deviceTypeId, configKey, configValue):
		if not deviceTypeId in self.managedDeviceGUIConfigs:
			self.managedDeviceGUIConfigs[deviceTypeId] = dict()
		self.managedDeviceGUIConfigs[deviceTypeId][configKey] = configValue
	
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will retrieve a GUI config value for a device type and key; it allows
	# passing in a default value in case the value is not found in the settings
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def getGUIConfigValue(self, deviceTypeId, configKey, defaultValue=u''):
		if not deviceTypeId in self.managedDeviceGUIConfigs:
			return defaultValue
		elif configKey in self.managedDeviceGUIConfigs[deviceTypeId]:
			return self.managedDeviceGUIConfigs[deviceTypeId][configKey]
		else:
			self.logger.threaddebug(u'Returning default GUIConfigValue for {0}: {1}'.format(deviceTypeId, configKey))
			return defaultValue
			
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will retrieve the list of device response definitions for the given
	# device type
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def getDeviceResponseDefinitions(self, deviceTypeId):
		if deviceTypeId in self.deviceResponseDefinitions:
			return self.deviceResponseDefinitions[deviceTypeId]
		else:
			return ()
	
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will update the enumeratedDevices list of devices from the uPNP
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def updateUPNPEnumerationList(self, deviceTypeId):
		uPNPCacheTime = int(self.getGUIConfigValue(deviceTypeId, GUI_CONFIG_UPNP_CACHETIMESEC, u'180'))
		if time.time() > self.lastDeviceEnumeration + uPNPCacheTime or len(self.enumeratedDevices) == 0:
			serviceId = self.getGUIConfigValue(deviceTypeId, GUI_CONFIG_UPNP_SERVICE, u'ssdp:all')
			self.logger.debug(u'Performing uPnP search for: {0}'.format(serviceId))
			discoveredDevices = RPFrameworkNetworkingUPnP.uPnPDiscover(serviceId)
			self.logger.debug(u'Found {0} devices'.format(len(discoveredDevices)))
			
			self.enumeratedDevices = discoveredDevices
			self.lastDeviceEnumeration = time.time()
			
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will get the full path to a file with the given name inside the plugin
	# directory; note this is specifically returning a string, not unicode, to allow
	# use of the IO libraries which require ascii
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def getPluginDirectoryFilePath(self, fileName, pluginName = None):
		if pluginName is None:
			pluginName = self.pluginDisplayName.replace(' Plugin', '')
		indigoBasePath = indigo.server.getInstallFolderPath()
		
		requestedFilePath = os.path.join(indigoBasePath, "Plugins/{0}.indigoPlugin/Contents/Server Plugin/{1}".format(pluginName, fileName))
		return RPFrameworkUtils.to_str(requestedFilePath)
		
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will write out a plugin report to a file; it is intended to give us a
	# standard routine and look/feel for generating reports from the plugins
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def writePluginReport(self, headerText, headerProperties, reportHtml, reportFilename, isRelativePath = True):
		reportHtmlHeader = u"<html><head><title>" + headerText + u"</title><style type='text/css'>html,body { margin: 0px; padding: 0px; width: 100%; height: 100%; }\n.upnpDevice { margin: 10px 0px 8px 5px; border-bottom: solid 1px #505050; }\n.fieldLabel { width: 140px; display: inline-block; }</style></head><body>"
		reportHtmlHeader += u"<div style='background-color: #3f51b5; width: 100%; height: 50px; border-bottom: solid 2px black;'><span style='color: #a1c057; font-size: 25px; font-weight: bold; line-height: 49px; padding-left: 3px;'>" + headerText + u"</span></div>"
		if len(headerProperties) > 0:
			reportHtmlHeader += u"<div style='border-bottom: solid 2px black; padding: 8px 3px;'>"
			for headerProp in headerProperties:
				reportHtmlHeader += u"<div><span class='fieldLabel'><b>" + RPFrameworkUtils.to_unicode(headerProp[0]) + u"</b></span>" + RPFrameworkUtils.to_unicode(headerProp[1]) + u"</div>"
			reportHtmlHeader += u"</div>"
			
		reportFooter = u"</body></html>"
		
		reportFullHtml = reportHtmlHeader + reportHtml + reportFooter
		
		if isRelativePath == True:
			reportFilename = self.getPluginDirectoryFilePath(reportFilename)
		reportOutputFile = open(reportFilename, 'w')
		reportOutputFile.write(RPFrameworkUtils.to_str(reportFullHtml))
		reportOutputFile.close()
		
		return reportFilename
		
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine is called whenever the plugin is updating from an older version, as
	# determined by the plugin property and plugin version number
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def performPluginUpgradeMaintenance(self, oldVersion, newVersion):
		if oldVersion == u'':
			self.logger.info(u'Performing first upgrade/run of version {0}'.format(newVersion))
		else:
			self.logger.info(u'Performing upgrade from {0} to {1}'.format(oldVersion, newVersion))
			
		# execute the version-specific tasks
		if oldVersion == u'':
			# this is the first run of the plugin or the first run of the Indigo 7
			# version... remove unused Requests module if it is present
			pluginBasePath = os.getcwd()
			rpFrameworkRequestsPath = os.path.join(pluginBasePath, "RPFramework/requests")
			if os.path.isdir(rpFrameworkRequestsPath):
				try:
					self.logger.debug(u'Removing unused directory tree at {0}'.format(rpFrameworkRequestsPath))
					shutil.rmtree(rpFrameworkRequestsPath)
				except:
					self.logger.exception(u'Failed to remove legacy "requests" from RPFramework directory')
					
		# allow the descendant classes to perform their own upgrade options
		self.performPluginUpgrade(oldVersion, newVersion)
		
		# update the version flag within our plugin
		self.pluginPrefs['loadedPluginVersion'] = newVersion
		self.logger.debug(u'Completed plugin updating/installation for {0}'.format(newVersion))
		
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine may be used by plugins to perform any upgrades specific to the plugin;
	# it will be called following the framework's update processing
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def performPluginUpgrade(self, oldVersion, newVersion):
		pass
		