#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
Plex Media Server Device Communication Class

Manages communication with a single Plex Media Server via its HTTP API.
This class handles all HTTP communication, command queuing, and state updates
for a Plex server device, including tracking connected clients and sessions.
"""

# region Python Imports
import datetime
import os
import shutil
import threading
import time
import xml.etree.ElementTree as ET
from queue import Queue, Empty
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple, List, Dict, Any, TYPE_CHECKING

import requests
import urllib3
import indigo

from plex_media_container import PlexMediaContainer, MEDIACONTAINERTYPE_SERVERNODE, \
    MEDIACONTAINERTYPE_CLIENTLIST, MEDIACONTAINERTYPE_SESSIONLIST

if TYPE_CHECKING:
    from plugin import Plugin
    from plex_client import PlexClient
# endregion


class CommandType(Enum):
    """Types of commands that can be queued."""
    STATUS_UPDATE = "status_update"
    DOWNLOAD_IMAGE = "download_image"
    CLIENT_COMMAND = "client_command"
    GET_METADATA = "get_metadata"


@dataclass
class Command:
    """A command to be executed on the Plex server."""
    command_type: CommandType
    payload: Any = None


class PlexServer:
    """
    Manages communication with a single Plex Media Server.
    
    Features:
    - Threaded command processing via queue
    - Server status polling
    - Session/client tracking
    - Authentication via plex.tv
    - Image download for artwork
    
    All commands are queued and processed in a separate thread to avoid
    blocking the main Indigo thread.
    """
    
    DEFAULT_TIMEOUT = 10
    MAX_BAD_CALLS = 5

    def __init__(self, plugin: 'Plugin', device: indigo.Device):
        """
        Initialize the Plex server manager.
        
        Args:
            plugin: Reference to the main plugin instance
            device: The Indigo device this manager controls
        """
        self.host_plugin = plugin
        self.device = device
        self.logger = plugin.logger
        
        # Address configuration
        self._http_address = device.pluginProps.get('httpAddress', '')
        self._http_port = int(device.pluginProps.get('httpPort', '32400'))
        self._request_method = device.pluginProps.get('requestMethod', 'http')
        
        # Authentication
        self._login_required = str(device.pluginProps.get('loginRequired', 'false')).lower() == 'true'
        self._username = device.pluginProps.get('plexUsername', '')
        self._password = device.pluginProps.get('plexPassword', '')
        self._security_token = ''
        
        # Threading infrastructure
        self.queue: Queue = Queue()
        self.thread: Optional[threading.Thread] = None
        self._stop_thread = False
        
        # Status tracking
        self.bad_calls = 0
        self.last_update_time: float = 0
        
        # Client tracking
        self._current_client_list: List[Tuple[str, str]] = []
        self._child_devices: Dict[str, 'PlexClient'] = {}  # keyed by client ID or slot ID
        
        # Suppress SSL certificate verification warnings for self-signed certs
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        self.logger.debug(f"PlexServer initialized for {device.name}")

    # ========================================================================
    # region Lifecycle Methods
    # ========================================================================
    def start(self) -> None:
        """Start the device communication thread."""
        self._stop_thread = False
        self.thread = threading.Thread(
            target=self._process_queue,
            name=f"Plex-{self.device.id}",
            daemon=True
        )
        self.thread.start()
        self.logger.debug(f"Device thread started for {self.device.name}")
        
        # Queue an initial status update
        self.queue_status_update()

    def stop(self) -> None:
        """Stop the device communication thread."""
        self._stop_thread = True
        
        # Add a None command to wake up the thread
        self.queue.put(None)
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
            
        self.logger.debug(f"Device thread stopped for {self.device.name}")

    def _process_queue(self) -> None:
        """Main thread loop - processes commands from queue."""
        while not self._stop_thread:
            try:
                command = self.queue.get(timeout=0.5)
                
                if command is None:
                    continue
                
                self._execute_command(command)
                
            except Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error processing queue for {self.device.name}: {e}")

    def _execute_command(self, command: Command) -> None:
        """
        Execute a command from the queue.
        
        Args:
            command: The command to execute
        """
        try:
            if command.command_type == CommandType.STATUS_UPDATE:
                self._do_status_update()
                
            elif command.command_type == CommandType.DOWNLOAD_IMAGE:
                url_path, destination, width, height = command.payload
                self._do_download_image(url_path, destination, width, height)
                
            elif command.command_type == CommandType.CLIENT_COMMAND:
                self._do_client_command(command.payload)
                
            elif command.command_type == CommandType.GET_METADATA:
                device_id, media_key = command.payload
                self._do_get_metadata(device_id, media_key)
                
        except Exception as e:
            self.logger.error(f"Error executing {command.command_type}: {e}")

    # endregion
    # ========================================================================
    
    # ========================================================================
    # region Public Command Methods
    # ========================================================================
    def queue_status_update(self) -> None:
        """Queue a status update command."""
        self.queue.put(Command(CommandType.STATUS_UPDATE))

    def queue_image_download(self, url_path: str, destination: str, 
                            width: int = 0, height: int = 0) -> None:
        """
        Queue an image download command.
        
        Args:
            url_path: The URL path for the image
            destination: Local file path to save the image
            width: Optional resize width
            height: Optional resize height
        """
        self.queue.put(Command(
            CommandType.DOWNLOAD_IMAGE,
            payload=(url_path, destination, width, height)
        ))
        self.logger.debug(f"Queued image download: {url_path}")

    def queue_get_metadata(self, device_id: int, media_key: str) -> None:
        """
        Queue a metadata retrieval command.
        
        Args:
            device_id: The client device ID to update
            media_key: The media key to retrieve metadata for
        """
        self.queue.put(Command(
            CommandType.GET_METADATA,
            payload=(device_id, media_key)
        ))

    def send_client_playback_command(self, client_address: str, client_port: int,
                                     client_machine_id: str, command: str,
                                     media_type: str, command_id: int) -> None:
        """
        Send a playback command to a Plex client.
        
        Args:
            client_address: Client IP address
            client_port: Client port number
            client_machine_id: Client machine identifier
            command: The command to send (e.g., 'playback-play')
            media_type: Optional media type filter
            command_id: Unique command ID
        """
        # Ensure we have a valid security token
        self._retrieve_security_token()
        
        # Build media type parameter
        media_type_param = f'&mtype={media_type}' if media_type else ''
        
        # Build target URL - convert command format (e.g., 'playback-play' -> 'playback/play')
        command_path = command.replace('-', '/')
        target_url = f'http://{client_address}:{client_port}/player/{command_path}?commandID={command_id}{media_type_param}'
        
        # Build Plex headers
        plex_headers = {
            'X-Plex-Platform': 'Indigo',
            'X-Plex-Platform-Version': indigo.server.apiVersion,
            'X-Plex-Provides': 'controller',
            'X-Plex-Client-Identifier': indigo.server.getDbName(),
            'X-Plex-Product': 'Plex Media Server Manager',
            'X-Plex-Version': self.host_plugin.pluginVersion,
            'X-Plex-Device': 'Indigo HA Server',
            'X-Plex-Device-Name': 'Indigo Plugin',
            'X-Plex-Token': self._security_token,
            'X-Plex-Target-Client-Identifier': client_machine_id
        }
        
        self.logger.debug(f'Sending client playback command: {target_url}')
        
        try:
            response = requests.get(target_url, headers=plex_headers, timeout=self.DEFAULT_TIMEOUT, verify=False)
            self.logger.debug(f'Client Command Response: [{response.status_code}] {response.text}')
        except Exception as e:
            self.logger.error(f'Error sending client command: {e}')

    # endregion
    # ========================================================================
    
    # ========================================================================
    # region Client Registration
    # ========================================================================
    def register_client(self, device: indigo.Device, client: 'PlexClient') -> None:
        """
        Register a client device with this server.
        
        Args:
            device: The Indigo client device
            client: The PlexClient manager instance
        """
        if device.deviceTypeId == 'plexMediaClientSlot':
            # Use slot ID as key (e.g., "Slot 1")
            client_key = device.pluginProps.get('plexClientId', '')
        else:
            # Use client machine ID as key
            client_key = device.pluginProps.get('plexClientId', '')
        
        if client_key:
            self._child_devices[client_key] = client
            self.logger.debug(f"Registered client {client_key} with server {self.device.name}")

    def unregister_client(self, device: indigo.Device) -> None:
        """
        Unregister a client device from this server.
        
        Args:
            device: The Indigo client device to unregister
        """
        if device.deviceTypeId == 'plexMediaClientSlot':
            client_key = device.pluginProps.get('plexClientId', '')
        else:
            client_key = device.pluginProps.get('plexClientId', '')
        
        if client_key and client_key in self._child_devices:
            del self._child_devices[client_key]
            self.logger.debug(f"Unregistered client {client_key} from server {self.device.name}")

    # endregion
    # ========================================================================
    
    # ========================================================================
    # region Menu Generation Methods
    # ========================================================================
    def get_connected_clients_menu(self, selected_client: str = '') -> List[Tuple[str, str]]:
        """
        Get list of connected clients for config dialog menu.
        
        Args:
            selected_client: Currently selected client ID to ensure it's in list
            
        Returns:
            List of (client_id, client_name) tuples
        """
        clients = list(self._current_client_list)
        
        # Ensure selected client is in list
        if selected_client:
            found = any(c[0] == selected_client for c in clients)
            if not found:
                clients.append((selected_client, selected_client))
        
        return clients

    def get_client_slot_menu(self) -> List[Tuple[str, str]]:
        """
        Get list of available client slots for config dialog.
        
        Returns:
            List of (slot_id, slot_name) tuples
        """
        return [(f"Slot {i}", f"Slot {i}") for i in range(1, 11)]

    # endregion
    # ========================================================================
    
    # ========================================================================
    # region Command Implementations
    # ========================================================================
    def _do_status_update(self) -> None:
        """Execute server status update queries."""
        base_url = self._get_base_url()
        headers = self._get_auth_headers()
        
        # Query server root for basic info
        try:
            response = self._get(f"{base_url}/", headers)
            if response:
                self._handle_server_info_response(response.text)
        except Exception as e:
            self.logger.error(f"Error getting server info: {e}")
            self._handle_connection_error()
            return
        
        # Query client list
        try:
            response = self._get(f"{base_url}/clients", headers)
            if response:
                self._handle_client_list_response(response.text)
        except Exception as e:
            self.logger.debug(f"Error getting client list: {e}")
        
        # Query active sessions
        try:
            response = self._get(f"{base_url}/status/sessions", headers)
            if response:
                self._handle_sessions_response(response.text)
        except Exception as e:
            self.logger.error(f"Error getting sessions: {e}")
        
        self.last_update_time = time.time()
        self.bad_calls = 0  # Reset on success

    def _do_download_image(self, url_path: str, destination: str, 
                          width: int, height: int) -> None:
        """
        Download an image from the Plex server.
        
        Args:
            url_path: The URL path for the image
            destination: Local file path to save to
            width: Optional resize width
            height: Optional resize height
        """
        base_url = self._get_base_url()
        headers = self._get_auth_headers()
        
        try:
            full_url = f"{base_url}{url_path}"
            self.logger.debug(f"Downloading image from: {full_url}")
            
            response = requests.get(full_url, headers=headers, stream=True, timeout=30, verify=False)
            
            if response.status_code == 200:
                with open(destination, 'wb') as f:
                    response.raw.decode_content = True
                    shutil.copyfileobj(response.raw, f)
                
                # Resize if requested
                if width > 0 or height > 0:
                    self._resize_image(destination, width, height)
                
                self.logger.debug(f"Image saved to: {destination}")
            else:
                self.logger.warning(f"Failed to download image: HTTP {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"Error downloading image: {e}")

    def _do_get_metadata(self, device_id: int, media_key: str) -> None:
        """
        Retrieve metadata for a media item.
        
        Args:
            device_id: The client device ID to update with metadata
            media_key: The media key to retrieve
        """
        base_url = self._get_base_url()
        headers = self._get_auth_headers()
        
        try:
            response = self._get(f"{base_url}{media_key}", headers)
            if response:
                self._handle_metadata_response(response.text, device_id)
        except Exception as e:
            self.logger.error(f"Error getting metadata: {e}")

    def _do_client_command(self, payload: dict) -> None:
        """
        Execute a client command.
        
        Args:
            payload: Command payload dictionary
        """
        # This is handled by send_client_playback_command directly
        pass

    # endregion
    # ========================================================================
    
    # ========================================================================
    # region Response Handlers
    # ========================================================================
    def _handle_server_info_response(self, xml_text: str) -> None:
        """
        Handle server info response and update states.
        
        Args:
            xml_text: XML response from server root
        """
        try:
            container = PlexMediaContainer(xml_text, '/')
            
            if container.container_type == MEDIACONTAINERTYPE_SERVERNODE:
                states_to_update = [
                    {'key': 'connectionState', 'value': 'Connected'},
                    {'key': 'serverIdentifier', 'value': container.container_attributes.get('machineIdentifier', '')},
                    {'key': 'serverName', 'value': container.container_attributes.get('friendlyName', '')},
                    {'key': 'serverVersion', 'value': container.container_attributes.get('version', '')},
                    {'key': 'transcoderActiveVideoSessions', 'value': int(container.container_attributes.get('transcoderActiveVideoSessions', '0'))}
                ]
                self.device.updateStatesOnServer(states_to_update)
                self.logger.debug(f"Server info updated: {container.container_attributes.get('friendlyName', '')}")
                
        except Exception as e:
            self.logger.error(f"Error parsing server info: {e}")

    def _handle_client_list_response(self, xml_text: str) -> None:
        """
        Handle client list response.
        
        Args:
            xml_text: XML response from /clients endpoint
        """
        try:
            container = PlexMediaContainer(xml_text, '/clients')
            
            if container.container_type == MEDIACONTAINERTYPE_CLIENTLIST:
                self.logger.debug(f'Found {len(container.clients)} clients')
                
                for plex_client in container.clients:
                    client_id = plex_client.get_client_id()
                    self.logger.debug(f'Found client with Machine Id: {client_id}')
                    
                    if client_id:
                        # Update specific client device if we have one
                        if client_id in self._child_devices:
                            client_manager = self._child_devices[client_id]
                            client_dev = client_manager.device
                            
                            if client_dev.states.get('clientConnectionStatus', '') != 'disconnected':
                                client_dev.updateStatesOnServer([
                                    {'key': 'clientAddress', 'value': plex_client.get_client_address()},
                                    {'key': 'clientPort', 'value': plex_client.get_client_port()}
                                ])
                        
                        # Update any slots that match this client
                        for slot_key, client_manager in self._child_devices.items():
                            if slot_key.startswith('Slot '):
                                slot_dev = client_manager.device
                                if slot_dev.states.get('clientId', '') == client_id:
                                    slot_dev.updateStatesOnServer([
                                        {'key': 'clientAddress', 'value': plex_client.get_client_address()},
                                        {'key': 'clientPort', 'value': plex_client.get_client_port()}
                                    ])
                                    
        except Exception as e:
            self.logger.error(f"Error parsing client list: {e}")

    def _handle_sessions_response(self, xml_text: str) -> None:
        """
        Handle sessions response and update client states.
        
        Args:
            xml_text: XML response from /status/sessions endpoint
        """
        try:
            container = PlexMediaContainer(xml_text, '/status/sessions')
            
            if container.container_type != MEDIACONTAINERTYPE_SESSIONLIST:
                return
            
            # Update server session count
            session_count = int(container.container_attributes.get('size', '0'))
            self.device.updateStateOnServer('activeSessionsCount', value=session_count)
            self.logger.debug(f'Found {len(container.video_sessions)} active media sessions')
            
            # Track connected clients for menu and disconnection detection
            new_client_list: List[Tuple[str, str]] = []
            connected_clients: Dict[str, bool] = {}
            slot_num = 0
            
            for session in container.video_sessions:
                slot_num += 1
                
                # Debug output
                self.logger.debug(f'MediaContainer Media Information: {session.media_info}')
                self.logger.debug(f'MediaContainer Player Information: {session.player_info}')
                self.logger.debug(f'Identified as Slot {slot_num}')
                
                # Get player identification
                player_machine_id = session.player_info.get('machineIdentifier', '')
                player_name = session.player_info.get('title', player_machine_id)
                
                # Find clients to update
                clients_to_process: List['PlexClient'] = []
                
                if player_machine_id in self._child_devices:
                    clients_to_process.append(self._child_devices[player_machine_id])
                
                slot_id = f'Slot {slot_num}'
                if slot_id in self._child_devices:
                    clients_to_process.append(self._child_devices[slot_id])
                
                # Process each matched client
                self.logger.debug(f'Found {len(clients_to_process)} clients to update')
                
                for client_manager in clients_to_process:
                    self._update_client_with_session(client_manager, session, player_machine_id, slot_num)
                
                if not clients_to_process:
                    self.logger.debug(f'Found unknown client: {player_machine_id}')
                
                # Track for menu and disconnection
                if player_machine_id:
                    new_client_list.append((player_machine_id, player_name))
                    connected_clients[player_machine_id] = True
            
            # Mark disconnected clients
            self._mark_disconnected_clients(connected_clients, slot_num)
            
            # Update client list for menu
            self.logger.debug(f'Updating current client list to: {new_client_list}')
            self._current_client_list = new_client_list
            self.device.updateStateOnServer('connectedClientCount', value=len(new_client_list))
            
        except Exception as e:
            self.logger.error(f"Error parsing sessions: {e}")

    def _update_client_with_session(self, client_manager: 'PlexClient', 
                                    session: Any, player_machine_id: str,
                                    slot_num: int) -> None:
        """
        Update a client device with session information.
        
        Args:
            client_manager: The PlexClient manager
            session: The video session data
            player_machine_id: The player's machine identifier
            slot_num: The slot number
        """
        dev = client_manager.device
        states_to_update = []
        
        self.logger.debug(f'Found client device to update for machineID: {player_machine_id}')
        
        # Connection status
        states_to_update.append({
            'key': 'clientConnectionStatus',
            'value': session.player_info.get('state', 'connected')
        })
        
        # User info
        states_to_update.append({
            'key': 'currentUser',
            'value': session.user_info.get('title', '')
        })
        
        # Media type
        states_to_update.append({
            'key': 'currentlyPlayingMediaType',
            'value': session.video_attributes.get('type', 'unknown')
        })
        
        # For slots, track the client ID
        if dev.deviceTypeId == 'plexMediaClientSlot':
            states_to_update.append({
                'key': 'clientId',
                'value': player_machine_id
            })
        
        # Build title (include show name for episodes)
        media_title = session.video_attributes.get('title', '')
        if session.video_attributes.get('type', 'unknown') == 'episode':
            grandparent_title = session.video_attributes.get('grandparentTitle', '')
            if grandparent_title:
                media_title = f"{grandparent_title} : {media_title}"
        
        states_to_update.append({'key': 'currentlyPlayingTitle', 'value': media_title})
        states_to_update.append({'key': 'currentlyPlayingSummary', 'value': session.video_attributes.get('summary', '')})
        states_to_update.append({'key': 'currentlyPlayingKey', 'value': session.video_attributes.get('key', '')})
        
        # Art URLs
        states_to_update.append({'key': 'currentlyPlayingArtUrl', 'value': session.video_attributes.get('art', '')})
        states_to_update.append({'key': 'currentlyPlayingThumbnailUrl', 'value': session.video_attributes.get('thumb', '')})
        
        # Parent info
        states_to_update.append({'key': 'currentlyPlayingParentKey', 'value': session.video_attributes.get('parentKey', '')})
        states_to_update.append({'key': 'currentlyPlayingParentTitle', 'value': session.video_attributes.get('parentTitle', '')})
        states_to_update.append({'key': 'currentlyPlayingParentThumbnailUrl', 'value': session.video_attributes.get('parentThumb', '')})
        
        # Grandparent info
        states_to_update.append({'key': 'currentlyPlayingGrandparentKey', 'value': session.video_attributes.get('grandparentKey', '')})
        states_to_update.append({'key': 'currentlyPlayingGrandparentTitle', 'value': session.video_attributes.get('grandparentTitle', '')})
        states_to_update.append({'key': 'currentlyPlayingGrandparentArtUrl', 'value': session.video_attributes.get('grandparentArt', '')})
        states_to_update.append({'key': 'currentlyPlayingGrandparentThumbnailUrl', 'value': session.video_attributes.get('grandparentThumb', '')})
        
        # Content info
        states_to_update.append({'key': 'currentlPlayingTitleYear', 'value': session.video_attributes.get('year', '')})
        states_to_update.append({'key': 'currentlyPlayingStarRating', 'value': session.video_attributes.get('rating', '')})
        states_to_update.append({'key': 'currentlyPlayingContentRating', 'value': session.video_attributes.get('contentRating', '')})
        states_to_update.append({'key': 'currentlyPlayingContentResolution', 'value': session.media_info.get('videoResolution', '')})
        
        # Duration and position
        content_duration = int(session.video_attributes.get('duration', '0'))
        current_offset = int(session.video_attributes.get('viewOffset', '0'))
        
        states_to_update.append({'key': 'currentlyPlayingContentLengthMS', 'value': content_duration})
        states_to_update.append({'key': 'currentlyPlayingContentLengthDisplay', 'value': str(datetime.timedelta(seconds=content_duration // 1000))})
        states_to_update.append({'key': 'currentlyPlayingContentLengthOffset', 'value': current_offset})
        states_to_update.append({'key': 'currentlyPlayingContentLengthOffsetDisplay', 'value': str(datetime.timedelta(seconds=current_offset // 1000))})
        
        # Percent complete
        if current_offset == 0 or content_duration == 0:
            percent_complete = 0
        else:
            percent_complete = int((float(current_offset) / float(content_duration)) * 100.0)
        states_to_update.append({
            'key': 'currentlyPlayingContentPercentComplete',
            'value': percent_complete,
            'uiValue': f'{percent_complete}%'
        })
        
        # Genre
        states_to_update.append({'key': 'currentlyPlayingGenre', 'value': ','.join(session.genre_list)})
        
        # Request additional metadata for tracks and episodes if needed
        media_type = session.video_attributes.get('type', 'unknown')
        if media_type == 'track' and session.video_attributes.get('parentKey', ''):
            self.queue_get_metadata(dev.id, session.video_attributes.get('parentKey', ''))
        elif media_type == 'episode' and session.video_attributes.get('grandparentKey', ''):
            self.queue_get_metadata(dev.id, session.video_attributes.get('grandparentKey', ''))
        
        # Player device title
        states_to_update.append({'key': 'playerDeviceTitle', 'value': session.player_info.get('title', '')})
        
        # Batch update
        dev.updateStatesOnServer(states_to_update)

    def _mark_disconnected_clients(self, connected_clients: Dict[str, bool], 
                                   max_slot: int) -> None:
        """
        Mark clients that are no longer connected as disconnected.
        
        Args:
            connected_clients: Dict of connected client IDs
            max_slot: Maximum slot number currently in use
        """
        # Standard disconnected state values
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
        
        for client_key, client_manager in self._child_devices.items():
            dev = client_manager.device
            
            if dev.deviceTypeId == 'plexMediaClient':
                # Check if this client is connected
                client_id = dev.pluginProps.get('plexClientId', '')
                if dev.states.get('clientConnectionStatus', '') != 'disconnected' and client_id not in connected_clients:
                    dev.updateStatesOnServer(disconnected_states)
                    
            elif dev.deviceTypeId == 'plexMediaClientSlot':
                # Check if this slot is beyond the current active slots
                slot_str = dev.pluginProps.get('plexClientId', 'Slot 99')
                if not slot_str:
                    slot_str = 'Slot 99'
                try:
                    slot_num = int(slot_str.replace('Slot ', ''))
                except ValueError:
                    slot_num = 99
                
                if slot_num > max_slot:
                    # Add clientId to disconnected states for slots
                    slot_disconnected = list(disconnected_states)
                    slot_disconnected.append({'key': 'clientId', 'value': ''})
                    dev.updateStatesOnServer(slot_disconnected)

    def _handle_metadata_response(self, xml_text: str, device_id: int) -> None:
        """
        Handle metadata response for genre updates.
        
        Args:
            xml_text: XML response from metadata endpoint
            device_id: The client device ID to update
        """
        try:
            # Parse as generic container to get directory info
            container = PlexMediaContainer(xml_text, '/library')
            
            for media_dir in container.directories:
                dir_media_key = media_dir.dictionary_attributes.get('key', '').replace('/children', '')
                self.logger.debug(f'Received metadata for media key {dir_media_key}')
                
                # Find matching client device
                for client_key, client_manager in self._child_devices.items():
                    dev = client_manager.device
                    media_type = dev.states.get('currentlyPlayingMediaType', 'unknown')
                    
                    if (media_type == 'track' and dev.states.get('currentlyPlayingParentKey', '') == dir_media_key) or \
                       (media_type == 'episode' and dev.states.get('currentlyPlayingGrandparentKey', '') == dir_media_key):
                        dev.updateStateOnServer('currentlyPlayingGenre', ','.join(media_dir.genre_list))
                        
        except Exception as e:
            self.logger.error(f"Error parsing metadata: {e}")

    # endregion
    # ========================================================================
    
    # ========================================================================
    # region HTTP Methods
    # ========================================================================
    def _get_base_url(self) -> str:
        """Get the base URL for the Plex server."""
        return f"{self._request_method}://{self._http_address}:{self._http_port}"

    def _get_auth_headers(self) -> Dict[str, str]:
        """
        Get authentication headers for requests.
        
        Returns:
            Dict of HTTP headers including auth token if available
        """
        headers = {
            'Accept': 'application/xml',
            'X-Plex-Platform': 'Indigo',
            'X-Plex-Platform-Version': indigo.server.apiVersion,
            'X-Plex-Provides': 'controller',
            'X-Plex-Client-Identifier': indigo.server.getDbName(),
            'X-Plex-Product': 'Plex Media Server Manager',
            'X-Plex-Version': self.host_plugin.pluginVersion,
            'X-Plex-Device': 'Indigo HA Server',
            'X-Plex-Device-Name': 'Indigo Plugin'
        }
        
        if self._login_required:
            self._retrieve_security_token()
            if self._security_token:
                headers['X-Plex-Token'] = self._security_token
        
        return headers

    def _get(self, url: str, headers: Dict[str, str] = None) -> Optional[requests.Response]:
        """
        Perform HTTP GET request.
        
        Args:
            url: Full URL to request
            headers: Optional headers dict
            
        Returns:
            Response object or None on error
        """
        try:
            response = requests.get(url, headers=headers, timeout=self.DEFAULT_TIMEOUT, verify=False)
            
            # Check for auth errors
            if response.status_code == 401 and self._security_token:
                self.logger.debug('Invalidating security token due to 401 response')
                self._security_token = ''
            
            return response
        except requests.exceptions.ConnectionError as e:
            self.logger.warning(f"Connection error: {e}")
            self._handle_connection_error()
            return None
        except requests.exceptions.Timeout:
            self.logger.warning(f"Timeout connecting to {url}")
            return None
        except Exception as e:
            self.logger.error(f"HTTP GET error: {e}")
            return None

    def _retrieve_security_token(self) -> None:
        """Retrieve security token from plex.tv if needed."""
        if self._security_token:
            return
        
        if not self._login_required:
            return
        
        plex_headers = {
            'X-Plex-Platform': 'Indigo',
            'X-Plex-Platform-Version': indigo.server.apiVersion,
            'X-Plex-Provides': 'controller',
            'X-Plex-Client-Identifier': indigo.server.getDbName(),
            'X-Plex-Product': 'Plex Media Server Manager',
            'X-Plex-Version': self.host_plugin.pluginVersion,
            'X-Plex-Device': 'Indigo HA Server',
            'X-Plex-Device-Name': 'Indigo Plugin'
        }
        
        try:
            response = requests.post(
                'https://plex.tv/users/sign_in.xml',
                headers=plex_headers,
                auth=(self._username, self._password),
                timeout=self.DEFAULT_TIMEOUT
            )
            
            self.logger.debug(f'Plex.tv Sign-In Response: [{response.status_code}]')
            
            if response.status_code == 201:
                # Parse XML response
                auth_xml = ET.fromstring(response.text)
                auth_token_node = auth_xml.find('authentication-token')
                if auth_token_node is not None and auth_token_node.text:
                    self._security_token = auth_token_node.text
                    self.logger.debug('Successfully obtained plex.tv authentication token')
                else:
                    self.logger.error('No authentication token in plex.tv response')
            else:
                self._security_token = ''
                self.logger.error('Failed to obtain authentication token from plex.tv site')
                
        except Exception as e:
            self.logger.error(f"Error obtaining security token: {e}")
            self._security_token = ''

    # endregion
    # ========================================================================
    
    # ========================================================================
    # region Error Handling
    # ========================================================================
    def _handle_connection_error(self) -> None:
        """Handle connection errors."""
        self.bad_calls += 1
        
        if self.bad_calls >= self.MAX_BAD_CALLS:
            self.logger.warning(f"Device {self.device.name} has failed {self.bad_calls} consecutive calls")
            self.device.updateStateOnServer('connectionState', value='Disconnected')

    # endregion
    # ========================================================================
    
    # ========================================================================
    # region Image Processing
    # ========================================================================
    def _resize_image(self, filepath: str, width: int, height: int) -> None:
        """
        Resize an image file.
        
        Args:
            filepath: Path to the image file
            width: Target width (0 for proportional)
            height: Target height (0 for proportional)
        """
        try:
            from PIL import Image
            
            with Image.open(filepath) as img:
                orig_width, orig_height = img.size
                
                if width > 0 and height > 0:
                    # Exact resize
                    new_size = (width, height)
                elif width > 0:
                    # Max dimension mode - use width as max
                    ratio = width / max(orig_width, orig_height)
                    new_size = (int(orig_width * ratio), int(orig_height * ratio))
                else:
                    return  # No resize needed
                
                resized = img.resize(new_size, Image.Resampling.LANCZOS)
                resized.save(filepath)
                self.logger.debug(f"Resized image to {new_size}")
                
        except ImportError:
            self.logger.warning("PIL not available for image resizing")
        except Exception as e:
            self.logger.error(f"Error resizing image: {e}")

    # endregion
    # ========================================================================
