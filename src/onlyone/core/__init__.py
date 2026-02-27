"""
Core deduplication engine — scanner, hasher, grouper, and pipeline orchestrator.

This package contains the performance-critical foundation of the onlyone:
- FileScannerImpl: recursive directory traversal with size/extension filters
- HasherImpl + XXHashAlgorithmImpl: xxHash64-based partial/full content hashing
- FileGrouperImpl: size and hash-based grouping with duplicate filtering
- Deduplicator: multi-stage pipeline (size → partial hashes → full hash)
- Models: File, DuplicateGroup, and configuration objects

All components are pure Python with no GUI dependencies — suitable for CLI and server usage.
"""

from .scanner import FileScanner
from .grouper import FileGrouper
from .hasher import HasherImpl, XXHashAlgorithmImpl
from .deduplicator import DeduplicatorImpl
from .sorter import Sorter
from .demasker import demask_filename
from .models import (
    File, DuplicateGroup, DeduplicationMode, DeduplicationParams, DeduplicationStats,
    SortOrder, FileHashes, BoostMode)
from onlyone.core.measurer import bytes_to_human, human_to_bytes, is_valid_size_format

__all__ = [
    "FileScanner",
    "FileGrouper",
    "HasherImpl",
    "XXHashAlgorithmImpl",
    "DeduplicatorImpl",
    "File",
    "DuplicateGroup",
    'BoostMode',
    "DeduplicationMode",
    "DeduplicationParams",
    "DeduplicationStats",
    "SortOrder",
    "demask_filename",
    "FileHashes",
    "Sorter",
    "bytes_to_human",
    "human_to_bytes",
    "is_valid_size_format"
]