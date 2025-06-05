"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License

scanner.py
Implements file scanning functionality using object-oriented design and modern pathlib.
Features:
- Uses pathlib.Path for robust, cross-platform path handling
- Recursively scans directories
- Applies size and extension filters
- Returns a FileCollection containing scanned files
"""

import os
from typing import List, Optional, Callable
from pathlib import Path

# Local imports
from core.models import File, FileCollection
from core.interfaces import FileScanner


class FileScannerImpl(FileScanner):
    """
    Scans directories recursively and filters files based on size and extensions.
    Uses `pathlib.Path` for safe and consistent cross-platform behavior.
    Attributes:
        root_dir: Root directory to scan
        min_size: Minimum file size in bytes (optional)
        max_size: Maximum file size in bytes (optional)
        extensions: List of allowed file extensions (e.g., [".txt", ".jpg"])
    """

    def __init__(
        self,
        root_dir: str,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        extensions: Optional[List[str]] = None,
        favorite_dirs: Optional[List[str]] = None
    ):
        self.root_dir = root_dir
        self.min_size = min_size
        self.max_size = max_size
        self.extensions = [ext.lower() for ext in extensions] if extensions else []
        self.favorite_dirs = [os.path.normpath(d) for d in favorite_dirs] if favorite_dirs else []

    def scan(self,
             stopped_flag: Optional[Callable[[], bool]] = None,
             progress_callback: Optional[Callable[[str, int, int], None]] = None) -> FileCollection:
        """
        Scans the directory recursively and returns a filtered collection of files.
        Args:
            stopped_flag (Optional[Callable[[], bool]]): Function that returns True if operation should be stopped.
            progress_callback (Optional[Callable[[int, int], None]]): Callback to report progress (current, total).
        Returns:
            FileCollection: Collection of filtered File objects
        """
        print(f"🔍 Scanning directory: {self.root_dir}")
        found_files = []
        root_path = Path(self.root_dir)
        processed_files = 0

        if stopped_flag and stopped_flag():
            return FileCollection([])

        if not root_path.exists():
            raise RuntimeError(f"Directory does not exist: {self.root_dir}")
        if not root_path.is_dir():
            raise RuntimeError(f"Not a directory: {self.root_dir}")

        try:
            # Only precompute paths if we need progress tracking
            if progress_callback:
                all_paths = list(root_path.rglob("*"))
                total_files = sum(1 for p in all_paths if p.is_file())
            else:
                all_paths = root_path.rglob("*")
                total_files = 0  # Not used

            for path in all_paths:
                if stopped_flag and stopped_flag():
                    return FileCollection([])

                if path.is_file():
                    try:
                        file_info = self._process_file(path, stopped_flag=stopped_flag)
                        if file_info:
                            found_files.append(file_info)
                            processed_files += 1
                            if progress_callback and total_files > 0:
                                progress_callback('scanning files:', processed_files, total_files)
                    except Exception as e:
                        print(f"⚠️ Unable to process file {path}: {e}")
        except PermissionError as pe:
            print(f"🔒 Permission denied during scan: {pe}")
        except Exception as e:
            print(f"❌ Error during scanning: {e}")

        found_files.sort(key=lambda f: -f.size)
        return FileCollection(found_files)

    def _process_file(self, path: Path, stopped_flag: Optional[Callable[[], bool]] = None) -> Optional[File]:
        """
        Process an individual file path and return a File if it passes all filters.
        Args:
            path: Path object pointing to the file
            stopped_flag (Optional[Callable[[], bool]]): Function that returns True if operation should be stopped.
        Returns:
            Optional[File]: File object if it passes filters, else None
        """
        if stopped_flag and stopped_flag():
            return None

        # Check read permissions
        if not os.access(str(path), os.R_OK):
            print(f"No read permission for {path}")
            return None

        # Get file size
        try:
            size = path.stat().st_size
        except OSError as e:
            print(f"⚠️ Could not get size of {path}: {e}")
            return None

        # Skip zero-byte files
        if size == 0:
            return None

        # Apply size filter
        if not self._size_passes(size):
            return None

        # Apply extension filter
        if not self._extension_passes(path):
            return None

        try:
            file = File(path=str(path), size=size)
        except Exception as e:
            print(f"Failed to create File object for {path}: {e}")
            return None

        if self.favorite_dirs:
            file.set_favorite_status(self.favorite_dirs)

        return file

    def _size_passes(self, size: int) -> bool:
        """
        Check if file size is within configured limits.
        Args:
            size: File size in bytes
        Returns:
            True if file meets size criteria
        """
        if self.min_size is not None and size < self.min_size:
            return False
        if self.max_size is not None and size > self.max_size:
            return False
        return True

    def _extension_passes(self, path: Path) -> bool:
        """
        Check if file matches any of the allowed extensions.
        Args:
            path: Path object pointing to the file
        Returns:
            True if file has one of the allowed extensions
        """
        if not self.extensions:
            return True
        base_name = path.name
        if base_name.startswith("."):
            return False  # Skip hidden files when extensions are specified
        parts = base_name.split(".")
        if len(parts) < 2:
            return False  # No extension
        for i in range(1, len(parts)):
            candidate = "." + ".".join(parts[i:])
            if any(candidate.lower() == ext.lower() for ext in self.extensions):
                return True
        return False

