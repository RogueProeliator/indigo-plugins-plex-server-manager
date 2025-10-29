# Plex Media Server Manager - Version History

## Version 3.0.4 (October 29, 2025)
**Python 3 sys.maxint Fix**

### Fixed
- **CRITICAL**: Fixed `sys.maxint` attribute error
  - **Error**: `module 'sys' has no attribute 'maxint'`
  - **Location**: `RPFramework/RPFrameworkIndigoParam.py` line 75
  - **Fix**: Changed `sys.maxint` to `sys.maxsize`
  - **Why**: In Python 2, `sys.maxint` was the maximum integer value. In Python 3, integers have unlimited precision, so `sys.maxint` was removed. The equivalent is `sys.maxsize`.

### Files Modified
- `RPFramework/RPFrameworkIndigoParam.py` - Fixed sys.maxint → sys.maxsize

### Verification
- All Python files compile successfully
- No attribute errors

---

## Version 3.0.3 (October 29, 2025)
**Final Import Fixes**

### Fixed
- **CRITICAL**: Fixed remaining absolute imports that were missed
  - Fixed `import RPFrameworkDeviceResponse` → `from . import RPFrameworkDeviceResponse`
  - Fixed `from dataAccess import indigosql` → `from .dataAccess import indigosql`
  - Fixed remaining Python 2 imports in multiple files:
    - `import Queue` → `import queue as Queue` (RPFrameworkDevice.py, RPFrameworkNonCommChildDevice.py)
    - `from urllib2 import urlopen` → `from urllib.request import urlopen` (RPFrameworkIndigoParam.py)
    - `import ConfigParser` → `import configparser as ConfigParser` (indigosql.py)

### Files Modified
- `RPFramework/RPFrameworkPlugin.py` - Fixed multiple import statements
- `RPFramework/RPFrameworkDevice.py` - Fixed Queue import
- `RPFramework/RPFrameworkIndigoParam.py` - Fixed urllib2 import
- `RPFramework/RPFrameworkNonCommChildDevice.py` - Fixed Queue import
- `RPFramework/dataAccess/indigosql.py` - Fixed ConfigParser import

### Verification
- All Python files compile successfully
- All imports now use Python 3 syntax
- All relative imports properly implemented

---

## Version 3.0.2 (October 29, 2025)
**Major Python 3 Syntax Fixes**

### Fixed
- **CRITICAL**: Fixed Python 2 vs Python 3 syntax incompatibilities
  - Fixed all `except Exception, e:` to `except Exception as e:` (multiple files)
  - Fixed all `raise Exception, "message"` to `raise Exception("message")` (bpgsql.py)
  - Fixed mixed tabs and spaces indentation (RPFrameworkPlugin.py line 732)
  - Fixed long integer literals `0L` to `0` (bpgsql.py)
  - Fixed regex patterns to use raw strings (avoid `\d` escape sequence warnings)
  - Fixed remaining print statements to use parentheses

### Files Modified
- `RPFramework/RPFrameworkPlugin.py` - Fixed tabs/spaces and regex patterns
- `RPFramework/RPFrameworkRESTfulDevice.py` - Fixed except clauses and regex
- `RPFramework/RPFrameworkTelnetDevice.py` - Fixed except clauses and regex  
- `RPFramework/dataAccess/bpgsql.py` - Fixed except clauses, raise statements, print, long literals
- `RPFramework/dataAccess/indigosql.py` - Fixed raise statements

### Verification
- All Python files now compile successfully with `python3 -m py_compile`
- No syntax errors remain
- Ready for testing in Indigo 2025.1

---

## Version 3.0.1 (October 29, 2025)
**Critical Bug Fix**

### Fixed
- **CRITICAL**: Fixed `No module named 'RPFrameworkPlugin'` import error
  - Converted all internal RPFramework imports from absolute to relative imports
  - Changed `import RPFrameworkPlugin` to `from . import RPFrameworkPlugin`
  - Affected 13 files in the RPFramework directory
  - This was required for Python 3 package import compatibility

