
# File Deduplicator

A PyQt-based tool for finding and removing duplicate files with advanced filtering and progress tracking.

## Features

- **Scan** directories for duplicates by size and content(uses xxhash)
- **Filter** by file size and extension
- Supports multiple **deduplication modes**: fast, normal, full
- **Preview** images directly in the interface
- **Progress tracking** both for searching duplicates and deleting them
- **Statistics** Dialog Box
- **Context menu** (with open,reveal in explorer and delete file(s) options)
- **One click deletion** ( using 'Keep One File Per Group' button)
- Manage **favorite directories** for prioritization
- tooltips

## Built With

- Python 3.x
- PySide6 (Qt)
- send2trash
- PIL/Pillow (for image handling)
- xxhash

## How to build
`pip install xxhash pillow send2trash pyside6 nuitka`
`nuitka --standalone --onefile --windows-console-mode=disable --enable-plugins=pyside6 --output-dir=dist main_window.py`

© 2025 initumX (initum.x@gmail.com)
