"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License

favourite_dirs_dialog.py

This module contains the FavouriteDirsDialog class, a dialog window for managing favourite folders.

The dialog allows users to:
- Add new favourite folders via file dialog
- Remove selected folders from the list
- Save or discard changes via OK/Cancel buttons

Created as part of the File Deduplicator application.
"""

from PySide6.QtWidgets import (
    QDialog, QListWidget, QPushButton, QHBoxLayout,
    QVBoxLayout, QFileDialog, QAbstractItemView
)


class FavouriteDirsDialog(QDialog):
    """
    Dialog for managing the list of favourite folders.

    Attributes:
        favourite_dirs (list[str]): List of current favourite folders.
        list_widget (QListWidget): Widget for displaying folder list.
    """
    def __init__(self, parent=None, initial_dirs: list[str] = None):
        super().__init__(parent)

        self.setWindowTitle("Favourite Folders")
        self.setMinimumWidth(500)

        self.favourite_dirs = initial_dirs or []

        # Folder list widget with explicit parent
        self.list_widget = QListWidget(self)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)

        if self.favourite_dirs:
            for path in self.favourite_dirs:
                self.list_widget.addItem(path)

        # Buttons with explicit parent
        add_button = QPushButton("Add Folder", self)
        remove_button = QPushButton("Remove Selected", self)
        ok_button = QPushButton("OK", self)
        cancel_button = QPushButton("Cancel", self)

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
        dir_path = QFileDialog.getExistingDirectory(self, "Select Favourite Folder to add")
        if dir_path:
            if dir_path not in self.favourite_dirs:
                self.favourite_dirs.append(dir_path)
                self.list_widget.addItem(dir_path)

    def on_remove(self):
        """Handler for removing selected folders."""
        selected_items = self.list_widget.selectedItems()
        for item in selected_items:
            text = item.text()
            if text in self.favourite_dirs:
                self.favourite_dirs.remove(text)
            self.list_widget.takeItem(self.list_widget.row(item))