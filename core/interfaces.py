"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License

interfaces.py

Defines core interfaces (Protocols) used throughout the deduplication system.
These protocols enforce structural typing using Python's `typing.Protocol` to ensure
consistency across modules while maintaining flexibility and modularity.

Key Components:
---------------
- Hasher: Interface for computing partial and full hashes of files.
- HashAlgorithm: Standardized interface for hash functions (e.g., SHA-256, MD5, XXHASH).
- FileScanner: Interface for scanning directories and returning structured file metadata.
- FileGrouper: Interface for grouping files by size or hash values.
- SizeStage / PartialHashStage: Interfaces for individual stages in the deduplication pipeline.
- Deduplicator: Interface for the main deduplication engine coordinating all stages.
"""

from typing import Protocol, List, Dict, Tuple, Optional, Callable
from core.models import (
    File,
    DeduplicationParams,
    DuplicateGroup,
    DeduplicationStats,
    FileCollection,
)


# ===== Interfaces =====

class TranslatorProtocol(Protocol):
    def tr(self, key: str) -> str:
        ...

class Hasher(Protocol):
    """Interface for hashing different parts of a file."""
    def compute_front_hash(self, file: File) -> bytes: ...
    def compute_middle_hash(self, file: File) -> bytes: ...
    def compute_end_hash(self, file: File) -> bytes: ...
    def compute_full_hash(self, file: File) -> bytes: ...


class HashAlgorithm(Protocol):
    """
    Interface for generic hash algorithms.

    Allows plugging in different hashing functions like SHA-256, MD5, or xxHash
    without affecting the rest of the deduplication logic.
    """

    @staticmethod
    def hash(data: bytes) -> bytes:
        """Computes the hash of the provided byte data."""
        ...


class FileScanner(Protocol):
    """
    Interface for scanning file systems and collecting file metadata.

    Methods:
        scan: Scans and returns a structured collection of files.
    """
    def scan(
        self,
        stopped_flag: Optional[Callable[[], bool]] = None,
        progress_callback: Optional[Callable[[str, int, object], None]] = None
    ) -> FileCollection:
        """
        Scan files from the configured directory.

        Args:
            stopped_flag: Function that returns True if operation should be canceled.
            progress_callback: Optional callback for reporting progress (current, total).

        Returns:
            FileCollection containing all scanned files matching filters.
        """
        ...


class FileGrouper(Protocol):
    """
    Interface for grouping files based on content hashes or size.

    Used during various stages of the deduplication pipeline to identify potential duplicates.
    """
    def group_by_size(self, files: List[File]) -> Dict[int, List[File]]:
        """Group files by their size in bytes."""
        ...

    def group_by_front_hash(self, files: List[File]) -> Dict[bytes, List[File]]:
        """Group files by their front hash."""
        ...

    def group_by_middle_hash(self, files: List[File]) -> Dict[bytes, List[File]]:
        """Group files by their middle hash."""
        ...

    def group_by_end_hash(self, files: List[File]) -> Dict[bytes, List[File]]:
        """Group files by their end hash."""
        ...

    def group_by_full_hash(self, files: List[File]) -> Dict[bytes, List[File]]:
        """Group files by their full content hash."""
        ...


# =============================
# Stage Interfaces
# =============================


class SizeStage(Protocol):
    """
    Interface for the first stage of deduplication: grouping files by size.

    Methods:
        process: Takes a list of files and returns groups of same-size files.
    """
    def process(
        self,
        files: List[File],
        stopped_flag: Optional[Callable[[], bool]] = None,
        progress_callback: Optional[Callable[[str, int, object], None]] = None
    ) -> List[DuplicateGroup]:
        """
        Group files by size to find initial duplicate candidates.

        Args:
            files: List of files to group.
            stopped_flag: Optional function to check for cancellation.
            progress_callback: Optional callback for progress updates (stage, current, total).

        Returns:
            List of groups where each contains 2+ files of the same size.
        """
        ...


class PartialHashStage(Protocol):
    """
    Interface for a deduplication stage that uses partial hashing.

    Each implementation computes a specific hash (front/middle/end),
    compares files, and confirms small duplicates early.
    """

    def get_threshold(self) -> int:
        """Get the file size threshold for early duplicate confirmation."""
        ...

    def get_stage_name(self) -> str:
        """Return the name of this stage (used in logging and stats)."""
        ...

    def process(
        self,
        groups: List[DuplicateGroup],
        confirmed_duplicates: List[DuplicateGroup],
        stopped_flag: Optional[Callable[[], bool]] = None,
        progress_callback: Optional[Callable[[str, int, object], None]] = None
    ) -> List[DuplicateGroup]:
        """
        Process groups through this stage, identifying confirmed and potential duplicates.

        Args:
            groups: Current groups of potential duplicates.
            confirmed_duplicates: List to append newly confirmed duplicates to.
            stopped_flag: Optional function to check for cancellation.
            progress_callback: Optional callback for progress updates (stage, current, total).

        Returns:
            List of refined potential duplicate groups to pass to next stage.
        """
        ...


class Deduplicator(Protocol):
    """
    Interface for the main deduplication engine.

    Coordinates multiple stages (size → partial hashes → full hash) depending on mode.
    Collects detailed statistics about the deduplication process.
    """
    def find_duplicates(
        self,
        files: List[File],
        params: DeduplicationParams,
        stopped_flag: Optional[Callable[[], bool]] = None,
        progress_callback: Optional[Callable[[str, int, object], None]] = None
    ) -> Tuple[List[DuplicateGroup], DeduplicationStats]:
        """
        Run the full deduplication pipeline based on the selected mode.

        Args:
            files: List of scanned files to analyze for duplicates.
            params: Unified configuration parameters including root directory, size filters,
                    file extensions, favorite directories, deduplication mode, and sort order
            stopped_flag: Optional function to check for cancellation.
            progress_callback: Optional callback for progress updates (stage, current, total).

        Returns:
            A tuple containing:
                - List of confirmed and potential duplicate groups
                - Statistics collected during processing
        """
        ...