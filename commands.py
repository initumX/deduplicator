"""
Unified command orchestrator for deduplication.
This is the SINGLE source of truth for business logic — used by both GUI and CLI.
No Qt/PySide6 dependencies — pure Python.
"""
from typing import List, Optional, Callable, Tuple
from core.models import DuplicateGroup, DeduplicationStats, DeduplicationParams, File
from api import FileDeduplicateApp

class DeduplicationCommand:
    """
    Orchestrates the entire deduplication workflow:
    1. Initialize app with root directory
    2. Set favorite directories
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
        self.app: Optional[FileDeduplicateApp] = None

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
        # Initialize app with root directory
        self.app = FileDeduplicateApp(params.root_dir)
        self.app.favorite_dirs = params.favorite_dirs

        # Execute core operation — SAME CODE PATH for GUI and CLI
        groups, stats = self.app.find_duplicates(
            min_size=params.min_size_bytes,
            max_size=params.max_size_bytes,
            extensions=params.extensions,
            favorite_dirs=params.favorite_dirs,
            mode=params.mode,
            stopped_flag=stopped_flag,
            progress_callback=progress_callback
        )

        return groups, stats

    def get_files(self) -> List[File]:
        """Get scanned files after execution."""
        if not self.app or not self.app.files:
            raise RuntimeError("Execute command first before accessing files")
        return self.app.files

    def get_app(self) -> FileDeduplicateApp:
        """Get the underlying app instance (for advanced use cases)."""
        if not self.app:
            raise RuntimeError("Command not executed yet")
        return self.app