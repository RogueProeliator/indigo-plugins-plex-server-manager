#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
Plex Media Client Device Class

Manages state for a Plex media client device, which is a non-communicating
child device that tracks the playback state of a specific client connected
to a Plex Media Server.
"""

# region Python Imports
from typing import TYPE_CHECKING

import indigo

if TYPE_CHECKING:
    from plugin import Plugin
# endregion


class PlexClient:
    """
    Manages state for a Plex media client device.
    
    This is a non-communicating device class that tracks the playback
    state of a specific client connected to a Plex Media Server. The
    actual communication happens through the parent server device.
    
    There are two types of client devices:
    - plexMediaClient: Tracks a specific client by machine ID
    - plexMediaClientSlot: Tracks whatever client is in a numbered slot
    """

    def __init__(self, plugin: 'Plugin', device: indigo.Device):
        """
        Initialize the Plex client manager.
        
        Args:
            plugin: Reference to the main plugin instance
            device: The Indigo device this manager controls
        """
        self.host_plugin = plugin
        self.device = device
        self.logger = plugin.logger
        
        # Command ID counter for playback commands
        self._command_id = 0
        
        self.logger.debug(f"PlexClient initialized for {device.name}")

    def get_next_command_id(self) -> int:
        """
        Get the next command ID for client playback commands.
        
        The command ID is incremented with each call to ensure
        unique command identification.
        
        Returns:
            The next command ID to use
        """
        self._command_id += 1
        return self._command_id

    def update_states(self, states: list) -> None:
        """
        Update device states on the Indigo server.
        
        Args:
            states: List of state dictionaries with 'key' and 'value' keys
        """
        try:
            self.device.updateStatesOnServer(states)
        except Exception as e:
            self.logger.error(f"Error updating states for {self.device.name}: {e}")

    def mark_disconnected(self) -> None:
        """Mark this client as disconnected and clear all playback states."""
        disconnected_states = [
            {'key': 'clientConnectionStatus', 'value': 'disconnected'},
            {'key': 'clientAddress', 'value': ''},
            {'key': 'clientPort', 'value': 0},
            {'key': 'currentUser', 'value': ''},
            {'key': 'currentlyPlayingKey', 'value': ''},
            {'key': 'currentlyPlayingMediaType', 'value': 'unknown'},
            {'key': 'currentlyPlayingParentKey', 'value': ''},
            {'key': 'currentlyPlayingTitle', 'value': ''},
            {'key': 'currentlyPlayingSummary', 'value': ''},
            {'key': 'currentlyPlayingArtUrl', 'value': ''},
            {'key': 'currentlyPlayingThumbnailUrl', 'value': ''},
            {'key': 'currentlyPlayingParentTitle', 'value': ''},
            {'key': 'currentlyPlayingParentThumbnailUrl', 'value': ''},
            {'key': 'currentlyPlayingGrandparentKey', 'value': ''},
            {'key': 'currentlyPlayingGrandparentTitle', 'value': ''},
            {'key': 'currentlyPlayingGrandparentArtUrl', 'value': ''},
            {'key': 'currentlyPlayingGrandparentThumbnailUrl', 'value': ''},
            {'key': 'currentlPlayingTitleYear', 'value': ''},
            {'key': 'currentlyPlayingStarRating', 'value': ''},
            {'key': 'currentlyPlayingContentRating', 'value': ''},
            {'key': 'currentlyPlayingContentResolution', 'value': ''},
            {'key': 'currentlyPlayingContentLengthMS', 'value': 0},
            {'key': 'currentlyPlayingContentLengthDisplay', 'value': ''},
            {'key': 'currentlyPlayingContentLengthOffset', 'value': 0},
            {'key': 'currentlyPlayingContentLengthOffsetDisplay', 'value': ''},
            {'key': 'currentlyPlayingContentPercentComplete', 'value': 0},
            {'key': 'currentlyPlayingGenre', 'value': ''},
            {'key': 'playerDeviceTitle', 'value': ''}
        ]
        
        # For slot devices, also clear the client ID
        if self.device.deviceTypeId == 'plexMediaClientSlot':
            disconnected_states.append({'key': 'clientId', 'value': ''})
        
        self.update_states(disconnected_states)

    @property
    def is_slot_device(self) -> bool:
        """Check if this is a slot-based client device."""
        return self.device.deviceTypeId == 'plexMediaClientSlot'

    @property
    def client_id(self) -> str:
        """
        Get the client identifier.
        
        For regular clients, this is the machine ID from plugin props.
        For slot devices, this is the current client ID from state.
        
        Returns:
            The client identifier string
        """
        if self.is_slot_device:
            return self.device.states.get('clientId', '')
        else:
            return self.device.pluginProps.get('plexClientId', '')

    @property
    def slot_number(self) -> int:
        """
        Get the slot number for slot devices.
        
        Returns:
            The slot number, or 0 if not a slot device
        """
        if not self.is_slot_device:
            return 0
        
        slot_str = self.device.pluginProps.get('plexClientId', 'Slot 0')
        try:
            return int(slot_str.replace('Slot ', ''))
        except ValueError:
            return 0

    @property
    def is_connected(self) -> bool:
        """Check if this client is currently connected."""
        status = self.device.states.get('clientConnectionStatus', 'disconnected')
        return status != 'disconnected'

    @property
    def parent_server_id(self) -> int:
        """Get the ID of the parent media server device."""
        try:
            return int(self.device.pluginProps.get('mediaServer', '0'))
        except ValueError:
            return 0
