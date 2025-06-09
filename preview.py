"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License

preview.py

Image preview widget for the File Deduplicator application.

Implements a QLabel-based image viewer that:
- Displays a preview of selected image files
- Supports common image formats (PNG, JPG, BMP, GIF, WEBP)
- Automatically scales images to fit available space
- Preserves aspect ratio during resizing
- Handles loading errors gracefully
"""

from PySide6.QtWidgets import QLabel, QSizePolicy
from PySide6.QtCore import Qt, QRunnable, QThreadPool, QObject, Signal
from PySide6.QtGui import QPixmap
from core.models import File



class ImageLoaderSignals(QObject):
    image_loaded = Signal(object)
    loading_failed = Signal(str)


class ImageLoaderRunnable(QRunnable):
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        self.signals = ImageLoaderSignals()
        self.is_running = True

    def run(self):
        if not self.is_running:
            return

        pixmap = QPixmap(self.file_path)
        if pixmap.isNull():
            self.signals.loading_failed.emit("Unsupported image format or corrupted file.")
        else:
            self.signals.image_loaded.emit(pixmap)

    def cancel(self):
        self.is_running = False


class ImagePreviewLabel(QLabel):
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("Select an image file to preview...")
        self.setWordWrap(True)
        self.current_file = None
        self.original_pixmap = None
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.thread_pool = QThreadPool()
        self.current_runnable = None

    def set_file(self, file: File):
        self.current_file = file
        self.setText("Loading preview...")

        if self.current_runnable:
            self.current_runnable.cancel()
            self.current_runnable = None

        runnable = ImageLoaderRunnable(file.path)
        runnable.signals.image_loaded.connect(self._on_image_loaded)
        runnable.signals.loading_failed.connect(self._on_loading_failed)
        self.current_runnable = runnable
        self.thread_pool.start(runnable)

    def _on_image_loaded(self, pixmap):
        if self.current_runnable:
            self.original_pixmap = pixmap
            self.update_pixmap()

    def _on_loading_failed(self, error_message):
        self.setText(error_message)
        self.original_pixmap = None

    def update_pixmap(self):
        if not self.original_pixmap:
            return

        scaled = self.original_pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_pixmap()