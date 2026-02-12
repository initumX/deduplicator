
# [File Deduplicator](https://initumx.github.io/deduplicator/)

![screenshot](/deduplicator224.png "Main Window")

A PyQt-based tool for finding and removing duplicate files with advanced filtering and progress tracking.

## Features

- **Scan** directories for duplicates by size and content(uses xxhash)
- **Filter** by file size and extension
- **Sorts** duplicate inside groups by path dept and creation time
- Supports multiple **deduplication modes**: fast, normal, full
- **Preview** images directly in the interface
- **Progress tracking** both for searching duplicates and deleting them
- **Statistics** Dialog Box
- **Context menu** (with open, reveal in explorer and delete file(s) options)
- **One click deletion** ( using 'Keep One File Per Group' button)
- Manage **favourite directories** for prioritization
- tooltips

## Built With

- Python 3.x
- PySide6 (Qt)
- send2trash
- PIL/Pillow (for image handling)
- xxhash

## How to build with Nuitka
`pip install xxhash pillow send2trash pyside6 nuitka pyinstaller`


`nuitka --standalone --onefile --windows-console-mode=disable --enable-plugins=pyside6 --output-dir=dist main_window.py`

## How to build with Pyinstaller
`pyinstaller --noconfirm --clean --noconsole --onefile --exclude-module=PySide6.QtNetwork main_window.py`

Or just download binary from [realeases](https://github.com/initumX/deduplicator/releases)   

Check out [website](https://initumx.github.io/deduplicator/)

© 2025 initumX (initum.x@gmail.com)







