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
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from core.models import File


class ImagePreviewLabel(QLabel):
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("Select an image file to preview...")
        self.setWordWrap(True)
        self.current_file = None
        self.original_pixmap = None
        self.last_scaled_pixmap = None  # Cache last scaled pixmap

        # Set size policy for proper resizing inside QSplitter
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)

    def set_file(self, file: File):
        self.current_file = file
        try:
            pixmap = QPixmap(file.path)
            if pixmap.isNull():
                self.setText("Unsupported image format or corrupted file.")
                self.original_pixmap = None
            else:
                self.original_pixmap = pixmap
                self.update_pixmap()
        except Exception as e:
            self.setText(f"Error loading image:\n{str(e)}")
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
        # Force update pixmap on resize
        self.update_pixmap()