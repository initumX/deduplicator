"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License

core/scanner.py
Implements file scanning functionality using object-oriented design and modern pathlib.
Features:
- Uses pathlib.Path for robust, cross-platform path handling
- Recursively scans directories
- Applies size and extension filters
- Returns a List containing scanned files
"""

import os
import sys
from typing import List, Optional, Callable
from pathlib import Path
import time
import logging

logger = logging.getLogger(__name__)

# Local imports
from onlyone.core.models import File
from onlyone.core.interfaces import FileScanner

class FileScannerImpl(FileScanner):
    """
    Scans directories recursively and filters files based on size and extensions.
    Uses `pathlib.Path` for safe and consistent cross-platform behavior.

    Attributes:
        root_dir: Root directory to scan
        min_size: Minimum file size in bytes (optional)
        max_size: Maximum file size in bytes (optional)
        extensions: List of allowed file extensions (e.g., [".txt", ".jpg"])
        favourite_dirs: Directories marked as favourites for special processing
    """

    def __init__(
        self,
        root_dir: str,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        extensions: Optional[List[str]] = None,
        favourite_dirs: Optional[List[str]] = None,
        excluded_dirs: Optional[List[str]] = None
    ):
        self.root_dir = root_dir
        self.min_size = min_size
        self.max_size = max_size
        self.extensions = [ext.lower() for ext in extensions] if extensions else []
        self.favourite_dirs = [str(Path(d).resolve()) for d in favourite_dirs] if favourite_dirs else []
        self.excluded_dirs = [str(Path(d).resolve()) for d in excluded_dirs] if excluded_dirs else []

    def scan(self,
            stopped_flag: Optional[Callable[[], bool]] = None,
            progress_callback: Optional[Callable[[str, int, object], None]] = None) -> List[File]:
        """
        Single-pass scanner with real-time progress updates and debug logging.
        Returns a filtered list of files found in the directory tree.
        """
        logger.debug("Starting scan operation")
        logger.debug(f"Root directory: {self.root_dir}")
        logger.debug(f"Filters: min_size={self.min_size}, max_size={self.max_size}, extensions={self.extensions}")

        found_files = []
        root_path = Path(self.root_dir)
        processed_files = 0

        # Check for cancellation before starting
        if stopped_flag and stopped_flag():
            logger.debug("Scan cancelled before start")
            return []

        # Validate root directory exists and is accessible
        if not root_path.exists():
            error_msg = f"Directory does not exist: {self.root_dir}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        if not root_path.is_dir():
            error_msg = f"Not a directory: {self.root_dir}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        # Progress throttling: update every N files to reduce UI overhead
        progress_interval = 5000  # Update every 5,000 files
        progress_counter = 0

        try:
            logger.debug(f"Scanning directory: {self.root_dir}")
            start_time = time.time()

            # Use os.walk instead of Path.rglob for faster traversal
            for root, dirs, files in os.walk(str(root_path)):
                # Check for cancellation at each directory level
                if stopped_flag and stopped_flag():
                    logger.debug("Scan interrupted by user")
                    return []

                # Pre-filter subdirectories BEFORE os.walk enters them
                dirs[:] = [d for d in dirs if self._prefilter_dirs(Path(root) / d)]

                for filename in files:
                    path = Path(root) / filename
                    file_info = self._process_file(path, stopped_flag=stopped_flag)
                    if file_info:
                        found_files.append(file_info)
                    processed_files += 1
                    progress_counter += 1

                    # Update progress only when threshold reached (no time.time() calls!)
                    if progress_callback and progress_counter >= progress_interval:
                        progress_callback('scanning', processed_files, None)
                        progress_counter = 0

            # Final update for small datasets
            if progress_callback and progress_counter > 0:
                progress_callback('scanning', processed_files, None)

            end_time = time.time()
            elapsed_time = end_time - start_time

            logger.debug(f"Total scan time: {elapsed_time:.2f} seconds")
            logger.debug(f"Scan completed. Found {len(found_files)} matching files.")

        except PermissionError as pe:
            logger.warning(f"Permission denied during scan: {pe}")

        except Exception:
            logger.exception("Unexpected error during scanning")
            raise

        return found_files

    @staticmethod
    def _is_system_trash(path: Path) -> bool:
        """
        Check if path belongs to OS trash/recycle bin (cross-platform).
        Returns False on any error (fail-safe: better to scan than skip valid data).
        """
        try:
            # Resolve to absolute path for reliable substring matching
            path_str = str(path.resolve(strict=False))

            if sys.platform == "win32":
                # Windows: $Recycle.Bin on system drive (C: by default)
                if "$Recycle.Bin" in path_str or "\\Recycler\\" in path_str:
                    return True
            elif sys.platform == "darwin":
                # macOS: user-specific .Trash
                if "/.Trash/" in path_str or path_str.endswith("/.Trash"):
                    return True
            else:
                # Linux/BSD: freedesktop.org standard locations
                if ".local/share/Trash" in path_str or "/.trash/" in path_str:
                    return True

            return False
        except (OSError, ValueError):
            # Fail-safe: on any filesystem error, assume NOT trash
            return False

    @staticmethod
    def _is_excluded_directory(path: Path, excluded_dirs: List[str]) -> bool:
        """Check if path is within an excluded directory."""
        try:
            path_str = str(path.resolve(strict=False))
            for excluded_dir in excluded_dirs:
                normalized_excluded = os.path.normpath(excluded_dir)
                if path_str.startswith(normalized_excluded + os.sep) or \
                        path_str == normalized_excluded:
                    return True
            return False
        except (OSError, ValueError):
            return False

    def _prefilter_dirs(self, path: Path) -> bool:
        """Pre-filter directories: skip system trash and inaccessible locations."""
        # Skip system trash directories to avoid rescanning deleted files
        if FileScannerImpl._is_system_trash(path):
            logger.debug(f"Skipping system trash directory: {path}")
            return False

        if self.excluded_dirs and self._is_excluded_directory(path, self.excluded_dirs):
            logger.debug(f"Skipping excluded directory: {path}")
            return False

        # Skip inaccessible directories
        try:
            return path.is_dir() and os.access(path, os.R_OK | os.X_OK)
        except (OSError, PermissionError):
            logger.debug(f"Skipping inaccessible directory: {path}")
            return False

    def _process_file(self, path: Path, stopped_flag: Optional[Callable[[], bool]] = None) -> Optional[File]:
        """
        Process an individual file path and return a File if it passes all filters.
        Args:
            path: Path object pointing to the file
            stopped_flag: Function that returns True if operation should be stopped.
        Returns:
            Optional[File]: File object if it passes filters, else None
        """
        if stopped_flag and stopped_flag():
            return None

        try:
            if path.is_symlink():
                logger.debug(f"Skipping symbolic link: {path}")
                return None
        except (OSError, PermissionError) as e:
            logger.debug(f"Could not check symlink status for {path}: {e}")
            return None

        try:
            # Get file size directly
            stat_result = path.stat()
            size = stat_result.st_size
        except (OSError, PermissionError) as e:
            logger.debug(f"Could not get size of {path}: {e}")
            return None

        # Skip zero-byte files
        if size == 0:
            logger.debug(f"Skipping zero-byte file: {path}")
            return None

        # Apply size filter
        if not self._size_passes(size):
            logger.debug(f"Skipping {path} (size {size} bytes outside range)")
            return None

        # Apply extension filter
        if not self._extension_passes(path):
            logger.debug(f"Skipping {path} (extension not allowed)")
            return None

        try:
            path_depth = str(path).rstrip(os.sep).count(os.sep) # number of path separators
            file = File(
                path=str(path),
                size=size,
                path_depth=path_depth
            )
        except Exception as e:
            logger.debug(f"Failed to create File object for {path}: {e}")
            return None

        if self.favourite_dirs:
            try:
                file.set_favourite_status(self.favourite_dirs)
            except Exception as e:
                logger.debug(f"Error setting favourite status for {path}: {e}")
                # Continue processing — favourite status is optional metadata

        logger.debug(f"Accepted file: {path.name} ({size} bytes)")
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
        ext = path.suffix.lower()
        return any(ext == allowed_ext for allowed_ext in self.extensions)