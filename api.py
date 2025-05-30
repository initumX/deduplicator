import os
from core.scanner import FileScannerImpl
from core.deduplicator import Deduplicator
from core.models import DeduplicationMode, DuplicateGroup, FileCollection, File
from utils.services import FileService
from typing import List, Optional, Callable
from core.similar_image_finder import SimilarImageFinder
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
        self.root_dir = root_dir
        self.scanner: Optional[FileScannerImpl] = None
        self.deduplicator = Deduplicator()
        self.image_finder = SimilarImageFinder()
        self.files: List[File] = []
        self.duplicate_groups: List[DuplicateGroup] = []
        self.stats = None

    def scan_directory(self, min_size=None, max_size=None, extensions=None,
                       stopped_flag: Optional[Callable[[], bool]] = None) -> FileCollection:
        """
        Scan directory recursively and filter files by size and extension.
        Args:
            min_size (int, optional): Minimum file size in bytes.
            max_size (int, optional): Maximum file size in bytes.
            extensions (List[str], optional): Allowed file extensions like [".txt", ".jpg"].
            stopped_flag (Callable, optional): Function that returns True if operation should be stopped.
        Returns:
            FileCollection: Collection of filtered files.
        """
        self.scanner = FileScannerImpl(
            root_dir=self.root_dir,
            min_size=min_size,
            max_size=max_size,
            extensions=extensions
        )
        file_collection = self.scanner.scan(stopped_flag=stopped_flag)
        self.files = file_collection.files
        return file_collection

    def find_duplicates(self, mode=DeduplicationMode.NORMAL,
                        stopped_flag: Optional[Callable[[], bool]] = None) -> List[DuplicateGroup]:
        """
        Detect duplicate files from already scanned files.
        Args:
            mode (DeduplicationMode): Strategy for detecting duplicates.
            stopped_flag (Callable, optional): Function that returns True if operation should be stopped.
        Returns:
            List[DuplicateGroup]: Groups of duplicate files.
        """
        if not self.files:
            raise RuntimeError("No files have been scanned yet. Call scan_directory first.")

        self.duplicate_groups, self.stats = self.deduplicator.find_duplicates(self.files, mode, stopped_flag=stopped_flag)
        return self.duplicate_groups

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
            file_paths (List[str]): Paths to files to delete.
        Raises:
            RuntimeError: If any file fails to be moved to trash.
        """
        try:
            missing_files = [path for path in file_paths if not os.path.exists(path)]
            if missing_files:
                raise FileNotFoundError(f"The following files do not exist: {missing_files}")
            FileService.move_multiple_to_trash(file_paths)
            self.files = [f for f in self.files if f.path not in file_paths]
            updated_groups = []
            for group in self.duplicate_groups:
                filtered_files = [f for f in group.files if f.path not in file_paths]
                if len(filtered_files) >= 2:
                    updated_groups.append(DuplicateGroup(size=group.size, files=filtered_files))
            self.duplicate_groups = updated_groups
        except Exception as e:
            logger.error(f"Error deleting files: {e}", exc_info=True)
            raise RuntimeError(f"Error deleting files: {e}") from e

    def find_similar_images(self, files: List[File], threshold=5,
                            stopped_flag: Optional[Callable[[], bool]] = None) -> List[DuplicateGroup]:
        """
        Find visually similar images among scanned files.

        Args:
            threshold (int): Maximum allowed perceptual hash difference.
            stopped_flag (Callable, optional): Function that returns True if operation should be stopped.

        Returns:
            List of DuplicateGroup objects containing similar images.
        """
        if not self.files:
            raise RuntimeError("No files found. Call scan_directory first.")

        self.image_finder.threshold = threshold
        similar_groups = self.image_finder.find_similar_images(self.files, stopped_flag=stopped_flag)
        return similar_groups

    def find_similar_to_image(self, target_file: File, threshold=5,
                              stopped_flag: Optional[Callable[[], bool]] = None) -> List[DuplicateGroup]:
        """
        Find images similar to a specific file.

        Args:
            target_file (File): The reference image.
            threshold (int): Max phash difference.
            stopped_flag (Callable, optional): Function that returns True if operation should be stopped.

        Returns:
            List of groups with similar images.
        """
        if not self.files:
            raise RuntimeError("No files found. Call scan_directory first.")

        self.image_finder.threshold = threshold
        similar_files = self.image_finder.find_similar_to_image(target_file, self.files, stopped_flag=stopped_flag)
        return similar_files