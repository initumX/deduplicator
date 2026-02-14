
# [Highlander](https://initumx.github.io/highlander/)

![screenshot](/deduplicator224.png "Main Window")

A PyQt-based tool for finding and removing duplicate files with advanced filtering and progress tracking.

## Features

- **Filter** by file size and extension
- **Sorts** files inside duplicate groups by path dept and filename length
- Supports **deduplication modes**: fast, normal, full
- **Preview** images directly in the interface
- **Progress tracking** both for searching duplicates and deleting them
- **Statistics** Dialog Box
- **Context menu** (open, reveal in explorer and delete file(s) options)
- **One click deletion** ( using 'Keep One File Per Group' button)
- Manage **priority directories**

## How does it work?

* **Recursively scans** root folder using filters (min/max size, extension)
* **Apply the cheapest check first** (compare by size)
  * **Further checking** depends on mode: 
  
    * "fast" mode: checks hash-sum of first 64+ KB of the file (false positives very possible)<br>
    * "normal" mode: checks hash-sum of 3 parts of the file: front -> middle -> end (generally reliable)
    * "full" mode: checks hash-sum of front -> middle -> entire file (very slow for large files)


        This multi-stage approach minimizes expensive full-hash computations. 
        Each filtering step (size-> front -> middle, etc) eliminates non-matching files early, 
        ensuring that only highly probable duplicates reach the final stage.
                
* **Shows** the list of groups **sorted in descending order** - groups with larger files come first. 
Files **inside a group** are sorted by path dept or filename length (you can regulate this).
            
## How to delete files?
* **Delete individual files** (using the context menu)
* **Delete all duplicates at once** (using "Keep One File Per Group" button)

## How does "Keep One File Per Group" button work ?
This button moves **ALL files to trash EXCEPT the first file in each group**.
          
Which file is "first" depends on sorting:
* Priority files always come first
* Among priorities: shortest path (or shortest filename, depending on sorting Order) comes first
* Among non-priorities: same rule

      IMPORTANT: If a group has multiple priority files, 
          ONLY ONE (THE FIRST ONE) will be kept.
          The other priority files will be deleted (moved to trash) 
          like any other duplicates.
      REMEMBER: In the end, there can be only one file/per group :)

## How to use cli-version
   ### Examples
`highlander -i ~/Downloads -m 130KB -M 5MB -x .jpg,.png --sort shortest-filename --keep-one`

    Shows all duplicates from ~/Downloads with size from 130KB to 5MB and extension .jpg and .png. 
    Duplicates in each group are sorted by filename length (from shortest to longest filename). 
    Asks confirmation before deleting

`highlander -i ~/Downloads -m 130KB -M 5MB --keep-one --force`

    The same command as previous, but with no extension filter (doesn't filter 
    files by extension), and with --sort shortest-path (default in case you haven't set sort option).
    Deletes duplicates to trash without confirmation (--force option)

   - `-i, --input`  input folder
   - `-m, --min-size`,  min size filter
   - `-M, --max-size`, max size filter
   - `-x, --extensions` extension filter(comma separated)
   - `-p, --priority-dirs` priority dirs(comma or space separated)
   - `--mode [fast, normal, full]` searching mode (normal by default)
   - `--sort [shortest-path, shortest-filename]` sorting inside a group (shortest-path by default)
   - `--keep-one` Keep one file/per group and move the rest to trash (one confirmation)
   - `--keep-one --force` Keep one file/per group and move the rest to trash (no confirmation)

## Built With

- Python 3.x
- PySide6 (Qt)
- send2trash
- PIL/Pillow (for image handling)
- xxhash

## How to install and run
- `pip install highlander[gui]`
- `highlander-gui` (to use GUI-version) 
- `highlander` (to use cli)
- You can also get binary from releases

## TESTS
` pytest tests/ -v`

## How to build with Nuitka
`pip install xxhash pillow send2trash pyside6 nuitka pyinstaller`

`nuitka --standalone --onefile --windows-console-mode=disable --enable-plugins=pyside6 --output-dir=dist main_window.py`

## How to build with Pyinstaller
`pyinstaller --noconfirm --clean --noconsole --onefile --exclude-module=PySide6.QtNetwork main_window.py`

Or just download binary from [realeases](https://github.com/initumX/highlander/releases)   

Check out [website](https://initumx.github.io/highlander/)

© 2026 initumX (initum.x@gmail.com)







