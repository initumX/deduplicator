from PySide6.QtWidgets import (
    QDialog, QVBoxLayout,
    QTextEdit, QLabel, QDialogButtonBox
)
from PySide6.QtGui import QFont


class DeletionConfirmDialog(QDialog):
    """Custom deletion confirmation dialog with expandable preview."""

    def __init__(self, parent=None, files_count: int = 0, space_saved: str = "", preview_text: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Confirm Deletion")
        self.setMinimumSize(700, 500)  # Large default size
        self.setSizeGripEnabled(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title_label = QLabel(f"Move {files_count} files to trash?")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Space savings info
        info_label = QLabel(f"Total space saved: {space_saved}")
        info_label.setStyleSheet("color: #2e7d32; font-weight: bold;")
        layout.addWidget(info_label)

        # Separator
        layout.addSpacing(10)

        # Preview text area (stretchable)
        self.preview_edit = QTextEdit()
        self.preview_edit.setReadOnly(True)
        self.preview_edit.setPlainText(preview_text)
        self.preview_edit.setFont(QFont("Consolas", 9))  # Monospace font for file paths
        self.preview_edit.setStyleSheet("""
            QTextEdit {
                background-color: #f5f5f5;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        layout.addWidget(self.preview_edit, stretch=1)  # stretch=1 occupies all available space

        # Buttons
        button_box = QDialogButtonBox()
        button_box.addButton(QDialogButtonBox.StandardButton.No)
        button_box.addButton(QDialogButtonBox.StandardButton.Yes)
        button_box.button(QDialogButtonBox.StandardButton.Yes).setText("Move to Trash")
        button_box.button(QDialogButtonBox.StandardButton.No).setText("Cancel")
        button_box.button(QDialogButtonBox.StandardButton.No).setDefault(True)

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(button_box)