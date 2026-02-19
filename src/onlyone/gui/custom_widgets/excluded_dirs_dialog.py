"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License
excluded_dirs_dialog.py
Dialog for managing excluded folders list.
"""
from PySide6.QtWidgets import (
    QDialog, QListWidget, QPushButton, QHBoxLayout,
    QVBoxLayout, QFileDialog, QAbstractItemView
)


class ExcludedDirsDialog(QDialog):
    """Dialog for managing the list of excluded folders."""

    def __init__(self, parent=None, initial_dirs: list[str] = None):
        super().__init__(parent)
        self.setWindowTitle("Excluded Folders")
        self.setMinimumWidth(500)
        self.excluded_dirs = initial_dirs or []

        self.list_widget = QListWidget(self)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)

        if self.excluded_dirs:
            for path in self.excluded_dirs:
                self.list_widget.addItem(path)

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

        add_button.clicked.connect(self.on_add)
        remove_button.clicked.connect(self.on_remove)
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)

    def get_selected_dirs(self) -> list[str]:
        """Returns the selected excluded folders."""
        return [self.list_widget.item(i).text() for i in range(self.list_widget.count())]

    def on_add(self):
        """Handler for adding a new folder."""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Folder to Exclude")
        if dir_path:
            if dir_path not in self.excluded_dirs:
                self.excluded_dirs.append(dir_path)
                self.list_widget.addItem(dir_path)

    def on_remove(self):
        """Handler for removing selected folders."""
        selected_items = self.list_widget.selectedItems()
        for item in selected_items:
            text = item.text()
            if text in self.excluded_dirs:
                self.excluded_dirs.remove(text)
                self.list_widget.takeItem(self.list_widget.row(item))