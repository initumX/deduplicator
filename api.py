"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License

api.py

Main application programming interface (API) module for the file deduplication tool.

This module defines the central class `FileDeduplicateApp`, which acts as a facade to coordinate:
- File scanning and filtering (`scan_directory`)
- Duplicate detection (`find_duplicates`)
- Data management (`get_files`, `get_duplicate_groups`)
- File deletion (`delete_files`)

The class provides a unified interface for GUI or CLI applications to interact with the core functionality,
including support for progress reporting and cancellation via callbacks.
"""
import os
from typing import List, Optional, Callable, Tuple

from core.scanner import FileScannerImpl
from core.deduplicator import DeduplicatorImpl
from core.models import (
    DeduplicationMode,
    DeduplicationStats,
    DuplicateGroup,
    FileCollection,
    File
)
from core.interfaces import FileScanner, Deduplicator as DeduplicatorInterface
import logging

logger = logging.getLogger(__name__)


class FileDeduplicateApp:
    """
    Main application class that coordinates file scanning and duplicate detection.
    Acts as a facade to core functionality: scanning, filtering, deduplication.
    """

    def __init__(self, root_dir: str):
        """
        Initialize the app with a root directory.
        Args:
            root_dir (str): Initial directory to scan.
        """
        self.favorite_dirs = None
        self.root_dir = root_dir
        self._scanner: Optional[FileScanner] = None
        self._deduplicator: DeduplicatorInterface = DeduplicatorImpl()
        self.files: List[File] = []
        self.duplicate_groups: List[DuplicateGroup] = []
        self.stats = None

    def scan_directory(
        self,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        extensions: Optional[List[str]] = None,
        favorite_dirs: Optional[List[str]] = None,
        stopped_flag: Optional[Callable[[], bool]] = None,
        progress_callback: Optional[Callable[[str, int, object], None]] = None
    ) -> FileCollection:
        """
        Scan directory recursively and filter files by size, extension, and favorite directories.
        Args:
            min_size: Minimum file size in bytes.
            max_size: Maximum file size in bytes.
            extensions: Allowed file extensions like [".txt", ".jpg"].
            favorite_dirs: Directories to mark files as 'favorite'.
            stopped_flag: Function that returns True if operation should be stopped.
            progress_callback: Optional function called with (current, total) during scan.
        Returns:
            FileCollection: Collection of filtered files.
        """
        self._scanner = FileScannerImpl(
            root_dir=self.root_dir,
            min_size=min_size,
            max_size=max_size,
            extensions=extensions,
            favorite_dirs=favorite_dirs
        )
        file_collection = self._scanner.scan(stopped_flag=stopped_flag, progress_callback=progress_callback)
        self.files = file_collection.files
        return file_collection

    def find_duplicates(
        self,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        extensions: Optional[List[str]] = None,
        favorite_dirs: Optional[List[str]] = None,
        mode: DeduplicationMode = DeduplicationMode.NORMAL,
        stopped_flag: Optional[Callable[[], bool]] = None,
        progress_callback: Optional[Callable[[str, int, object], None]] = None
    ) -> Tuple[List[DuplicateGroup], DeduplicationStats]:
        """
        Unified method to perform scanning + duplicate detection.
        Ideal for GUI where the user expects a single action when clicking "Find Duplicates".

        Supports optional progress reporting via callback.

        Args:
            min_size: Min file size filter
            max_size: Max file size filter
            extensions: List of allowed extensions
            favorite_dirs: Favorite directories to highlight
            mode: Deduplication mode (fast/normal/full)
            stopped_flag: Callback to check cancellation request
            progress_callback: Optional callback for progress updates (stage_name, current, total)

        Returns:
            Tuple[List[DuplicateGroup], DeduplicationStats]
        """

        # Step 1: Scan files
        file_collection = self.scan_directory(
            min_size=min_size,
            max_size=max_size,
            extensions=extensions,
            favorite_dirs=favorite_dirs,
            stopped_flag=stopped_flag,
            progress_callback=progress_callback
        )

        if not file_collection:
            raise RuntimeError("No files found during scanning.")

        # Step 2: Find duplicates
        self.duplicate_groups, stats = self._deduplicator.find_duplicates(
            self.files, mode,
            stopped_flag=stopped_flag,
            progress_callback=progress_callback
        )
        self.stats = stats
        return self.duplicate_groups, self.stats

    def get_stats(self):
        """Get statistics about the last deduplication run."""
        return self.stats

    def get_duplicate_groups(self) -> List[DuplicateGroup]:
        """Get all duplicate groups detected during last run."""
        return self.duplicate_groups

    def get_files(self) -> List[File]:
        """Get all files found during last scan."""
        return self.files