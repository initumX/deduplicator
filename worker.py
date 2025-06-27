from PySide6.QtCore import QThread, Signal, QMutex, QDeadlineTimer, QMutexLocker


class DeduplicateWorker(QThread):
    progress = Signal(str, int, object)  # stage, current, total
    finished = Signal(list, object)  # duplicate_groups, stats
    error = Signal(str)

    def __init__(self, app, min_size, max_size, extensions, favorite_dirs, mode):
        super().__init__()
        self.app = app
        self.min_size = min_size
        self.max_size = max_size
        self.extensions = extensions
        self.favorite_dirs = favorite_dirs
        self.mode = mode
        self._stopped = False
        self._mutex = QMutex()
        self._progress_mutex = QMutex()
        self._deadline = QDeadlineTimer(1000)

    def stop(self):
        with QMutexLocker(self._mutex):
            self._stopped = True
        self.wait(self._deadline.remainingTime())

    def is_stopped(self):
        with QMutexLocker(self._mutex):
            return self._stopped

    def safe_emit_progress(self, stage, current, total):
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

            result, stats = self.app.find_duplicates(
                min_size=self.min_size,
                max_size=self.max_size,
                extensions=self.extensions,
                favorite_dirs=self.favorite_dirs,
                mode=self.mode,
                stopped_flag=self.is_stopped,
                progress_callback=self.safe_progress_emit
            )

            if not self.is_stopped():
                self.finished.emit(result, stats)

        except Exception as e:
            if not self.is_stopped():
                self.error.emit(f"{type(e).__name__}: {str(e)}")
        finally:
            self.cleanup()

    def safe_progress_emit(self, stage, current, total=None):
        if not self.is_stopped():
            try:
                self.progress.emit(stage, current, total)
            except RuntimeError:
                self.stop()

    def cleanup(self):
        self.progress.disconnect()
        self.finished.disconnect()
        self.error.disconnect()