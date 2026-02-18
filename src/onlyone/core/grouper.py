"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License

core/grouper.py
Implements file grouping strategies using File objects and Hasher.
Replaces multiple standalone groupers with a single class implementing FileGrouper.
"""

from typing import List, Dict, Tuple, Any, Callable
from collections import defaultdict
from onlyone.core.interfaces import FileGrouper
from onlyone.core.models import File
from onlyone.core.hasher import HasherImpl, XXHashAlgorithmImpl, Hasher


class FileGrouperImpl(FileGrouper):
    """
    A concrete implementation of FileGrouper using xxHash-based hashing.
    Uses an injected Hasher instance for flexibility and testability.
    """

    def __init__(self, hasher: Hasher = None):
        self.hasher = hasher or HasherImpl(XXHashAlgorithmImpl())

    def group_by_size(self, files: List[File]) -> Dict[int, List[File]]:
        """Groups files by their size."""
        return self._group_by(files, lambda f: f.size)

    def group_by_size_and_extension(self, files: List[File]) -> Dict[Tuple[int, str], List[File]]:
        """Groups files by both size and extension (fast pre-filter before hashing)."""
        return self._group_by(files, lambda f: (f.size, f.extension))

    def group_by_size_and_name(self, files: List[File]) -> Dict[Tuple[int, str], List[File]]:
        """Groups files by both size and name(including extension)."""
        return self._group_by(files, lambda f: (f.size, f.name))

    def group_by_front_hash(self, files: List[File]) -> Dict[bytes, List[File]]:
        """Groups files by front hash."""
        return self._group_by(files, self.hasher.compute_front_hash)

    def group_by_middle_hash(self, files: List[File]) -> Dict[bytes, List[File]]:
        """Groups files by middle hash."""
        return self._group_by(files, self.hasher.compute_middle_hash)

    def group_by_end_hash(self, files: List[File]) -> Dict[bytes, List[File]]:
        """Groups files by end hash."""
        return self._group_by(files, self.hasher.compute_end_hash)

    def group_by_full_hash(self, files: List[File]) -> Dict[bytes, List[File]]:
        """Groups files by full content hash."""
        return self._group_by(files, self.hasher.compute_full_hash)

    @staticmethod
    def _group_by(files: List[File], key_func: Callable[[File], Any]) -> Dict[Any, List[File]]:
        """
        Helper method to group files by any computed key.
        Args:
            files: List of files to group
            key_func: Function that computes a hashable key from a File
        Returns:
            Dict[key, List[File]]
        """
        groups = defaultdict(list)
        skipped_files = 0
        for file in files:
            try:
                key = key_func(file)
                if key is not None:
                    groups[key].append(file)
            except Exception as e:
                print(f"⚠️ Error processing {file.path}: {e}")
                skipped_files += 1

        if skipped_files > 0:
            print(f"⚠️ Skipped {skipped_files} files due to hash computation errors")

        result = {}
        for key, group in groups.items():
            if len(group) >= 2: # Avoid groups with less than 2 files
                sorted_group = sorted(group, key=lambda f: not f.is_from_fav_dir)
                result[key] = sorted_group

        return result

