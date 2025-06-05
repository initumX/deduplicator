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
from utils.services import FileService, DuplicateService
# from core.similar_image_finder import SimilarImageFinder
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
        # self._image_finder = SimilarImageFinder()
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
        progress_callback: Optional[Callable[[str, int, int], None]] = None
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
        progress_callback: Optional[Callable[[str, int, int], None]] = None
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

    def delete_files(self, file_paths: List[str]):
        """
        Move specified files to trash and update internal collections.
        Args:
            file_paths: Paths to files to delete.
        Raises:
            RuntimeError: If any file fails to be moved to trash.
        """
        try:
            missing = [p for p in file_paths if not os.path.exists(p)]
            if missing:
                raise FileNotFoundError(f"Missing files: {missing}")

            FileService.move_multiple_to_trash(file_paths)

            # Обновляем данные в памяти
            self.files = DuplicateService.remove_files_from_file_list(self.files, file_paths)
            self.duplicate_groups = DuplicateService.remove_files_from_groups(self.duplicate_groups, file_paths)

        except Exception as e:
            logger.error(f"Error deleting files: {e}")
            raise RuntimeError(f"Failed to delete files: {e}") from e

    # def find_similar_images(
    #     self,
    #     files: List[File],
    #     threshold: int = 5,
    #     stopped_flag: Optional[Callable[[], bool]] = None
    # ) -> List[DuplicateGroup]:
    #     """
    #     Find visually similar images among scanned files.
    #     Args:
    #         files: Files to check for similarity.
    #         threshold: Maximum allowed perceptual hash difference.
    #         stopped_flag: Function that returns True if operation should be stopped.
    #     Returns:
    #         List of DuplicateGroup objects containing similar images.
    #     """
    #     if not self.files:
    #         raise RuntimeError("No files found. Call scan_directory first.")
    #
    #     self._image_finder.threshold = threshold
    #     similar_groups = self._image_finder.find_similar_images(files, stopped_flag=stopped_flag)
    #     return similar_groups
    #
    # def find_similar_to_image(
    #     self,
    #     target_file: File,
    #     threshold: int = 5,
    #     stopped_flag: Optional[Callable[[], bool]] = None
    # ) -> List[DuplicateGroup]:
    #     """
    #     Find images similar to a specific file.
    #     Args:
    #         target_file: The reference image.
    #         threshold: Max phash difference.
    #         stopped_flag: Function that returns True if operation should be stopped.
    #     Returns:
    #         List of groups with similar images.
    #     """
    #     if not self.files:
    #         raise RuntimeError("No files found. Call scan_directory first.")
    #
    #     self._image_finder.threshold = threshold
    #     similar_files = self._image_finder.find_similar_to_image(target_file, self.files, stopped_flag=stopped_flag)
    #     return similar_files