
# [OnlyOne](https://initumx.github.io/onlyone/)

![screenshot](/deduplicator224.png "Main Window")

A PyQt-based tool for finding and removing duplicate files with advanced filtering and progress tracking.

## How to install and run
### First Way - use venv (virtual environment)
- Create python virtual environment `python3 venv ~/onlyone && cd ~/onlyone`
- Activate it `source ~/onlyone/bin/activate`
- Install onlyone into it `pip install onlyone[gui]` 
- Now you can run `onlyone` or `onlyone-gui` commands from your virtual environment
- Don't use binary from github release (they are obsolete).

### Second Way - wait for build release :)

## Features

- **Filters** files by file size and extension
- **Sorts** files inside duplicate groups by path dept and filename length
- Supports **deduplication modes**: fast, normal, full
- **Preview** images directly in the interface (for gui-version)
- **Progress tracking** both for searching duplicates and deleting them
- **Statistics** both for gui and cli-verison
- **Context menu** (open, reveal in explorer and delete file(s) options)
- **One click deletion** ( using 'Keep One File Per Group' button)
- Manage **priority directories**

## How does it work?

* **Recursively scans** folder using filters (min/max size, extension)
* **Apply the cheapest check first** (compare by size)
* **Further checking** depends on mode: 
  
  * "fast" mode: checks hash-sum of first 64+ KB of the file (false positives very possible)
  * "normal" mode: checks hash-sum of 3 parts of the file: front -> middle -> end (generally reliable)
  * "full" mode: checks hash-sum of front -> middle -> entire file (very slow for large files)

  
        Each filtering step (size-> front -> middle, etc) eliminates non-matching files early, 
        ensuring that only highly probable duplicates reach the final stage.
                
* **Shows** the list of groups **sorted in descending order** - groups with larger files come first. 
Files **inside a group** are sorted by path or filename length (you can regulate this).
            
## How to delete files?
* **Delete individual files** (using the context menu)
* **Delete all duplicates at once** (using "Keep One File Per Group" button)

## How does "Keep One File Per Group" button work ?
This button moves **ALL files to trash EXCEPT the first file in each group**.
          
Which file is "first" depends on sorting:
* Priority files(files from **"Priority Folders"**, if set) always come first
* Among priorities: shortest path (or shortest filename, if set) comes first
* Among non-priorities: same rule (shortest path is used by default)

      IMPORTANT: If a group has multiple priority files, 
          ONLY ONE (THE FIRST ONE) will be kept.
          The other priority files will be deleted (moved to trash) 
          like any other duplicates.
      REMEMBER: In the end, there can be only one file/per group :)

## How to use cli-version
    Examples:
    ----------
    Basic usage - find duplicates in Downloads folder
    `onlyone -i ~/Downloads`

    Filter files by size and extensions and find duplicates
    `onlyone -i .~/Downloads -m 500KB -M 10MB -x .jpg,.png`

    Same as above + move duplicates to trash (with confirmation prompt)
    `onlyone -i .~/Downloads -m 500KB -M 10MB -x .jpg,.png --keep-one`

    Same as above but without confirmation and with output to a file (for scripts)
    `onlyone -i .~/Downloads -m 500KB -M 10MB -x .jpg,.png --keep-one --force > ~/Downloads/report.txt`

   - `-i, --input`  input folder
   - `-m, --min-size`,  min size filter
   - `-M, --max-size`, max size filter
   - `-x, --extensions` extension filter(comma separated)
   - `-p, --priority-dirs` priority dirs(comma or space separated)
   - `--mode [fast, normal, full]` searching mode (normal by default)
   - `--sort [shortest-path, shortest-filename]` sorting inside a group (shortest-path by default)
   - `--keep-one` Keep one file/per group and move the rest to trash (one confirmation)
   - `--keep-one --force` Keep one file/per group and move the rest to trash (no confirmation)
   - `--verbose, -v` Show detailed statistics and progress

## Built With

- Python 3.x
- PySide6 (Qt)
- send2trash
- PIL/Pillow (for image handling)
- xxhash

## TESTS
` pytest tests/ -v`

## How to build with Nuitka
`pip install xxhash pillow send2trash pyside6 nuitka pyinstaller`

`nuitka --standalone --onefile --windows-console-mode=disable --enable-plugins=pyside6 --output-dir=dist main_window.py`

## How to build with Pyinstaller
`pyinstaller --noconfirm --clean --noconsole --onefile --exclude-module=PySide6.QtNetwork main_window.py`

Or just download binary from [realeases](https://github.com/initumX/onlyone/releases)   

Check out [website](https://initumx.github.io/onlyone/)

© 2026 initumX (initum.x@gmail.com)







