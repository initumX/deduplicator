### [2.4.4] - 15 Feb 2026
- fixed f-strings
- fixed  Python 3.9 compatibility issue with `Type | None` syntax in PySide6 GUI code

### [2.4.5] - 16 Feb 2026
- GUI perf: Scan time reduced up to ~4x by minimizing progress callback overhead
- Fix encoding for Windows consoles to prevent UnicodeEncodeError

### [2.4.6] - 18 Feb 2026
- Refactor progress dialog management with safe cleanup
- Use count-based progress throttling in scanner
- NEW: Implemented "Boost" logic for initial grouping
- improved code consistency

### [2.4.7] - 20 Feb 2026
- refactor(core): removed FileCollection abstraction
- NEW: Implemented "Excluded dirs" functionality
- Removed using comma as separator in CLI
- Fixed some issues

### [2.4.8] - 21 Feb 2026
- GUI: doesn't support comma as extension separator anymore (space only)
- NEW: added one more option for "boost" - fuzzy filename (group files of same size and similar filename)