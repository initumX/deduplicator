
# [OnlyOne](https://initumx.github.io/onlyone/)

![screenshot](/deduplicator224.png "Main Window")

A PyQt-based tool for finding and removing duplicate files with advanced filtering and progress tracking.

*Note: GUI-version is "extra"(not mandatory part), so to install app with gui, use:

`pip install onlyone[gui]`

### How to install and run
    ### First Way - use venv (virtual environment)
    1. Create python virtual environment and go there: 
    python3 venv ~/onlyone && cd ~/onlyone
    -----
    2. Activate it:
    source ~/onlyone/bin/activate
    -----
    3.Install onlyone into it: 
    pip install onlyone[gui]
    -----
    Done.
    Now you can run `onlyone` or `onlyone-gui` commands from your virtual environment

    ### Second Way - wait for build release :)

### Features
      Filters files by file size and extension
      -------
      Sorts files inside duplicate groups by path depth and filename length
      ------
      Supports deduplication modes: fast, normal, full
      ------
      Preview images directly in the interface (in gui-version)
      ------
      Progress tracking both for searching duplicates and deleting them (in gui-version)
      -------
      Statistics/report
      ------
      Context menu (open, reveal in explorer and delete file(s) options)
      ------
      One click deletion (delete all duplicates at once)
      ------
      Manage priority directories

### How does it work?
    1. Recursively scans folder using filters (min/max size, extension)
    2. Apply the cheapest check first (compare by size)
    3. Further checking depends on mode: 
      a) "fast": checks hash-sum of first 64+ KB of files (false positives very possible)
      b) "normal": checks hash-sum of 3 parts of the file: front -> middle -> end (generally reliable)
      c) "full": checks hash-sum of front -> middle -> entire file (very slow for large files)
    4. Shows the list of groups sorted in descending order (groups with larger files come first). 
    --------
    Files inside a group are sorted by path/filename length (you can regulate this).

### Deleting all duplicates at once
    The main principle: ALL files moved to trash EXCEPT the FIRST file in each group.
    ---
    Which file is "first" depends on sorting:
      Priority files(files from "Priority Folders", if set) always come first
      Among priorities: file with shortest path (by default) comes first
      Among non-priorities: same rule (shortest path is used by default for in-group sorting)
      If both files have the same path depth, the file with shortest filename wins the first place.

      REMEMBER: In the end, there can be only one file/per group :)
---


### How to use cli-version
    Examples:
    ----------
    Basic usage - find duplicates in Downloads folder
    onlyone -i ~/Downloads

    Filter files by size and extensions and find duplicates
    onlyone -i .~/Downloads -m 500KB -M 10MB -x .jpg,.png

    Same as above + move duplicates to trash (with confirmation prompt)
    onlyone -i .~/Downloads -m 500KB -M 10MB -x .jpg,.png --keep-one

    Same as above but without confirmation and with output to a file (for scripts)
    onlyone -i .~/Downloads -m 500KB -M 10MB -x .jpg,.png --keep-one --force > ~/Downloads/report.txt
    
    Options:
    ---------
    -i, --input          input folder
    -m, --min-size       min size filter
    -M, --max-size       max size filter
    -x, --extensions,    extension filter(comma separated)
    -p, --priority-dirs  priority dirs(comma or space separated)

    --mode [fast, normal, full]                   searching mode (normal by default)
    --sort [shortest-path, shortest-filename]     sorting inside a group (shortest-path by default)

    --keep-one            Keep one file/per group and move the rest to trash (one confirmation)
    --keep-one --force    Keep one file/per group and move the rest to trash (no confirmation)
    --verbose, -v         Show detailed statistics and progress
    --help, -h            Show help file
---

### Boring stuff

    Built With
        - Python 3.x
        - PySide6 (Qt)
        - send2trash
        - PIL/Pillow (for image handling)
        - xxhash

    TESTS
        pytest tests/ -v

    How to build with Pyinstaller
             pyinstaller --noconfirm --clean --noconsole --copy-metadata onlyone --onefile \
                            --exclude-module=PySide6.QtNetwork ./src/onlyone/gui/launcher.py 

    Or just download binary from [realeases](https://github.com/initumX/onlyone/releases)

### Contacts
 * [GitHub Page](https://github.com/initumX/onlyone)
 * email (initum.x@gmail.com)

© 2026 initumX
