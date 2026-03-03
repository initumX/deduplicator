from PySide6.QtCore import QRunnable, QObject, Signal, QMutex, QMutexLocker
from onlyone.services.duplicate_service import DuplicateService
from onlyone.core.models import DuplicateGroup
from typing import List
import logging

logger = logging.getLogger(__name__)


class KeepOneWorkerSignals(QObject):
    """Signals for KeepOneWorker."""
    finished = Signal(list, list)  # files_to_delete, updated_groups
    error = Signal(str)


class KeepOneWorker(QRunnable):
    """
    Worker to calculate files to delete for 'Keep One File Per Group' operation.
    Runs in background thread to avoid UI freeze.
    """

    def __init__(self, duplicate_groups: List[DuplicateGroup]):
        super().__init__()
        self.duplicate_groups = duplicate_groups
        self.signals = KeepOneWorkerSignals()
        self._stopped = False
        self._mutex = QMutex()
        self.setAutoDelete(True)

    def stop(self):
        """Request worker to stop."""
        with QMutexLocker(self._mutex):
            self._stopped = True

    def is_stopped(self) -> bool:
        """Check if stop was requested."""
        with QMutexLocker(self._mutex):
            return self._stopped

    def run(self):
        """Execute calculation in background thread."""
        try:
            if self.is_stopped():
                return

            # This is the heavy operation - now runs in background
            files_to_delete, updated_groups = DuplicateService.keep_only_one_file_per_group(
                self.duplicate_groups
            )

            if self.is_stopped():
                return

            self.signals.finished.emit(files_to_delete, updated_groups)

        except Exception as e:
            logger.exception(f"KeepOneWorker failed: {e}")
            if not self.is_stopped():
                self.signals.error.emit(f"{type(e).__name__}: {str(e)}")