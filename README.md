# Introduction
This Indigo 6.1+ plugin allows Indigo to monitor, and in the future control, Plex Media Server installations and their connected clients. Plex Media Server is a popular media-streaming server that can run on OS X, among other platforms, and stream to supported clients as well as over DLNA. This plugin supports v0.9+ using the official XML-based API.

_**INDIGO 6 IMPORTANT NOTE:**_ The Indigo 6 version of this plugin is end-of-life with respect to new development, however the latest stable version on Indigo 6 is [still available](https://github.com/RogueProeliator/IndigoPlugins-Plex-Server-Manager-Plugin/releases/tag/v1.2.1) on the releases page and is working as expected at the moment. Please consider an upgrade to Indigo 7 to support further development of our favorite HA platform!

# Software Requirements
This plugin should work on any Plex Media Server v0.9 and above; it has been developed and tested against v0.9.11. For some features you may need an account registered with Plex.tv... but a Plex Pass subscription should not be necessary.

# Enabling Network Control of the Receiver - Important Step
The first step is to ensure that your receiver is connected to the network; the menu system will vary by model, but generally this is pretty easy to setup for those models with an On Screen Display. Additionally, some models require that you enable network control of the receiver -- please check your menus/settings or manual for more information.

# Installation and Configuration
###O btaining the Plugin
The latest released version of the plugin is available for download in the Releases section... those versions in beta will be marked as a Pre-Release and will not appear in update notifications.

### Configuring the Plugin
Upon first installation you will be asked to configure the plugin; please see the instructions on the configuration screen for more information. Most users will be fine with the defaults unless an email is desired when a new version is released.<br />
![](<Documentation/Doc-Images/PlexMediaServerManager_PluginConfig.png>)

# Plugin Devices
### Plex Media Server Devices
You will need to create a single Plex Media Server device for each server installation that you wish to monitor. This Indigo device will track basic information such as the number of connected clients and active sessions. Upon creating the new Indigo device, you will be presented with the device configuration screen:<br />
![](<Documentation/Doc-Images/PlexMediaServerManager_ServerDeviceConfig.png>)

### Plex Media Client Devices
Plex Media Client devices allow you to monitor particular clients which connect to the Plex Media Server which you setup in the previous step. This will allow you track their current state (e.g. connected, playing, paused, disconnected) as well as obtain information about the media that they are currently playing -- such as the title, rating, artwork, etc. You can also trigger off the current state in order to setup theater scenes or turn on lights whenever the client stops for that mid-movie popcorn break!

When you create this device in Indigo it will show you a device configuration dialog, as seen below. Select the Plex Media Server and the client you wish to monitor from the list of currently-connected clients. In order for your client to appear here, it must be actively connected to the Plex Media Server. The best way to ensure it is seen is to begin playing a movie, music or TV show on the client (it may be paused).<br />
![](<Documentation/Doc-Images/PlexMediaServerManager_ClientDeviceConfig.png>)<br />

Alternatively, if you do not care about what particular client is connected and just the connections, you may use the Plex Media Client Slot device. Instead of selecting a particular client, you tell it to monitor the first connection (Slot 1), the second connected client (Slot 2), etc. This is most often used to be able to show a control page with all of the connections to the server.

# Available Device States
The plugin tracks several devices states which are updated according to the polling frequency set in Plex Media Server Device Config as seen above; both the server and client states are updated according to the update polling frequency.

### Plex Media Server Device States
- **connectionState**: track if Indigo has been able to successfully create/maintain a connection to the server
- **serverVersion**: reports the version of the server software installed and monitored by the plugin
- **transcoderActiveVideoSessions**: tracks the number of active transcoding sessions being processed by the server
- **connectedClientCount**: the number of clients connected to the server (not accurate at this time)
- **activeSessionsCount**: the number of clients actively streaming content from the server

### Plex Media Client Device States
- **clientConnectionStatus**: the current state of the client -- Connected, Not Connected, Paused, Buffering, or Playing
- **clientAddress**: the IP address of the connected client
- **clientPort**: the IP address on which the connected client is communicating for Plex commands
- **currentUser**: the name of the current user logged in via the client
- **currentlyPlayingTitle**: the title of the currently playing media (title of the movie or "Series : Episode Title" for TV shows)
- **currentlyPlayingSummary**: the summary/description provided for the currently playing media
- **currentlyPlayingArtUrl**: the relative URL that may be used to display the currently playing media's artwork
- **currentlyPlayingThumbnailUrl**: the relative URL that may be used to display the currently playing media's thumbnail artwork
- **currentlyPlayingMediaType**: the type of media currently being played -- Clip, Movie, Playlist Clip, Trailer, TV Episode or Unknown
- **currentlPlayingTitleYear**: the release year of the currently playing title
- **currentlyPlayingStarRating**: the "star rating" of the currently playing media
- **currentlyPlayingContentRating**: the "content rating" of the currently playing media -- such as G, PG, PG-13, etc.
- **currentlyPlayingContentResolution**: the resolution of the currently playing media - such as 720 or 1080
- **currentlyPlayingContentLengthMS**: the length, in milliseconds, of the currently playing media
- **currentlyPlayingContentLengthOffset**: the current position of the client within the currently playing media
- **currentlyPlayingContentPercentComplete**: the current position of the client as a percentage complete
- **playerDeviceTitle**: the name of the device which is playing this media (e.g. Roku 2 XS)

# Notable Actions
### Download Currently Playing Art / Download Currently Playing Art for Slot
This allows you to download the various artwork associated with the currently playing media file of a client and, optionally, define a "no artwork available" image to use when none is found (or the client is disconnected). Use with the standard configuration dialog for a description of the fields, or it may be executed via script:<br />
![](<Documentation/Doc-Images/PlexMediaServerManager_DownloadArtConfig.png>)

*via scripting*
```python
plexMediaServerManager = indigo.server.getPlugin("com.duncanware.plexMediaServerManager")
plexMediaServerManager.executeAction("downloadCurrentlyPlayingArt", <YOUR_DEVICE_ID>, props={"artElement":"art", "saveToFilename":"/Users/aashe/Pictures/CurrentlyPlayingArt.png", "noArtworkFilename":"/Users/aashe/Pictures/NoArtworkAvailablePlaceholder.png"})
```

### Send Playback Command###
This action allows sending certain playback commands to any Plex client... basic commands such as play, pause, stop, forward/back, etc. are supported by the Plex API and this plugin. Note, however that some clients do not support accepting commands from Plex or only support a subset of those available.
