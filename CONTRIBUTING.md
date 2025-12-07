# Contributing to Plex Media Server Manager Plugin

Thank you for your interest in contributing! This document provides guidelines for contributing to this project.

## Reporting Issues

When reporting issues, please include:

1. **Indigo Version**: Which version of Indigo you're using
2. **Python Version**: Run `python3 --version` in Terminal
3. **Plugin Version**: Found in Indigo's Plugins menu
4. **Error Messages**: Copy the complete error from the Event Log
5. **Steps to Reproduce**: Detailed steps to reproduce the issue
6. **Configuration**: Sanitize and include your device configuration (remove passwords)

## Development Setup

### Prerequisites

- Indigo 2025.1 or later
- Python 3.11 or later
- macOS development environment
- A Plex Media Server for testing

### Testing Changes

1. Make your changes to the plugin files
2. Zip the plugin:
   ```bash
   cd "Plex Media Server Manager Python3.indigoPlugin"
   zip -r "../test-plugin.zip" .
   ```
3. Install in Indigo and test thoroughly
4. Check the Event Log for any errors

## Python 3 Compatibility Guidelines

When making changes, ensure Python 3 compatibility:

### String Handling
- Use `str()` instead of `unicode()`
- All strings are unicode by default in Python 3
- Use `isinstance(obj, str)` for string checks

### Threading
- Use `thread.is_alive()` instead of `thread.isAlive()`
- Use `thread.join()` for cleanup

### Dictionary Methods
- Use `dict.items()` instead of `dict.iteritems()`
- Use `dict.keys()` instead of `dict.iterkeys()`
- Use `dict.values()` instead of `dict.itervalues()`

### Print Statements
- Use `print()` function: `print("message")`
- Not print statement: `print "message"`

### Division
- Use `//` for integer division
- Use `/` for float division

## Code Style

- Follow PEP 8 guidelines where possible
- Maintain consistency with existing code style
- Use tabs for indentation (as per existing code)
- Comment complex logic
- Keep lines under 120 characters when practical

## Submitting Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Make your changes
4. Test thoroughly with a real Plex server
5. Commit with clear messages
6. Push to your fork
7. Submit a pull request

### Pull Request Guidelines

- Include a clear description of the changes
- Reference any related issues
- Include testing notes
- Update CHANGELOG.md with your changes

## Testing Checklist

Before submitting, verify:

- [ ] Plugin loads without errors in Indigo
- [ ] Devices can be created and configured
- [ ] Server connection works
- [ ] Status updates work correctly
- [ ] No errors in Event Log during normal operation
- [ ] Plugin can be cleanly stopped and restarted
- [ ] Changes don't break existing functionality

## Questions?

If you have questions about contributing, feel free to open an issue for discussion.

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.
