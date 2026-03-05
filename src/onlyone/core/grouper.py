#!/usr/bin/env python3
"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License

core/grouper.py
Implements file grouping strategies using File objects and Hasher.
"""
from typing import List, Dict, Tuple, Any, Callable, Optional, TypeVar
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
import threading
import logging

from onlyone.core.models import File
from onlyone.core.hasher import Hasher, HasherImpl, XXHashAlgorithmImpl
from onlyone.core.demasker import demask_filename

logger = logging.getLogger("onlyone.core.grouper")

# Type alias for grouping key
K = TypeVar('K')

# Default number of worker threads for parallel hashing
DEFAULT_HASH_WORKERS = 4


class FileGrouper:
    """
    Concrete implementation of file grouping using xxHash-based hashing.

    Supports both sequential grouping (for fast partial hashes) and
    parallel grouping (for slow full-content hashes).
    """

    def __init__(self, hasher: Optional[Hasher] = None, max_workers: int = DEFAULT_HASH_WORKERS):
        self.hasher = hasher or HasherImpl(XXHashAlgorithmImpl())
        self.max_workers = max_workers

    # ==========================
    # Public Grouping Methods
    # ==========================

    def group_by_size(self, files: List[File]) -> Dict[int, List[File]]:
        """Groups files by their size."""
        return self._group_by(files, lambda f: f.size)

    def group_by_size_and_extension(self, files: List[File]) -> Dict[Tuple[int, str], List[File]]:
        """Groups files by both size and extension."""
        return self._group_by(files, lambda f: (f.size, f.extension))

    def group_by_size_and_name(self, files: List[File]) -> Dict[Tuple[int, str], List[File]]:
        """Groups files by both size and name (including extension)."""
        return self._group_by(files, lambda f: (f.size, f.name))

    def group_by_size_and_normalized_name(self, files: List[File]) -> Dict[Tuple[int, str], List[File]]:
        """Groups files by size and a normalized (fuzzy) version of the filename."""
        return self._group_by(files, lambda f: (f.size, demask_filename(f.name)))

    def group_by_front_hash(self, files: List[File]) -> Dict[bytes, List[File]]:
        """Groups files by front hash (Sequential)."""
        return self._group_by(files, self.hasher.compute_front_hash)

    def group_by_middle_hash(self, files: List[File]) -> Dict[bytes, List[File]]:
        """Groups files by middle hash (Sequential)."""
        return self._group_by(files, self.hasher.compute_middle_hash)

    def group_by_end_hash(self, files: List[File]) -> Dict[bytes, List[File]]:
        """Groups files by end hash (Sequential)."""
        return self._group_by(files, self.hasher.compute_end_hash)

    def group_by_full_hash(
        self,
        files: List[File],
        stopped_flag: Optional[Callable[[], bool]] = None
    ) -> Dict[bytes, List[File]]:
        """
        Groups files by full content hash (Parallelized).

        Args:
            files: List of files to hash.
            stopped_flag: Optional callback to check for cancellation.
        """
        return self._group_by_parallel(files, self.hasher.compute_full_hash, stopped_flag)

    # ==========================
    # Internal Helpers
    # ==========================

    def _group_by(self, files: List[File], key_func: Callable[[File], Any]) -> Dict[Any, List[File]]:
        """
        Helper method to group files by any computed key (Sequential).
        """
        groups = defaultdict(list)
        skipped_count = 0

        for file in files:
            try:
                key = key_func(file)
                if key is not None:
                    groups[key].append(file)
            except Exception as e:
                logger.warning(f"Error processing {file.path}: {e}")
                skipped_count += 1

        if skipped_count > 0:
            logger.warning(f"Skipped {skipped_count} files due to computation errors")

        return self._finalize_groups(groups)

    def _group_by_parallel(
        self,
        files: List[File],
        key_func: Callable[[File], Any],
        stopped_flag: Optional[Callable[[], bool]] = None
    ) -> Dict[Any, List[File]]:
        """
        Helper method to group files by any computed key (Parallel).

        Uses ThreadPoolExecutor to overlap I/O wait times during hashing.
        """
        groups = defaultdict(list)
        skipped_count = 0
        lock = threading.Lock()

        def _worker(file: File) -> Tuple[File, Optional[Any], Optional[Exception]]:
            """Worker function to compute key for a single file."""
            try:
                return file, key_func(file), None
            except Exception as e:
                return file, None, e

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_file: Dict[Future, File] = {
                executor.submit(_worker, file): file for file in files
            }

            # Collect results
            for future in as_completed(future_to_file):
                # Check cancellation between batches
                if stopped_flag and stopped_flag():
                    logger.warning("Hash computation interrupted by user")
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

                file, key, error = future.result()

                with lock:
                    if error:
                        logger.warning(f"Error processing {file.path}: {error}")
                        skipped_count += 1
                    elif key is not None:
                        groups[key].append(file)

        if skipped_count > 0:
            logger.warning(f"Skipped {skipped_count} files due to computation errors")

        return self._finalize_groups(groups)

    @staticmethod
    def _finalize_groups(groups: Dict[Any, List[File]]) -> Dict[Any, List[File]]:
        """
        Filters groups to keep only duplicates (≥2 files) and sorts them.

        Sorting priority: Files from favourite directories come first.
        """
        result = {}
        for key, group in groups.items():
            if len(group) >= 2:
                # Sort: Favourite files first (is_from_fav_dir=True -> False when negated)
                sorted_group = sorted(group, key=lambda f: not f.is_from_fav_dir)
                result[key] = sorted_group
        return result