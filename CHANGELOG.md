### [2.4.4] - 15 Feb 2026
- fixed f-strings
- fixed  Python 3.9 compatibility issue with `Type | None` syntax in PySide6 GUI code

### [2.4.5] - 16 Feb 2026
- GUI perf: Scan time reduced up to ~4x by minimizing progress callback overhead
- Fix encoding for Windows consoles to prevent UnicodeEncodeError