# Plex Media Server Manager Plugin - Complete Bug Fixes

## Problem 1: Import Error
The plugin failed to load with the following error:
```
type: type object 'RPFrameworkDevice' has no attribute 'RPFrameworkDevice'
```

### Root Cause
The issue was in `/Contents/Server Plugin/RPFramework/__init__.py` on line 24.

**Incorrect code:**
```python
from .RPFrameworkDevice import RPFrameworkDevice
```

This imports the **class** `RPFrameworkDevice` directly, but other files expected it to be a **module**.

### Solution
Changed to import the module instead:
```python
from . import RPFrameworkDevice
```

---

## Problem 2: Python 3 Compatibility - unicode Type
After fixing the import error, multiple `unicode` errors appeared:
```
NameError: name 'unicode' is not defined
```

### Root Cause
Python 3 removed the `unicode` type and `unicode()` function. All strings are unicode by default and use `str`.

### Solution
Fixed all occurrences of `unicode`:

**1. RPFrameworkPlugin.py:**
- Lines 254-255: `unicode(pluginVersion)` → `str(pluginVersion)`
- Line 1153: `unicode(dumpDev)` → `str(dumpDev)`

**2. RPFrameworkDeviceResponse.py:**
- Line 119: `isinstance(responseObj, (str, unicode))` → `isinstance(responseObj, str)`

**3. RPFrameworkConfig.xml:**
- Lines 111, 137: `unicode('%dp:loginRequired%')` → `str('%dp:loginRequired%')`

---

## Problem 3: Thread Method Renamed
Error when stopping device communication:
```
type: 'RPFrameworkThread' object has no attribute 'isAlive'
```

### Root Cause
Python 3 renamed the threading method `isAlive()` to `is_alive()`.

### Solution
Replaced all `isAlive()` calls with `is_alive()`:

**1. RPFrameworkDevice.py:**
- Lines 144, 163: `isAlive()` → `is_alive()`

**2. RPFrameworkThread.py:**
- Line 61: `isAlive()` → `is_alive()`

---

## Summary of All Changes

### Files Modified:
1. **RPFramework/__init__.py** - Fixed module import pattern
2. **RPFrameworkPlugin.py** - Replaced `unicode()` with `str()` (3 instances)
3. **RPFrameworkDeviceResponse.py** - Removed `unicode` from isinstance check
4. **RPFrameworkConfig.xml** - Replaced `unicode()` with `str()` (2 instances)
5. **RPFrameworkDevice.py** - Replaced `isAlive()` with `is_alive()` (2 instances)
6. **RPFrameworkThread.py** - Replaced `isAlive()` with `is_alive()` (1 instance)

### Total Fixes:
- ✓ 1 import pattern fix
- ✓ 5 unicode → str conversions
- ✓ 3 isAlive() → is_alive() conversions

---

## Installation
1. **Remove** the current version of the plugin from Indigo
2. **Install** the fixed plugin: `Plex_Media_Server_Manager_Python3_indigoPlugin_FIXED.zip`
3. **Restart** the plugin in Indigo

The plugin should now work correctly with Python 3 without any compatibility errors!

---

## Technical Notes
These fixes address the core Python 2 → Python 3 compatibility issues:
- String type unification (unicode → str)
- Threading API updates (isAlive → is_alive)
- Module import patterns

All changes maintain backward compatibility with existing Indigo configurations and device settings.
