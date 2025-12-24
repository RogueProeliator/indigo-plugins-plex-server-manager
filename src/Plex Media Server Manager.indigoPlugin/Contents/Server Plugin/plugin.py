#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
Plex Media Server Manager Plugin for Indigo
Developed by RogueProeliator <rp@rogueproeliator.com>

This plugin allows Indigo to monitor Plex Media Servers and track connected clients,
currently playing media, and other status information.

Command structure based on the PMS published API, available here:
https://code.google.com/p/plex-api/wiki/MediaContainer

Rewritten for Indigo 2025.1 without RPFramework dependency.
"""

# region Python Imports
import logging
import shutil
import time
from typing import Dict, Optional, Tuple, List

import requests
import indigo

from plex_server import PlexServer
from plex_client import PlexClient
# endregion

# region Constants
LOG_FORMAT = '%(asctime)s.%(msecs)03d\t%(levelname)-10s\t%(name)s.%(funcName)-28s %(message)s'

# Debug level mapping from plugin prefs to Python logging levels
DEBUG_LEVEL_MAP = {
    "0": logging.WARNING,  # Off = minimal logging
    "1": logging.INFO,     # Low = info level
    "2": logging.DEBUG     # High = debug level
}
# endregion


class Plugin(indigo.PluginBase):
    """
    Main plugin class for Plex Media Server Manager.
    
    This plugin monitors Plex Media Servers and their connected clients,
    tracking playback status, media information, and connection states.
    """

    # ========================================================================
    # region Class Construction and Destruction
    # ========================================================================
    def __init__(self, plugin_id: str, plugin_display_name: str, 
                 plugin_version: str, plugin_prefs: indigo.Dict):
        """
        Initialize the plugin.
        
        Args:
            plugin_id: The unique identifier for this plugin
            plugin_display_name: Human-readable plugin name
            plugin_version: Plugin version string
            plugin_prefs: Saved plugin preferences
        """
        super().__init__(plugin_id, plugin_display_name, plugin_version, plugin_prefs)
        
        # Initialization flags
        self.plugin_is_initializing = True
        self.plugin_is_shutting_down = False
        
        # Configure logging
        debug_level_str = self.pluginPrefs.get('debugLevel', '0')
        self.debug_level = DEBUG_LEVEL_MAP.get(debug_level_str, logging.WARNING)
        
        self.plugin_file_handler.setFormatter(
            logging.Formatter(fmt=LOG_FORMAT, datefmt='%Y-%m-%d %H:%M:%S')
        )
        self.indigo_log_handler.setLevel(self.debug_level)
        
        # Device tracking - maps device ID to device manager instance
        self.managed_devices: Dict[int, PlexServer] = {}
        
        # Client devices tracked by their parent server
        self.client_devices: Dict[int, PlexClient] = {}
        
        self.logger.debug("Plugin __init__ complete")
        self.plugin_is_initializing = False

    # endregion
    # ========================================================================
    
    # ========================================================================
    # region Plugin Lifecycle Methods
    # ========================================================================
    def startup(self) -> None:
        """
        Called after plugin initialization.
        
        Perform any startup tasks here.
        """
        self.logger.info("Plugin starting...")
        
        # Initialize all server devices to a known state
        for dev in indigo.devices.iter("self"):
            if dev.deviceTypeId == 'plexMediaServer':
                self.logger.debug(f"Initializing server device: {dev.name}")
                dev.updateStateOnServer('connectionState', value='Starting')
        
        self.logger.info("Plugin started successfully")

    def shutdown(self) -> None:
        """
        Called when plugin is shutting down.
        
        Clean up any resources, stop threads, etc.
        """
        self.logger.info("Plugin shutting down...")
        self.plugin_is_shutting_down = True
        
        # Stop all device threads
        for dev_id, plex_server in self.managed_devices.items():
            try:
                plex_server.stop()
            except Exception as e:
                self.logger.warning(f"Error stopping device {dev_id}: {e}")
        
        self.logger.info("Plugin shutdown complete")

    def runConcurrentThread(self) -> None:
        """
        Main plugin loop for status polling.
        
        This method runs in a separate thread and is responsible for
        periodic status updates of all managed server devices.
        """
        self.logger.debug("Concurrent thread starting")
        self.sleep(1)  # Initial pause
        
        try:
            while True:
                # Check each managed server device for status update
                for dev_id, plex_server in list(self.managed_devices.items()):
                    try:
                        dev = indigo.devices.get(dev_id)
                        if dev and self._time_to_update(dev, plex_server):
                            plex_server.queue_status_update()
                    except Exception as e:
                        self.logger.error(f"Error checking device {dev_id}: {e}")
                
                self.sleep(2)  # Main loop interval
                
        except self.StopThread:
            self.logger.info("Concurrent thread stopping")

    # endregion
    # ========================================================================
    
    # ========================================================================
    # region Device Communication Methods
    # ========================================================================
    def deviceStartComm(self, dev: indigo.Device) -> None:
        """
        Called when device communication should start.
        
        Args:
            dev: The Indigo device to start communication with
        """
        self.logger.info(f"Starting communication with {dev.name}")
        
        try:
            if dev.deviceTypeId == 'plexMediaServer':
                # Update state to indicate we're starting
                dev.updateStateOnServer('connectionState', value='Starting')
                
                # Create server device manager instance
                plex_server = PlexServer(self, dev)
                self.managed_devices[dev.id] = plex_server
                plex_server.start()
                
                # Trigger state list refresh if needed
                dev.stateListOrDisplayStateIdChanged()
                
                self.logger.debug(f"Server device {dev.name} communication started")
                
            elif dev.deviceTypeId in ('plexMediaClient', 'plexMediaClientSlot'):
                # Update state to indicate we're starting
                dev.updateStateOnServer('clientConnectionStatus', value='disconnected')
                
                # Create client device manager instance
                plex_client = PlexClient(self, dev)
                self.client_devices[dev.id] = plex_client
                
                # Register with parent server
                media_server_id = int(dev.pluginProps.get('mediaServer', '0'))
                if media_server_id in self.managed_devices:
                    self.managed_devices[media_server_id].register_client(dev, plex_client)
                
                # Trigger state list refresh if needed
                dev.stateListOrDisplayStateIdChanged()
                
                self.logger.debug(f"Client device {dev.name} communication started")
            
        except Exception as e:
            self.logger.error(f"Failed to start communication with {dev.name}: {e}")
            if dev.deviceTypeId == 'plexMediaServer':
                dev.updateStateOnServer('connectionState', value='Error')
            else:
                dev.updateStateOnServer('clientConnectionStatus', value='disconnected')

    def deviceStopComm(self, dev: indigo.Device) -> None:
        """
        Called when device communication should stop.
        
        Args:
            dev: The Indigo device to stop communication with
        """
        self.logger.info(f"Stopping communication with {dev.name}")
        
        try:
            if dev.deviceTypeId == 'plexMediaServer':
                # Stop and remove server device manager
                if dev.id in self.managed_devices:
                    plex_server = self.managed_devices[dev.id]
                    plex_server.stop()
                    del self.managed_devices[dev.id]
                
                # Update device state
                dev.setErrorStateOnServer("")
                dev.updateStateOnServer('connectionState', value='Disabled')
                
            elif dev.deviceTypeId in ('plexMediaClient', 'plexMediaClientSlot'):
                # Unregister from parent server
                media_server_id = int(dev.pluginProps.get('mediaServer', '0'))
                if media_server_id in self.managed_devices:
                    self.managed_devices[media_server_id].unregister_client(dev)
                
                # Remove from client devices
                if dev.id in self.client_devices:
                    del self.client_devices[dev.id]
                
                # Update device state
                dev.setErrorStateOnServer("")
                dev.updateStateOnServer('clientConnectionStatus', value='disconnected')
            
            self.logger.debug(f"Device {dev.name} communication stopped")
            
        except Exception as e:
            self.logger.warning(f"Error stopping communication with {dev.name}: {e}")

    def didDeviceCommPropertyChange(self, orig_dev: indigo.Device, 
                                    new_dev: indigo.Device) -> bool:
        """
        Check if device properties changed in a way that requires restart.
        
        Args:
            orig_dev: Original device state
            new_dev: New device state
            
        Returns:
            True if communication should be restarted
        """
        # Properties that require restart if changed
        restart_props = ['httpAddress', 'httpPort', 'requestMethod', 'pollInterval',
                        'loginRequired', 'plexUsername', 'plexPassword', 'mediaServer',
                        'plexClientId']
        
        for prop in restart_props:
            if orig_dev.pluginProps.get(prop) != new_dev.pluginProps.get(prop):
                self.logger.debug(f"Property {prop} changed, requiring restart")
                return True
        
        return False

    # endregion
    # ========================================================================
    
    # ========================================================================
    # region Configuration UI Callbacks
    # ========================================================================
    def getDeviceConfigUiValues(self, pluginProps: indigo.Dict, 
                                 typeId: str, devId: int) -> Tuple[indigo.Dict, indigo.Dict]:
        """
        Get default values for device config UI.
        
        Args:
            pluginProps: Current plugin properties
            typeId: Device type ID
            devId: Device ID (0 for new device)
            
        Returns:
            Tuple of (valuesDict, errorsDict)
        """
        values_dict = indigo.Dict(pluginProps)
        errors_dict = indigo.Dict()
        
        if typeId in ('plexMediaClient', 'plexMediaClientSlot') and len(self.managed_devices) > 0:
            # If the device does not define a media server, grab the first available
            if not values_dict.get('mediaServer'):
                for dev in indigo.devices.iter('self'):
                    if dev.deviceTypeId == 'plexMediaServer':
                        values_dict['mediaServer'] = str(dev.id)
                        break
        
        return (values_dict, errors_dict)

    def validateDeviceConfigUi(self, values_dict: indigo.Dict, 
                               type_id: str, dev_id: int) -> Tuple[bool, indigo.Dict]:
        """
        Validate device configuration.
        
        Args:
            values_dict: Dialog values
            type_id: Device type ID
            dev_id: Device ID (0 for new device)
            
        Returns:
            Tuple of (valid, values_dict) or (False, values_dict, errors_dict)
        """
        errors_dict = indigo.Dict()
        
        if type_id == 'plexMediaServer':
            # Validate HTTP address
            http_address = values_dict.get("httpAddress", "").strip()
            if not http_address:
                errors_dict["httpAddress"] = "Please enter a hostname or IP address"
            
            # Validate port
            try:
                port = int(values_dict.get("httpPort", "32400"))
                if port < 1 or port > 65535:
                    errors_dict["httpPort"] = "Port must be between 1 and 65535"
            except ValueError:
                errors_dict["httpPort"] = "Please enter a valid port number"
            
            # Validate authentication fields if login required
            if str(values_dict.get('loginRequired', 'false')).lower() == 'true':
                if not values_dict.get('plexUsername', '').strip():
                    errors_dict['plexUsername'] = "Username is required when login is enabled"
                if not values_dict.get('plexPassword', '').strip():
                    errors_dict['plexPassword'] = "Password is required when login is enabled"
            else:
                # Clear credentials if login not required
                values_dict['plexUsername'] = ''
                values_dict['plexPassword'] = ''
            
            # Set address for display
            values_dict["address"] = http_address
            
        elif type_id in ('plexMediaClient', 'plexMediaClientSlot'):
            # Validate media server selection
            if not values_dict.get('mediaServer'):
                errors_dict['mediaServer'] = "Please select a Plex Media Server"
            
            # Validate client selection
            if not values_dict.get('plexClientId'):
                errors_dict['plexClientId'] = "Please select a client"
            
            # Set address for display
            values_dict['address'] = values_dict.get('plexClientId', '')
        
        if len(errors_dict) > 0:
            errors_dict["showAlertText"] = "Please correct the highlighted errors."
            return False, values_dict, errors_dict
        
        return True, values_dict

    def validatePrefsConfigUi(self, values_dict: indigo.Dict) -> Tuple[bool, indigo.Dict]:
        """
        Validate plugin preferences configuration.
        
        Args:
            values_dict: Dialog values
            
        Returns:
            Tuple of (valid, values_dict)
        """
        return True, values_dict

    def closedPrefsConfigUi(self, values_dict: indigo.Dict, 
                            user_cancelled: bool) -> None:
        """
        Called when plugin prefs dialog closes.
        
        Args:
            values_dict: Final dialog values
            user_cancelled: True if user cancelled
        """
        if not user_cancelled:
            # Update debug level
            debug_level_str = values_dict.get('debugLevel', '0')
            self.debug_level = DEBUG_LEVEL_MAP.get(debug_level_str, logging.WARNING)
            self.indigo_log_handler.setLevel(self.debug_level)
            
            self.logger.info("Plugin preferences saved")
        else:
            self.logger.debug("Plugin preferences cancelled")

    # endregion
    # ========================================================================
    
    # ========================================================================
    # region Dynamic List Callbacks
    # ========================================================================
    def getConnectedClients(self, filter: str = "", values_dict: indigo.Dict = None,
                            type_id: str = "", target_id: int = 0) -> List[Tuple[str, str]]:
        """
        Get list of connected clients for device configuration.
        
        Args:
            filter: Filter string (unused)
            values_dict: Current dialog values
            type_id: Device type ID
            target_id: Target device ID
            
        Returns:
            List of (client_id, client_name) tuples
        """
        media_server_id = values_dict.get('mediaServer', '')
        self.logger.debug(f'Retrieving clients for device of type {type_id}')
        
        if media_server_id == '':
            self.logger.debug('Cannot retrieve connected clients - no media server specified.')
            return []
        
        try:
            server_id = int(media_server_id)
            if server_id not in self.managed_devices:
                return []
            
            if type_id == 'plexMediaClientSlot':
                return self.managed_devices[server_id].get_client_slot_menu()
            else:
                selected_client = values_dict.get('plexClientId', '')
                return self.managed_devices[server_id].get_connected_clients_menu(selected_client)
        except (ValueError, KeyError) as e:
            self.logger.error(f"Error getting clients: {e}")
            return []

    def reloadConnectedClientsList(self, filter: str = "", values_dict: indigo.Dict = None,
                                   type_id: str = "", target_id: int = 0) -> None:
        """
        Dummy routine to refresh dynamic menus.
        
        Called when user clicks "Reload Client List" button.
        """
        pass

    # endregion
    # ========================================================================
    
    # ========================================================================
    # region Action Callbacks
    # ========================================================================
    def downloadCurrentlyPlayingArt(self, pluginAction: indigo.ActionGroup) -> None:
        """
        Download currently playing artwork for a Plex client device.
        
        Args:
            pluginAction: The action to execute
        """
        params = pluginAction.props
        device_id = pluginAction.deviceId
        
        # Validate required parameters
        destination_fn = params.get('saveToFilename', '').strip()
        if not destination_fn:
            self.logger.error("Download artwork action: No destination filename specified")
            return
        
        art_element = params.get('artElement', '')
        if not art_element:
            self.logger.error("Download artwork action: No art element specified")
            return
        
        # Get the client device
        if device_id not in self.client_devices:
            self.logger.error(f"Client device {device_id} not found")
            return
        
        client_device = self.client_devices[device_id]
        dev = indigo.devices[device_id]
        
        # Map art element to state key
        art_state_map = {
            'thumb': 'currentlyPlayingThumbnailUrl',
            'art': 'currentlyPlayingArtUrl',
            'parentThumb': 'currentlyPlayingParentThumbnailUrl',
            'grandparentArt': 'currentlyPlayingGrandparentArtUrl',
            'grandparentThumb': 'currentlyPlayingGrandparentThumbnailUrl'
        }
        
        state_key = art_state_map.get(art_element, '')
        if not state_key:
            self.logger.error(f"Invalid art element: {art_element}")
            return
        
        art_url_path = dev.states.get(state_key, '')
        
        # Handle no art available
        if not art_url_path:
            self.logger.debug(f'No art found for {art_element} on client {device_id}')
            
            placeholder_fn = params.get('noArtworkFilename', '').strip()
            if placeholder_fn:
                try:
                    shutil.copy2(placeholder_fn, destination_fn)
                except Exception as e:
                    self.logger.error(f'Error copying placeholder image: {e}')
            return
        
        # Get the parent server device
        server_id = int(dev.pluginProps.get('mediaServer', '0'))
        if server_id not in self.managed_devices:
            self.logger.error("Parent media server not found")
            return
        
        plex_server = self.managed_devices[server_id]
        
        # Parse resize options
        resize_width = 0
        resize_height = 0
        resize_mode = params.get('resizeMode', 'none')
        
        if resize_mode == 'exact':
            resize_width = int(params.get('imageResizeWidth', '0') or '0')
            resize_height = int(params.get('imageResizeHeight', '0') or '0')
        elif resize_mode == 'max':
            resize_width = int(params.get('imageResizeMaxDimension', '0') or '0')
        
        # Queue the download
        self.logger.debug(f'Scheduling download of art at {art_url_path}')
        plex_server.queue_image_download(art_url_path, destination_fn, resize_width, resize_height)

    def sendClientPlaybackCommand(self, pluginAction: indigo.ActionGroup) -> None:
        """
        Send a playback command to a Plex client.
        
        Args:
            pluginAction: The action to execute
        """
        params = pluginAction.props
        device_id = pluginAction.deviceId
        
        # Get the command to send
        command = params.get('commandToSend', '')
        if not command:
            self.logger.error("No playback command specified")
            return
        
        # Get media type (optional)
        media_type = params.get('mediaType', '')
        
        # Get the client device
        if device_id not in self.client_devices:
            self.logger.error(f"Client device {device_id} not found")
            return
        
        client = self.client_devices[device_id]
        dev = indigo.devices[device_id]
        
        # Get client address info
        client_address = dev.states.get('clientAddress', '')
        client_port = int(dev.states.get('clientPort', '0'))
        
        # Get client machine ID
        if dev.deviceTypeId == 'plexMediaClientSlot':
            client_machine_id = dev.states.get('clientId', '')
        else:
            client_machine_id = dev.pluginProps.get('plexClientId', '')
        
        if not client_address or client_port <= 0 or not client_machine_id:
            self.logger.warning('Cannot send playback command - client address not determined')
            return
        
        # Get the parent server
        server_id = int(dev.pluginProps.get('mediaServer', '0'))
        if server_id not in self.managed_devices:
            self.logger.error("Parent media server not found")
            return
        
        plex_server = self.managed_devices[server_id]
        
        # Send the command
        plex_server.send_client_playback_command(
            client_address, client_port, client_machine_id,
            command, media_type, client.get_next_command_id()
        )

    # endregion
    # ========================================================================
    
    # ========================================================================
    # region Menu Item Callbacks
    # ========================================================================
    def toggleDebugEnabled(self) -> None:
        """Toggle debug logging on/off."""
        if self.debug_level == logging.DEBUG:
            self.debug_level = logging.WARNING
            self.indigo_log_handler.setLevel(self.debug_level)
            self.pluginPrefs["debugLevel"] = "0"
            indigo.server.log("Debug logging disabled")
        else:
            self.debug_level = logging.DEBUG
            self.indigo_log_handler.setLevel(self.debug_level)
            self.pluginPrefs["debugLevel"] = "2"
            indigo.server.log("Debug logging enabled")

    def dumpDeviceDetailsToLog(self, values_dict: indigo.Dict, 
                               type_id: str) -> Tuple[bool, indigo.Dict]:
        """
        Dump device details to the event log.
        
        Args:
            values_dict: Dialog values
            type_id: Type identifier
            
        Returns:
            Tuple of (success, values_dict)
        """
        device_ids = values_dict.get("devicesToDump", [])
        
        for dev_id_str in device_ids:
            try:
                dev_id = int(dev_id_str)
                dev = indigo.devices[dev_id]
                
                indigo.server.log("")
                indigo.server.log(f"===== Device Details: {dev.name} =====")
                indigo.server.log(f"Device ID: {dev.id}")
                indigo.server.log(f"Device Type: {dev.deviceTypeId}")
                indigo.server.log(f"Enabled: {dev.enabled}")
                indigo.server.log(f"Address: {dev.address}")
                
                indigo.server.log("----- Plugin Properties -----")
                for key, value in dev.pluginProps.items():
                    # Mask password
                    if 'password' in key.lower():
                        value = '********'
                    indigo.server.log(f"  {key}: {value}")
                
                indigo.server.log("----- States -----")
                for key, value in dev.states.items():
                    indigo.server.log(f"  {key}: {value}")
                
                indigo.server.log("================================")
                
            except Exception as e:
                self.logger.error(f"Error dumping device {dev_id_str}: {e}")
        
        return True, values_dict

    def checkForUpdateImmediate(self, values_dict: indigo.Dict,
                                type_id: str) -> indigo.Dict:
        """
        Check for plugin updates.
        
        This is a placeholder - updates are now handled by Indigo's
        built-in plugin library system.
        
        Args:
            values_dict: Dialog values
            type_id: Type identifier
            
        Returns:
            Updated values_dict
        """
        values_dict['currentVersion'] = self.pluginVersion
        values_dict['latestVersion'] = self.pluginVersion
        values_dict['versionCheckResults'] = '2'  # Up to date
        
        return values_dict

    # endregion
    # ========================================================================
    
    # ========================================================================
    # region Helper Methods
    # ========================================================================
    def _time_to_update(self, dev: indigo.Device, plex_server: PlexServer) -> bool:
        """
        Check if device is due for status update.
        
        Args:
            dev: The Indigo device to check
            plex_server: The PlexServer manager instance
            
        Returns:
            True if device should be updated
        """
        if not dev.enabled:
            return False
        
        poll_interval = int(dev.pluginProps.get("pollInterval", "20"))
        if poll_interval <= 0:
            return False  # Polling disabled
        
        # Check time since last update
        elapsed = time.time() - plex_server.last_update_time
        return elapsed >= poll_interval

    # endregion
    # ========================================================================
