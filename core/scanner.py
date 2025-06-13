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
import time
import logging
logger = logging.getLogger(__name__)

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
        favorite_dirs: Directories marked as favorites for special processing
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
             progress_callback: Optional[Callable[[str, int, object], None]] = None) -> FileCollection:
        """
        Single-pass scanner with real-time progress updates and debug logging.
        Returns a filtered collection of files found in the directory tree.
        """
        logger.debug("📁 Starting scan operation...")
        logger.debug(f"Root directory: {self.root_dir}")
        logger.debug(f"Filters: min_size={self.min_size}, max_size={self.max_size}, extensions={self.extensions}")

        found_files = []
        root_path = Path(self.root_dir)
        processed_files = 0

        if stopped_flag and stopped_flag():
            logger.debug("🛑 Scan was cancelled before start.")
            return FileCollection([])

        if not root_path.exists():
            error_msg = f"Directory does not exist: {self.root_dir}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        if not root_path.is_dir():
            error_msg = f"Not a directory: {self.root_dir}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        try:
            logger.info(f"🔍 Scanning directory: {self.root_dir}")
            start_time = time.time()

            # Use os.walk instead of Path.rglob for faster traversal
            for root, dirs, files in os.walk(str(root_path)):
                if stopped_flag and stopped_flag():
                    logger.warning("🛑 Scan was interrupted by user.")
                    return FileCollection([])

                for filename in files:
                    path = Path(root) / filename
                    file_info = self._process_file(path, stopped_flag=stopped_flag)
                    if file_info:
                        found_files.append(file_info)
                    processed_files += 1

                    if progress_callback:
                        progress_callback('scanning', processed_files, None)

            end_time = time.time()
            elapsed_time = end_time - start_time

            logger.debug(f"⏱️ Total scan time: {elapsed_time:.2f} seconds")
            logger.info(f"✅ Scan completed. Found {len(found_files)} matching files.")

        except PermissionError as pe:
            logger.error(f"🔒 Permission denied during scan: {pe}", exc_info=True)
        except Exception as e:
            logger.exception(f"❌ Unexpected error during scanning: {e}")

        return FileCollection(found_files)

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

        if path.is_symlink():
            logger.warning(f"🔗 Skipping symbolic link: {path}")
            return None

        try:
            # Get file size directly
            stat_result = path.stat()
            size = stat_result.st_size
        except (OSError, PermissionError) as e:
            logger.warning(f"⚠️ Could not get size of {path}: {e}")
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
            creation_time = getattr(stat_result, 'st_birthtime', stat_result.st_ctime)
            file = File(path=str(path), size=size, creation_time=creation_time)
        except Exception as e:
            logger.warning(f"Failed to create File object for {path}: {e}")
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
        ext = path.suffix.lower()
        return any(ext == allowed_ext for allowed_ext in self.extensions)