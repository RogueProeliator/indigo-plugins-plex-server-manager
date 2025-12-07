# Plex Media Server Manager - Indigo Plugin (Python 3)

Control and monitor your Plex Media Server from Indigo Home Automation.

This is a Python 3 compatible version of the Plex Media Server Manager plugin for [Perceptive Automation's Indigo](https://www.indigodomo.com/) home automation platform.

## Features

- Monitor Plex Media Server status
- Track active playback sessions
- Control Plex clients
- Get real-time updates on media being played
- Integration with Indigo triggers and actions

## Requirements

- Indigo 2025.1 or later (with Python 3 support)
- Plex Media Server
- Network access to your Plex server

## Installation

### Method 1: Download Release

1. Download the latest `.indigoPlugin` zip file from the [Releases](../../releases) page
2. Double-click the downloaded file to install it in Indigo
3. Indigo will automatically install and enable the plugin

### Method 2: Manual Installation

1. Clone or download this repository
2. Zip the `Plex Media Server Manager Python3.indigoPlugin` folder:
   ```bash
   zip -r "Plex Media Server Manager Python3.indigoPlugin.zip" "Plex Media Server Manager Python3.indigoPlugin"
   ```
3. Double-click the zip file to install in Indigo

## Configuration

1. In Indigo, go to **Plugins** → **Plex Media Server Manager**
2. Create a new device (Device Type: Plex Media Server)
3. Configure the following settings:
   - **Request Method**: Select HTTP or HTTPS
   - **Server Address**: IP address or hostname of your Plex server
   - **Port**: Plex server port (default: 32400)
   - **Login Required**: Enable if your server requires authentication
   - **Username/Password**: Your Plex credentials (if required)
   - **Poll Interval**: How often to check server status (in seconds)

## Troubleshooting

### Connection Issues

If you see connection errors:
- Verify your Plex server is running
- Check the IP address and port are correct
- Test access in a web browser: `http://YOUR_SERVER_IP:32400/web`
- Ensure no firewall is blocking the connection
- If using authentication, verify your credentials are correct

### Plugin Won't Start

If the plugin fails to load, check the Indigo Event Log for specific error messages.

## Python 3 Compatibility Fixes

This version includes the following fixes for Python 3 compatibility:

- Fixed module import patterns in RPFramework
- Replaced `unicode()` with `str()`
- Updated `isAlive()` to `is_alive()` for threading
- Fixed isinstance checks for string types

See [CHANGELOG.md](CHANGELOG.md) for detailed information about all fixes.

## Original Plugin

This plugin is based on the original Plex Media Server Manager plugin by RogueProeliator. The original plugin was designed for Python 2, and this version has been updated for Python 3 compatibility with Indigo 2025.1+.

## Credits

- Original Plugin: RogueProeliator (Adam Ashe)
- Python 3 Conversion: Community contribution
- Framework: RPFramework by RogueProeliator

## License

See the original plugin documentation for license information.

## Support

For issues specific to this Python 3 version:
- Open an issue on this repository

For general plugin questions:
- Visit the [Indigo Forums](http://forums.indigodomo.com/)

## Version History

See [CHANGELOG.md](CHANGELOG.md) for a complete version history and list of changes.
