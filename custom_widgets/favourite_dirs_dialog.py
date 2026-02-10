"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License

favorite_dirs_dialog.py

This module contains the FavoriteDirsDialog class, a dialog window for managing favorite folders.

The dialog allows users to:
- Add new favorite folders via file dialog
- Remove selected folders from the list
- Save or discard changes via OK/Cancel buttons

Created as part of the File Deduplicator application.
"""

from PySide6.QtWidgets import (
    QDialog, QListWidget, QPushButton, QHBoxLayout,
    QVBoxLayout, QFileDialog, QAbstractItemView
)
from texts import TEXTS


class FavoriteDirsDialog(QDialog):
    """
    Dialog for managing the list of favorite folders.

    Attributes:
        favorite_dirs (list[str]): List of current favorite folders.
        list_widget (QListWidget): Widget for displaying folder list.
    """
    def __init__(self, parent=None, initial_dirs: list[str] = None):
        super().__init__(parent)

        self.setWindowTitle(TEXTS["dialog_favorite_dirs_title"])
        self.setMinimumWidth(500)

        self.favorite_dirs = initial_dirs or []

        # Folder list widget
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)

        if self.favorite_dirs:
            for path in self.favorite_dirs:
                self.list_widget.addItem(path)

        # Buttons
        add_button = QPushButton(TEXTS["btn_add_folder"])
        remove_button = QPushButton(TEXTS["btn_remove_selected"])
        ok_button = QPushButton(TEXTS["btn_ok"])
        cancel_button = QPushButton(TEXTS["btn_cancel"])

        button_layout = QHBoxLayout()
        button_layout.addWidget(add_button)
        button_layout.addWidget(remove_button)
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.list_widget)
        layout.addLayout(button_layout)

        # Connect signals
        add_button.clicked.connect(self.on_add)
        remove_button.clicked.connect(self.on_remove)
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)

    def get_selected_dirs(self) -> list[str]:
        """Returns the selected favorite folders."""
        return [self.list_widget.item(i).text() for i in range(self.list_widget.count())]

    def on_add(self):
        """Handler for adding a new folder."""
        dir_path = QFileDialog.getExistingDirectory(self, TEXTS["dialog_select_favorite_folder_title"])
        if dir_path:
            if dir_path not in self.favorite_dirs:
                self.favorite_dirs.append(dir_path)
                self.list_widget.addItem(dir_path)

    def on_remove(self):
        """Handler for removing selected folders."""
        selected_items = self.list_widget.selectedItems()
        for item in selected_items:
            text = item.text()
            if text in self.favorite_dirs:
                self.favorite_dirs.remove(text)
            self.list_widget.takeItem(self.list_widget.row(item))