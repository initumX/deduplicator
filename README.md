
# [OnlyOne](https://github.com/initumX/onlyone)

![screenshot](https://raw.githubusercontent.com/initumX/onlyone/refs/heads/main/onlyone247.jpg)  
[CHANGELOG](https://github.com/initumX/onlyone/blob/main/CHANGELOG.md)

A PyQt-based tool for finding and removing duplicate files with advanced filtering and progress tracking.

*Note: GUI-version is "extra"(not mandatory part), so to install app with gui, use:

`pip install onlyone[gui]`

## How to install and run
  1. Create python virtual environment and go there: `python3 venv ~/onlyone && cd ~/onlyone` 
  2. Activate it: `source ~/onlyone/bin/activate`
  3. Install onlyone into it: `pip install onlyone[gui]`
  4. Run the app: `onlyone-gui`  or `onlyone`(for cli)

If you don't want install it on venv, binary for linux and windows are available in [github release](https://github.com/initumX/onlyone/releases)

### Features
* Filtering by file size and extension
* Sorting inside duplicate groups 
* Supporting various deduplication modes
* Preview images/pdf directly in the interface
* Context menu(open/delete/reveal in explorer)
* Progress tracking (in gui-version)
* One click deletion (delete all duplicates at once)
* Priority and excluded directories functionality
* Statistics/report

### How does it work?
1. Recursively scans folder using filters (min/max size, extension)
2. Applies one of the initial grouping ways from "boosting" option (size, size+extension, etc)
3. Further checking depends on mode:
   * "fast": checks hash-sum of first 128+ KB (false positives very possible)
   * "normal": checks hash-sum of 3 parts of the file: front -> middle -> end (generally reliable)
   * "full": checks hash-sum of front -> middle -> entire file (very slow for large files)  
4. Shows the list of groups sorted in descending order (groups with larger files come first).   
   **Files inside a group are sorted by path/filename length (you can regulate this).

### NEW FEATURE [v.2.4.6]: Boosting implemented
    In older versions (before 2.4.6) initial grouping was based only on file size. 
    Now you can use various strategies using Boost combobox (or --boost key on cli, see --help):
    * by size: Compare only files of the same size (was the only method before)
    * by size and extension: Compare only files of the same size and extension.
    * by size and filename: Compare only files of the same size and filename

### NEW FEATURE [v.2.4.7]: Excluded dirs implemented
    Now you can set Excluded/ignored dirs both using GUI or cli (using --excluded-dirs key)

### Deleting all duplicates at once
The main principle: ALL files moved to trash EXCEPT the FIRST file in each group.  
Which file is "first" depends on sorting:  
* Priority files(files from "Priority Folders", if set) always come first
  * Among priorities: file with shortest path (by default) comes first
* Among non-priorities: same rule (shortest path is used by default for in-group sorting)  
If both files have the same path depth, the file with shortest filename wins the first place.

      REMEMBER: In the end, there can be only one file/per group :)
---


### How to use cli-version
Examples:  
Basic usage - find duplicates in Downloads folder:  
`onlyone -i ~/Downloads`  

Filter files by size and extensions and find duplicates:  
`onlyone -i .~/Downloads -m 500KB -M 10MB -x .jpg,.png`

Same as above + move duplicates to trash (with confirmation prompt):  
`onlyone -i .~/Downloads -m 500KB -M 10MB -x .jpg,.png --keep-one`

Same as above but without confirmation and with output to a file (for scripts):  
`onlyone -i .~/Downloads -m 500KB -M 10MB -x .jpg,.png --keep-one --force > ~/Downloads/report.txt`
    
Options:  
    `-i, --input`          input folder  
    `-m, --min-size`       min size filter  
    `-M, --max-size`       max size filter  
    `-x, --extensions`     extension filter(space separated)  
    `-p, --priority-dirs`  priority dirs(space separated)  
    `--excluded-dirs`     excluded/ignored dirs (space separated)  
    `--boost {size,extension,filename}`  Rule for initial file grouping:
* `size` Group files of the same size only (default)  
*  `extension`  Group files of the same size and extension  
* `filename`   Group files of the same size and filename  

`**Groups formed above will be checked (hash-checking) in further stages`  

`--mode {fast, normal, full}` checking mode (normal by default)
* `fast`    checks only by hashsum from the front part of file  
* `normal`  checks by hashsum from 3 parts of file  
* `full`    checks by hashsum from 2 part + whole file hashsum  

`--sort {shortest-path, shortest-filename}` sorting inside a group (shortest-path by default)  
`--keep-one`            Keep one file/per group and move the rest to trash (one confirmation)  
`--keep-one --force`    Keep one file/per group and move the rest to trash (no confirmation)  
`--verbose, -v`         Show detailed statistics and progress  
`--help, -h`            Show help file  
---

### TESTS
`pytest tests/ -v` 

### Build with Pyinstaller  
`pyinstaller --noconfirm --clean --noconsole --copy-metadata=onlyone --onefile --paths ./src --name=OnlyOne --exclude-module=PySide6.QtNetwork ./src/onlyone/gui/launcher.py` 

### Built With  
- Python 3.x
- PySide6 (Qt)
- send2trash
- PIL/Pillow (for image handling)
- xxhash

### LINKS
 * [GitHub Page](https://github.com/initumX/onlyone)
 * email (initum.x@gmail.com)

© 2026 initumX
