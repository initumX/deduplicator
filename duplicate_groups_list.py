"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License

duplicate_groups_list.py

UI component for displaying and interacting with duplicate file groups.
Allows users to preview files, open them, reveal in explorer, or move to trash.

Emits signals instead of handling deletion directly, which keeps this widget reusable
and decoupled from business logic.
"""

from PySide6.QtWidgets import QListWidget, QListWidgetItem, QMenu, QAbstractItemView
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, Signal
from core.models import File, DuplicateGroup
from utils.services import FileService
from utils.size_utils import SizeUtils
from core.interfaces import TranslatorProtocol
from translator import DictTranslator


class DuplicateGroupsList(QListWidget):
    """
    A custom list widget that displays duplicate groups.

    Signals:
        file_selected (File): Emitted when a file item is clicked.
        delete_requested (list[str]): Emitted when files should be deleted.
    """
    file_selected = Signal(File)
    delete_requested = Signal(list)  # Signal for deletion request

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.itemClicked.connect(self.on_item_clicked)

        # Use translator from parent or default to English
        self.translator = parent.translator if parent and hasattr(parent, "translator") else DictTranslator("en")
        self.tr = self.translator.tr

    def set_groups(self, groups: list[DuplicateGroup]):
        """Displays a list of duplicate groups in the UI."""
        self.clear()
        for idx, group in enumerate(groups):
            group.files.sort(key=lambda f: not f.is_from_fav_dir)
            size_str = SizeUtils.bytes_to_human(group.size)

            folder_title = f"📁 {self.tr('group_title_prefix')} {idx+1} | {self.tr('group_size_label')}: {size_str}"
            folder_title = QListWidgetItem(folder_title)
            folder_title.setFlags(Qt.ItemFlag.NoItemFlags)  # Inactive
            self.addItem(folder_title)
            for file in group.files:
                fav_marker = " ✅" if file.is_from_fav_dir else ""
                item_text = f"     {file.name}{fav_marker}"
                item = QListWidgetItem(item_text)
                item.setToolTip(file.path)
                item.setData(Qt.ItemDataRole.UserRole, file)
                self.addItem(item)
            empty_item = QListWidgetItem("")
            empty_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.addItem(empty_item)

    def on_item_clicked(self, item):
        """Emits signal when a file item is clicked."""
        file = item.data(Qt.ItemDataRole.UserRole)
        if file:
            self.file_selected.emit(file)

    def show_context_menu(self, point):
        """Shows context menu on right-click."""
        selected_items = self.selectedItems()
        if not selected_items:
            return

        menu = QMenu(self)

        if len(selected_items) == 1:
            file = selected_items[0].data(Qt.ItemDataRole.UserRole)
            open_action = QAction(self.tr("context_menu_open"), self)
            reveal_action = QAction(self.tr("context_menu_reveal"), self)
            delete_action = QAction(self.tr("context_menu_move_to_trash"), self)

            open_action.triggered.connect(lambda _: FileService.open_file(file.path))
            reveal_action.triggered.connect(lambda _: FileService.reveal_in_explorer(file.path))
            delete_action.triggered.connect(lambda _: self.delete_selected_files([selected_items[0]]))

            menu.addAction(open_action)
            menu.addAction(reveal_action)
            menu.addSeparator()
            menu.addAction(delete_action)

        else:
            # Safe format with fallback
            menu_text = self.tr("context_menu_move_multiple")
            try:
                menu_text = menu_text.format(count=len(selected_items))
            except KeyError:
                menu_text = f"Move {len(selected_items)} files to trash"

            delete_action = QAction(menu_text, self)
            delete_action.triggered.connect(lambda _: self.delete_selected_files(selected_items))
            menu.addAction(delete_action)

        menu.exec(self.mapToGlobal(point))

    def delete_selected_files(self, selected_items):
        """Emits signal with file paths to be moved to trash."""
        file_paths = [item.data(Qt.ItemDataRole.UserRole).path for item in selected_items]
        self.delete_requested.emit(file_paths)