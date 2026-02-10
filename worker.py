"""
Qt worker thread — accepts DeduplicationParams instead of separate arguments.
"""
from PySide6.QtCore import QThread, Signal, QMutex, QDeadlineTimer, QMutexLocker
from core.models import DeduplicationParams
from commands import DeduplicationCommand

class DeduplicateWorker(QThread):
    progress = Signal(str, int, object)  # stage, current, total
    finished = Signal(list, object)      # duplicate_groups, stats
    error = Signal(str)

    def __init__(self, params: DeduplicationParams):
        super().__init__()
        self.params = params
        self.command = DeduplicationCommand()
        self._stopped = False
        self._mutex = QMutex()
        self._progress_mutex = QMutex()

    def stop(self):
        with QMutexLocker(self._mutex):
            self._stopped = True
        deadline = QDeadlineTimer(1000)
        self.wait(deadline.remainingTime())

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

            groups, stats = self.command.execute(
                self.params,
                stopped_flag=self.is_stopped,
                progress_callback=self.safe_progress_emit
            )

            if not self.is_stopped():
                self.finished.emit(groups, stats)
        except Exception as e:
            if not self.is_stopped():
                self.error.emit(f"{type(e).__name__}: {str(e)}")