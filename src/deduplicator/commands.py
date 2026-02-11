"""
Unified command orchestrator for deduplication.
This is the SINGLE source of truth for business logic — used by both GUI and CLI.
No Qt/PySide6 dependencies — pure Python.
"""
from typing import List, Optional, Callable, Tuple
from deduplicator.core.models import DuplicateGroup, DeduplicationStats, DeduplicationParams, File
from deduplicator.core.scanner import FileScannerImpl
from deduplicator.core.deduplicator import DeduplicatorImpl

class DeduplicationCommand:
    """
    Orchestrates the entire deduplication workflow:
    1. Initialize app with root directory
    2. Set favourite directories
    3. Execute find_duplicates with progress/cancellation support

    Usage:
        # For GUI (with progress UI updates):
        params = DeduplicationParams(...)
        command = DeduplicationCommand()
        groups, stats = command.execute(
            params,
            progress_callback=qt_progress_adapter,
            stopped_flag=qt_cancellation_check
        )

        # For CLI (with console progress):
        groups, stats = command.execute(
            params,
            progress_callback=cli_progress_printer,
            stopped_flag=signal_handler_check
        )
    """

    def __init__(self):
        self._deduplicator = DeduplicatorImpl()
        self._files: List[File] = []  # Local state storage (not in app/api layer)

    def execute(
            self,
            params: DeduplicationParams,
            progress_callback: Optional[Callable[[str, int, Optional[int]], None]] = None,
            stopped_flag: Optional[Callable[[], bool]] = None
    ) -> Tuple[List[DuplicateGroup], DeduplicationStats]:
        """
        Execute deduplication with given parameters.

        Args:
            params: Validated deduplication parameters
            progress_callback: (stage: str, current: int, total: Optional[int]) -> None
            stopped_flag: () -> bool (returns True if operation should stop)

        Returns:
            Tuple of (duplicate_groups, statistics)

        Raises:
            ValueError: If parameters are invalid
            RuntimeError: If scanning/deduplication fails
        """
        # Step 1: Scan files using core scanner directly
        scanner = FileScannerImpl(
            root_dir=params.root_dir,
            min_size=params.min_size_bytes,
            max_size=params.max_size_bytes,
            extensions=params.extensions,
            favourite_dirs=params.favourite_dirs
        )

        file_collection = scanner.scan(
            stopped_flag=stopped_flag,
            progress_callback=progress_callback
        )

        self._files = file_collection.files

        if not self._files:
            raise RuntimeError("No files found matching filters")

        # Step 2: Find duplicates using core deduplicator directly
        groups, stats = self._deduplicator.find_duplicates(
            self._files,
            params,  # ← Unified params object with sort_order, mode, etc.
            stopped_flag=stopped_flag,
            progress_callback=progress_callback
        )

        return groups, stats

    def get_files(self) -> List[File]:
        """Get scanned files after execution."""
        return self._files.copy()  # Return copy to prevent external mutation