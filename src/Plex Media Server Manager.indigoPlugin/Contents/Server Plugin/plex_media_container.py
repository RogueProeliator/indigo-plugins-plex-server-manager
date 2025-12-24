#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
Plex Media Container Classes

Handles parsing of XML-based MediaContainer elements that the Plex Media Server
API returns. These classes encapsulate the different types of responses from
the Plex server including server info, client lists, and session data.
"""

# region Python Imports
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional
# endregion


# region Constants
MEDIACONTAINERTYPE_UNKNOWN = 0
MEDIACONTAINERTYPE_SERVERNODE = 1
MEDIACONTAINERTYPE_CLIENTLIST = 2
MEDIACONTAINERTYPE_SESSIONLIST = 3
# endregion


class PlexMediaContainer:
    """
    Handles the XML-based MediaContainer element that all Plex Media Server
    API calls return.
    
    Attributes:
        container_type: The type of container (server, client list, sessions)
        container_attributes: Dict of attributes from the root container element
        directories: List of PlexMediaContainerDirectory objects
        clients: List of PlexMediaClient objects (for client list responses)
        video_sessions: List of PlexMediaContainerVideoSession objects (for session responses)
    """

    def __init__(self, media_container_xml: str, plex_container_path: str):
        """
        Initialize the container by parsing XML data.
        
        Args:
            media_container_xml: Raw XML string from the Plex server
            plex_container_path: The API path used (e.g., '/', '/clients', '/status/sessions')
        """
        # Initialize collections
        self.container_attributes: Dict[str, str] = {}
        self.directories: List[PlexMediaContainerDirectory] = []
        self.clients: List[PlexMediaClient] = []
        self.video_sessions: List[PlexMediaContainerVideoSession] = []
        
        # Determine container type based on path
        if plex_container_path == '/':
            self.container_type = MEDIACONTAINERTYPE_SERVERNODE
        elif plex_container_path == '/clients':
            self.container_type = MEDIACONTAINERTYPE_CLIENTLIST
        elif plex_container_path == '/status/sessions':
            self.container_type = MEDIACONTAINERTYPE_SESSIONLIST
        else:
            self.container_type = MEDIACONTAINERTYPE_UNKNOWN
        
        # Parse the XML
        try:
            media_container_node = ET.fromstring(media_container_xml)
            
            # Load container attributes
            for key, value in media_container_node.items():
                self.container_attributes[key] = value
            
            # Parse directories
            for directory_node in media_container_node.findall('Directory'):
                self.directories.append(PlexMediaContainerDirectory(directory_node))
            
            # Parse clients (from 'Server' elements in client list)
            if self.container_type == MEDIACONTAINERTYPE_CLIENTLIST:
                for client_node in media_container_node.findall('Server'):
                    self.clients.append(PlexMediaClient(client_node))
            
            # Parse video/audio sessions
            if self.container_type == MEDIACONTAINERTYPE_SESSIONLIST:
                for video_node in media_container_node.findall('Video'):
                    self.video_sessions.append(PlexMediaContainerVideoSession(video_node))
                for audio_node in media_container_node.findall('Track'):
                    self.video_sessions.append(PlexMediaContainerVideoSession(audio_node))
            
            # Clear the element to free memory
            media_container_node.clear()
            
        except ET.ParseError as e:
            raise ValueError(f"Failed to parse Plex XML response: {e}")


class PlexMediaContainerDirectory:
    """
    Stores information about a "directory" element within the Plex API.
    
    This represents anything that can be drilled deeper into its hierarchy,
    such as library sections, playlists, or media metadata.
    
    Attributes:
        dictionary_attributes: Dict of attributes from the directory element
        genre_list: List of genre strings associated with this directory
    """

    def __init__(self, directory_xml_node: ET.Element):
        """
        Initialize from an XML directory node.
        
        Args:
            directory_xml_node: The XML Element for the directory
        """
        self.dictionary_attributes: Dict[str, str] = {}
        self.genre_list: List[str] = []
        
        # Load attributes
        _load_xml_element_to_dict(directory_xml_node, self.dictionary_attributes)
        
        # Load genre tags
        for genre_node in directory_xml_node.findall('Genre'):
            tag = genre_node.get('tag', '')
            if tag:
                self.genre_list.append(tag)


class PlexMediaClient:
    """
    Stores information about a connected Plex client.
    
    In the Plex API, connected clients appear as "Server" elements
    within the client list response.
    
    Attributes:
        client_attributes: Dict of attributes from the client element
    """

    def __init__(self, server_xml_node: ET.Element):
        """
        Initialize from an XML server/client node.
        
        Args:
            server_xml_node: The XML Element for the client
        """
        self.client_attributes: Dict[str, str] = {}
        
        # Load attributes
        _load_xml_element_to_dict(server_xml_node, self.client_attributes)

    def get_client_id(self) -> str:
        """Get the client's machine identifier."""
        return self.client_attributes.get('machineIdentifier', '')

    def get_client_name(self) -> str:
        """Get the client's product name."""
        return self.client_attributes.get('product', '')

    def get_client_address(self) -> str:
        """Get the client's IP address."""
        return self.client_attributes.get('address', '')

    def get_client_port(self) -> int:
        """Get the client's port number."""
        try:
            return int(self.client_attributes.get('port', '0'))
        except ValueError:
            return 0


class PlexMediaContainerVideoSession:
    """
    Stores information about an active video/audio session.
    
    This represents a currently playing media item, including the
    video attributes, player info, user info, and media info.
    
    Attributes:
        video_attributes: Dict of attributes from the video/track element
        user_info: Dict of user information
        player_info: Dict of player/client information
        media_info: Dict of media format information
        genre_list: List of genre strings
    """

    def __init__(self, video_xml_node: ET.Element):
        """
        Initialize from an XML video/track node.
        
        Args:
            video_xml_node: The XML Element for the video or track
        """
        self.video_attributes: Dict[str, str] = {}
        self.user_info: Dict[str, str] = {}
        self.player_info: Dict[str, str] = {}
        self.media_info: Dict[str, str] = {}
        self.genre_list: List[str] = []
        
        # Load video/track attributes
        _load_xml_element_to_dict(video_xml_node, self.video_attributes)
        
        # Load user info if present
        user_node = video_xml_node.find('User')
        if user_node is not None:
            _load_xml_element_to_dict(user_node, self.user_info)
        
        # Load player info if present
        player_node = video_xml_node.find('Player')
        if player_node is not None:
            _load_xml_element_to_dict(player_node, self.player_info)
        
        # Load media info if present
        media_node = video_xml_node.find('Media')
        if media_node is not None:
            _load_xml_element_to_dict(media_node, self.media_info)
        
        # Load genre list (for video items - tracks get genre from parent)
        if video_xml_node.tag != 'Track':
            for genre_node in video_xml_node.findall('Genre'):
                tag = genre_node.get('tag', '')
                if tag:
                    self.genre_list.append(tag)


def _load_xml_element_to_dict(xml_element: ET.Element, target_dict: Dict[str, str]) -> None:
    """
    Load all attributes from an XML element into a dictionary.
    
    Args:
        xml_element: The XML element to read attributes from
        target_dict: The dictionary to populate with attributes
    """
    for key, value in xml_element.items():
        target_dict[key] = value
