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

from .scanner import FileScannerImpl
from .grouper import FileGrouperImpl
from .hasher import HasherImpl, XXHashAlgorithmImpl
from .deduplicator import Deduplicator, DeduplicatorImpl
from .sorter import Sorter
from .models import (
    File, DuplicateGroup, DeduplicationMode, DeduplicationParams, DeduplicationStats,
    SortOrder, FileHashes)

__all__ = [
    "FileScannerImpl",
    "FileGrouperImpl",
    "HasherImpl",
    "XXHashAlgorithmImpl",
    "Deduplicator",
    "DeduplicatorImpl",
    "File",
    "DuplicateGroup",
    "DeduplicationMode",
    "DeduplicationParams",
    "DeduplicationStats",
    "SortOrder",
    "FileHashes",
    "Sorter"
]