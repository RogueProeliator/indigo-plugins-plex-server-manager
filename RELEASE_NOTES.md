# Release v3.0.4-py3

## Python 3 Compatible Release

This release updates the Plex Media Server Manager plugin for full Python 3 compatibility with Indigo 2025.1+.

## What's Fixed

### Critical Python 3 Compatibility Issues
- ✅ Fixed module import pattern causing initialization errors
- ✅ Replaced all `unicode` references with `str` (5 fixes)
- ✅ Updated threading API calls from `isAlive()` to `is_alive()` (3 fixes)

### Files Modified
- `RPFramework/__init__.py` - Module import fix
- `RPFrameworkPlugin.py` - String type conversions
- `RPFrameworkDeviceResponse.py` - isinstance check update
- `RPFrameworkConfig.xml` - Configuration string handling
- `RPFrameworkDevice.py` - Threading API updates
- `RPFrameworkThread.py` - Threading API updates

## Installation

### Requirements
- Indigo 2025.1 or later
- Python 3.11+
- Plex Media Server

### Install Steps
1. Download `Plex Media Server Manager Python3.indigoPlugin.zip`
2. Double-click the file to install in Indigo
3. Configure your Plex server connection in the plugin settings

## Configuration

Set up your Plex server device with:
- Server IP address or hostname
- Port (default: 32400)
- Authentication credentials (if required)
- Polling interval

## Known Issues
None at this time.

## Migration from Python 2 Version
If upgrading from an older Python 2 version:
1. Disable the old plugin
2. Install this version
3. Your existing device configurations should be preserved

## Support
- Report issues: [GitHub Issues](../../issues)
- Documentation: [README.md](../README.md)
- Indigo Forums: [Discussion Thread](http://forums.indigodomo.com/)

## Credits
- Original Plugin: RogueProeliator (Adam Ashe)
- Python 3 Conversion: Community contribution

---

**Full Changelog**: See [CHANGELOG.md](../CHANGELOG.md)
