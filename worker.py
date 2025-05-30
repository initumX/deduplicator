from PyQt5.QtCore import QThread, pyqtSignal
from typing import Any, Callable, List, Optional, Tuple
from core.models import FileCollection, DuplicateGroup


class Worker(QThread):
    """
    A generic worker thread for running long-running operations.

    Emits:
        started() - When the task starts
        finished(result) - When the task completes successfully
        error_occurred(msg) - On any exception
        progress(value) - For progress updates (0-100)
        log(message) - For logging status updates
    """
    started = pyqtSignal()
    finished = pyqtSignal(object)
    error_occurred = pyqtSignal(str)
    progress = pyqtSignal(int)
    log = pyqtSignal(str)

    def __init__(
            self,
            func: Callable[..., Any],
            *args,
            **kwargs
    ):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self._stop_flag = False

    def run(self):
        """Runs the function in a separate thread."""
        self.started.emit()
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            self._stop_flag = False

    def stop(self):
        """Request stopping the operation."""
        self._stop_flag = True

    def stopped_flag(self) -> bool:
        """Callable passed to backend methods to check if operation should stop."""
        return self._stop_flag