# Changelog

All notable changes to this project will be documented in this file.

## [3.0.4-py3] - 2025-10-29

### Fixed - Python 3 Compatibility

This release fixes all Python 2 to Python 3 compatibility issues to work with Indigo 2025.1+

#### Module Import Fix
- **File**: `RPFramework/__init__.py`
- **Issue**: Import pattern causing `'RPFrameworkDevice' has no attribute 'RPFrameworkDevice'` error
- **Fix**: Changed from `from .RPFrameworkDevice import RPFrameworkDevice` to `from . import RPFrameworkDevice`
- **Impact**: Allows proper module inheritance pattern used by child classes

#### Unicode Type Removal (5 fixes)
Python 3 removed the `unicode` type - all strings are now `str`.

**RPFrameworkPlugin.py**:
- Line 254: `unicode(pluginVersion)` → `str(pluginVersion)`
- Line 255: `unicode(pluginVersion)` → `str(pluginVersion)`
- Line 1153: `unicode(dumpDev)` → `str(dumpDev)`

**RPFrameworkDeviceResponse.py**:
- Line 119: `isinstance(responseObj, (str, unicode))` → `isinstance(responseObj, str)`

**RPFrameworkConfig.xml**:
- Line 111: `unicode('%dp:loginRequired%')` → `str('%dp:loginRequired%')`
- Line 137: `unicode('%dp:loginRequired%')` → `str('%dp:loginRequired%')`

#### Threading API Update (3 fixes)
Python 3 renamed `isAlive()` to `is_alive()` in threading module.

**RPFrameworkDevice.py**:
- Line 144: `concurrentThread.isAlive()` → `concurrentThread.is_alive()`
- Line 163: `concurrentThread.isAlive()` → `concurrentThread.is_alive()`

**RPFrameworkThread.py**:
- Line 61: `self.isAlive()` → `self.is_alive()`

### Summary of Changes
- **Total Files Modified**: 6
- **Total Fixes**: 9
  - 1 module import fix
  - 5 unicode → str conversions
  - 3 isAlive() → is_alive() updates

### Testing
All fixes have been tested and verified to work with:
- Indigo 2025.1
- Python 3.11
- macOS (latest)

## [3.0.4] - Original Release

Original Python 2 version by RogueProeliator.

See the plugin's VERSION_HISTORY.md file for complete history of the original plugin development.
