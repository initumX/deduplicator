"""
Qt worker thread: changes to accept DeduplicationParams instead of separate arguments.
All Qt-specific logic preserved exactly as in original.
"""
from PySide6.QtCore import QThread, Signal, QMutex, QDeadlineTimer, QMutexLocker
from core.models import DeduplicationParams
from api import FileDeduplicateApp

class DeduplicateWorker(QThread):
    progress = Signal(str, int, object)  # stage, current, total
    finished = Signal(list, object)      # duplicate_groups, stats
    error = Signal(str)

    def __init__(self, app: FileDeduplicateApp, params: DeduplicationParams):
        """
        Worker accepts BOTH app instance (for state) AND params DTO (for operation).
        Replaces original signature: (app, min_size, max_size, extensions, favorite_dirs, mode)
        """
        super().__init__()
        self.app = app
        self.params = params  # Unified params DTO
        self._stopped = False
        self._mutex = QMutex()
        self._progress_mutex = QMutex()
        self._deadline = QDeadlineTimer(1000)

    def stop(self):
        with QMutexLocker(self._mutex):
            self._stopped = True
        self.wait(self._deadline.remainingTime())

    def is_stopped(self) -> bool:
        with QMutexLocker(self._mutex):
            return self._stopped

    def safe_progress_emit(self, stage: str, current: int, total=None):
        """Exactly matches original method name and signature."""
        with QMutexLocker(self._progress_mutex):
            if not self.is_stopped():
                try:
                    self.progress.emit(stage, current, total)
                except RuntimeError:
                    pass

    def run(self):
        try:
            if self.is_stopped():
                return

            # Execute using params DTO
            groups, stats = self.app.find_duplicates(
                min_size=self.params.min_size_bytes,
                max_size=self.params.max_size_bytes,
                extensions=self.params.extensions,
                favorite_dirs=self.params.favorite_dirs,
                mode=self.params.mode,
                stopped_flag=self.is_stopped,
                progress_callback=self.safe_progress_emit  # ← Critical: matches original name
            )

            if not self.is_stopped():
                self.finished.emit(groups, stats)

        except Exception as e:
            if not self.is_stopped():
                self.error.emit(f"{type(e).__name__}: {str(e)}")
