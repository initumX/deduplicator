"""
Qt worker runnable — follows modern Qt pattern: QRunnable + QThreadPool.
Accepts DeduplicationParams for unified configuration.
"""
from PySide6.QtCore import QRunnable, QObject, Signal, QMutex, QMutexLocker
from onlyone.core.models import DeduplicationParams
from onlyone.commands import DeduplicationCommand


class WorkerSignals(QObject):
    """Separate QObject to hold signals (QRunnable cannot emit signals directly)."""
    progress = Signal(str, int, object)  # stage, current, total
    finished = Signal(list, object)      # duplicate_groups, stats
    error = Signal(str)


class DeduplicateWorker(QRunnable):
    """
    Worker runnable that performs deduplication in thread pool.
    Automatically deleted after execution (setAutoDelete=True).
    """
    def __init__(self, params: DeduplicationParams):
        super().__init__()
        self.params = params
        self.command = DeduplicationCommand()
        self.signals = WorkerSignals()
        self._stopped = False
        self._mutex = QMutex()
        self.setAutoDelete(True)  # Critical: auto-delete after run() completes

    def stop(self):
        """Sets the stopped flag to signal the worker to terminate gracefully."""
        with QMutexLocker(self._mutex):
            self._stopped = True

    def is_stopped(self) -> bool:
        """Returns True if the worker has been requested to stop."""
        with QMutexLocker(self._mutex):
            return self._stopped

    def safe_progress_emit(self, stage: str, current: int, total=None):
        """Emits progress signal safely with mutex protection."""
        with QMutexLocker(self._mutex):
            if not self._stopped:
                try:
                    self.signals.progress.emit(stage, current, total)
                except RuntimeError:
                    pass

    def run(self):
        """Main execution method. Runs in thread pool thread."""
        try:
            if self.is_stopped():
                return

            groups, stats = self.command.execute(
                self.params,
                stopped_flag=self.is_stopped,
                progress_callback=self.safe_progress_emit
            )

            if not self.is_stopped():
                self.signals.finished.emit(groups, stats)
        except Exception as e:
            if not self.is_stopped():
                self.signals.error.emit(f"{type(e).__name__}: {str(e)}")