### Files Modified
- `RPFramework/__init__.py`
- `RPFramework/RPFrameworkCommand.py`
- `RPFramework/RPFrameworkDevice.py`
- `RPFramework/RPFrameworkDeviceResponse.py`
- `RPFramework/RPFrameworkIndigoAction.py`
- `RPFramework/RPFrameworkIndigoParam.py`
- `RPFramework/RPFrameworkNetworkingUPnP.py`
- `RPFramework/RPFrameworkNonCommChildDevice.py`
- `RPFramework/RPFrameworkPlugin.py`
- `RPFramework/RPFrameworkRESTfulDevice.py`
- `RPFramework/RPFrameworkTelnetDevice.py`
- `RPFramework/RPFrameworkThread.py`
- `RPFramework/RPFrameworkUpdater.py`

---

## Version 3.0.0 (October 29, 2025)
**Initial Python 3 Conversion**

### Changed
- Updated Indigo API from 2.0 to 3.0 for Indigo 2025.1 compatibility
- Converted all Python 2 code to Python 3

### Python 2 → Python 3 Import Changes
- `httplib` → `http.client`
- `urllib2` → `urllib.request`
- `urllib` → `urllib.parse`
- `urlparse` → `urllib.parse`
- `Queue` → `queue`
- `StringIO.StringIO` → `io.BytesIO` / `io.StringIO`
- `ConfigParser` → `configparser`

### Unicode Handling Rewrite
- Completely rewrote `RPFrameworkUtils.to_unicode()` for Python 3
- Completely rewrote `RPFrameworkUtils.to_str()` for Python 3
- Removed all references to `basestring` type (doesn't exist in Python 3)
- Removed all direct `unicode()` function calls (doesn't exist in Python 3)
- Python 3 note: `str` is unicode by default, `bytes` is raw byte string

### Dictionary and String Methods
- Changed all `.iteritems()` to `.items()` (2 occurrences)
- Changed all `.has_key()` to `in` operator (6 occurrences)
- Changed all `isinstance(x, basestring)` to `isinstance(x, str)`

### Print Statements
- Converted all `print` statements to `print()` functions (8 occurrences)
- Primarily in debug code within `RPFramework/dataAccess/bpgsql.py`

### Files Modified in Initial Conversion
#### Core Plugin Files (4 files)
- `Contents/Info.plist` - API version and plugin version updates
- `Contents/Server Plugin/plugin.py` - Fixed unicode() call
- `Contents/Server Plugin/plexMediaServerDevices.py` - Fixed imports and .iteritems()
- `Contents/Server Plugin/plexMediaContainer.py` - Fixed imports

#### RPFramework Library (7 files)
- `RPFramework/RPFrameworkUtils.py` - Complete unicode handling rewrite
- `RPFramework/RPFrameworkCommand.py` - Fixed basestring
- `RPFramework/RPFrameworkRESTfulDevice.py` - Import updates
- `RPFramework/RPFrameworkTelnetDevice.py` - Import updates
- `RPFramework/RPFrameworkNetworkingUPnP.py` - Import and StringIO updates
- `RPFramework/RPFrameworkUpdater.py` - Import updates
- `RPFramework/dataAccess/bpgsql.py` - Print statements and has_key()

### Known Issues in 3.0.0
- Import error on startup: `No module named 'RPFrameworkPlugin'` (Fixed in 3.0.1)

---

## Pre-Python 3 Versions

### Version 2.3.5 (Original - Python 2)
- Last Python 2 version
- Compatible with Indigo API 2.0
- Original author: RogueProeliator (adam.d.ashe@gmail.com)

### Version 2.0.1
- Updated API to use Indigo 7 API calls
- Consolidated server state updates into new mass-update API calls

### Version 1.0.17
- Fixed bug where grandparent art URL was not cleared when client slots disconnected
- Added Currently Playing Summary state - description of the show
- Added Device Title state
- Added art download action for Slot devices

### Version 0.8.17
- Added unicode support
- Added support for secure (SSL) connection to server

### Version 0.0.1
- Initial Release

---

## Version Numbering Policy

Starting with version 3.0.1, every change to the plugin will result in a version increment:

- **Major version (X.0.0)**: Breaking changes, major rewrites, API changes
- **Minor version (3.X.0)**: New features, significant enhancements
- **Patch version (3.0.X)**: Bug fixes, small improvements, documentation updates

**Note**: Every time any file in the plugin is modified, the version number MUST be incremented in `Info.plist` and documented in this file.
