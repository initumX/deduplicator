from PySide6.QtCore import QThread, Signal

class DeduplicateWorker(QThread):
    progress = Signal(str, int, object)  # stage, current, total (может быть None)
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

    def stop(self):
        self._stopped = True

    def is_stopped(self):
        return self._stopped

    def run(self):
        try:
            # Start duplicate searching
            result, stats = self.app.find_duplicates(
                min_size=self.min_size,
                max_size=self.max_size,
                extensions=self.extensions,
                favorite_dirs=self.favorite_dirs,
                mode=self.mode,
                stopped_flag=self.is_stopped,
                progress_callback=lambda stage, cur, total=None: self.progress.emit(stage, cur, total)
            )
            if not self._stopped:
                self.finished.emit(result, stats)
        except Exception as e:
            self.error.emit(str(e))