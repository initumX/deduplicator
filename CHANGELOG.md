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
- fix(gui): fix progress dialog overlap with stats message box

### [2.4.9] - 23 Feb 2026
-fix(build): Fixed context menu issues on pyinstall builds  
-NEW: blacklist mode for extension list. To use it, just put a ^-sign as first "extension" in a list

### [2.5.0] 
-CLI: Deleted useless --quiet key from cli  
-CLI: Renamed --verbose to --stats (OnlyOne always works verbose, this key was confusing)  
-CLI: Added progress bar  
-CLI: Report formating moved from cli to a separate module  
-CLI: Clean output  
-CLI: ASCII-support (--ascii key)
-refactor(convert_utils): convert class to module functions and enhance API  
-CLI: --version, -v added
-CLI: --dry-run added
-NEW: Now it can work on python 3.8 too, but I recommend you use 3.9 or newer.

### [2.5.1] 25 Feb 2026
-NEW: Accepts list of folders (space separated) as input. Updated both gui and cli

### [2.5.2] 26 Feb 2026
-fix(stats): show correct total scanning time, calculation/grouping time and total time

### [2.5.3] 28 Feb 2026
-refactor: consistent logging
-perf(hasher): use streaming for full file hash. Read file in 1MB chunks instead of loading into memory
-improve error handling in hasher

### [2.5.4] 1 March 2026
-NEW: hotkeys (del to delete file, ctrl+space to select file)
-NEW: Status-bar
-NEW: logging deleted files in ~/.onlyone/app.log

### [2.5.5] 2 March 2026 
-fix validation
-simplify progress indication