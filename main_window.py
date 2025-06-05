"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License

main_window.py

File Deduplicator GUI Application

A PyQt-based graphical interface for finding and removing duplicate files.
Allows users to:
- Scan directories for duplicates
- Filter by size and file type
- Choose deduplication mode (fast/normal/full)
- Preview and delete duplicates with progress tracking

Main features:
- Integrated progress dialogs
- File preview (image support)
- Favorite folders prioritization
- Statistics reporting
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QSpinBox, QFileDialog,
    QListWidget, QAbstractItemView, QDialog, QMessageBox,
    QSplitter, QProgressDialog, QApplication, QGroupBox,
    QScrollArea
)
from PySide6.QtCore import Qt, QSettings

from core.models import DeduplicationMode, Stage
from api import FileDeduplicateApp
from utils.services import FileService
from dialogs import FavoriteDirsDialog
from preview import ImagePreviewLabel
from utils.services import DuplicateService
from utils.size_utils import SizeUtils
from duplicate_groups_list import DuplicateGroupsList
import os


class SettingsManager:
    def __init__(self):
        self.settings = QSettings("MyCompany", "FileDeduplicator")

    def save_settings(self, key: str, value: any):
        self.settings.setValue(key, value)

    def load_settings(self, key: str, default: any = None) -> any:
        return self.settings.value(key, default)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("File Deduplicator")
        self.resize(1000, 700)

        self.app = FileDeduplicateApp("")
        self.settings_manager = SettingsManager()

        # Widgets
        self.root_dir_input = QLineEdit()
        self.select_dir_button = QPushButton("Select Root Folder")
        self.extension_filter_input = QLineEdit()
        self.min_size_spin = QSpinBox()
        self.min_unit_combo = QComboBox()
        self.max_size_spin = QSpinBox()
        self.max_unit_combo = QComboBox()
        self.favorite_dirs_button = QPushButton("Select Favorite Folders")
        self.dedupe_mode_combo = QComboBox()
        self.find_duplicates_button = QPushButton("Find Duplicates")
        self.progress_dialog = None
        self.stats_window = None
        self.keep_one_button = QPushButton("Keep One File Per Group")
        self.about_button = QPushButton("About")
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # QListWidget with scroll
        self.favorite_list_widget = QListWidget()
        self.favorite_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)

        # Output widgets
        self.groups_list = DuplicateGroupsList()

        self.image_preview = ImagePreviewLabel()
        self.image_preview.setMinimumSize(300, 200)

        # Layouts
        self.init_ui()
        self.restore_settings()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        # --- Root Directory Layout ---
        root_layout = QHBoxLayout()
        root_layout.addWidget(QLabel("Root Folder:"))
        self.root_dir_input.setPlaceholderText("Select directory...")
        root_layout.addWidget(self.root_dir_input)
        self.select_dir_button.clicked.connect(self.select_root_folder)
        root_layout.addWidget(self.select_dir_button)

        # --- Filters Group Box ---
        filters_group = QGroupBox("Filters")
        filters_group.setFixedWidth(220)
        filters_group.setFixedHeight(200)

        # Min Size Layout
        min_size_layout = QHBoxLayout()
        self.min_size_spin.setRange(0, 1024 * 1024)
        self.min_size_spin.setValue(100)
        self.min_size_spin.setFixedWidth(60)
        self.min_unit_combo.addItems(["KB", "MB", "GB"])
        self.min_unit_combo.setCurrentText("KB")
        self.min_unit_combo.setFixedWidth(60)
        min_size_layout.addWidget(QLabel("Min Size:"))
        min_size_layout.addWidget(self.min_size_spin)
        min_size_layout.addWidget(self.min_unit_combo)

        # Max Size Layout
        max_size_layout = QHBoxLayout()
        self.max_size_spin.setRange(0, 1024 * 1024)
        self.max_size_spin.setValue(100)
        self.max_size_spin.setFixedWidth(60)
        self.max_unit_combo.addItems(["KB", "MB", "GB"])
        self.max_unit_combo.setCurrentText("MB")
        self.max_unit_combo.setFixedWidth(60)
        max_size_layout.addWidget(QLabel("Max Size:"))
        max_size_layout.addWidget(self.max_size_spin)
        max_size_layout.addWidget(self.max_unit_combo)

        # Extension filter layout
        extension_layout_inside = QHBoxLayout()
        self.extension_filter_input.setPlaceholderText(".jpg,.png")
        self.extension_filter_input.setToolTip(
            "Enter comma-separated file extensions to filter (e.g., .jpg, .png, .pdf)\n"
            "Or leave blank to avoid extension filtering.")
        extension_layout_inside.addWidget(QLabel("Extensions:"))
        extension_layout_inside.addWidget(self.extension_filter_input)

        # Vertical layout inside group box
        filters_group_layout = QVBoxLayout()
        filters_group_layout.addLayout(min_size_layout)
        filters_group_layout.addLayout(max_size_layout)
        filters_group_layout.addLayout(extension_layout_inside)
        filters_group.setLayout(filters_group_layout)
        # --- End of Filters Group Box ---

        # --- Favorite Folders UI Block ---
        favorite_group = QGroupBox("Favorite Folders")
        favorite_group.setFixedWidth(600)
        favorite_group.setFixedHeight(200)

        favorite_layout = QVBoxLayout()

        self.favorite_dirs_button = QPushButton("Manage Favorite Folders List")
        self.favorite_dirs_button.setToolTip(
            "Files from favorite folders are prioritized in each group. \n\n"
            "When using 'Keep One File Per Group', the first file \n\n"
            "from a favorite folder in the group will be preserved, \n\n"
            "and others will be moved to trash. \n\n"
            "Only one file per group can be saved this way.\n"
        )
        self.favorite_dirs_button.clicked.connect(self.select_favorite_dirs)
        favorite_layout.addWidget(self.favorite_dirs_button)

        # Включаем прокрутку
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # Vertical scroll not needed
        scroll_area.setWidget(self.favorite_list_widget)

        # Limit height using a container widget
        container = QWidget()
        container.setLayout(QVBoxLayout())
        container.layout().addWidget(scroll_area)
        container.layout().setContentsMargins(0, 0, 0, 0)
        container.setFixedHeight(120)  # Высота списка

        favorite_layout.addWidget(container)
        favorite_group.setLayout(favorite_layout)

        # --- Level layout: Size Filter + Favorite Folders ---
        level_layout = QHBoxLayout()
        level_layout.addWidget(filters_group)
        level_layout.addWidget(favorite_group)
        level_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # --- Unified Control Layout (Buttons and Deduplication Mode) ---
        control_layout = QHBoxLayout()
        self.find_duplicates_button.setFixedWidth(160)
        self.find_duplicates_button.setToolTip(
            "Start looking for duplicate files. \n\n"
            "Files from your favorite folders will be marked with ✅-sign"
        )
        self.find_duplicates_button.clicked.connect(self.start_deduplication)
        control_layout.addWidget(self.find_duplicates_button)

        mode_label = QLabel("Mode:")
        control_layout.addWidget(mode_label)
        self.dedupe_mode_combo.addItems([mode.value.upper() for mode in DeduplicationMode])
        self.dedupe_mode_combo.setFixedWidth(80)
        self.dedupe_mode_combo.setToolTip(
            "FAST: Compare file sizes and checksums of first 64KB only\n\n"
            "NORMAL: Compare sizes and checksums of first, middle and last 64KB\n\n"
            "FULL: Compare full file contents (slowest)"
        )
        control_layout.addWidget(self.dedupe_mode_combo)

        self.keep_one_button.setToolTip(
            "Keep one file (the first one) per group and move the rest to trash"
        )
        self.keep_one_button.setFixedWidth(200)
        self.keep_one_button.clicked.connect(self.keep_one_file_per_group)
        control_layout.addWidget(self.keep_one_button)

        self.about_button.setFixedWidth(80)
        self.about_button.setToolTip("Learn more about the program and its author")
        self.about_button.clicked.connect(self.show_about_dialog)

        control_layout.addWidget(self.about_button)

        control_layout.addStretch()  # Все элементы слева
        control_layout.setContentsMargins(0, 20, 0, 0)  # top=20

        # --- Splitter for groups list and image preview ---
        self.splitter.addWidget(self.groups_list)
        self.splitter.addWidget(self.image_preview)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        width = self.splitter.width()
        self.splitter.setSizes([int(width * 0.4), int(width * 0.6)])
        self.groups_list.setMinimumWidth(200)

        # --- Main Layout Assembly ---
        main_layout = QVBoxLayout()
        main_layout.addLayout(root_layout)
        main_layout.addLayout(level_layout)

        main_layout.addLayout(control_layout)
        main_layout.addWidget(self.splitter)
        main_widget.setLayout(main_layout)

        self.groups_list.file_selected.connect(self.image_preview.set_file)
        self.groups_list.delete_requested.connect(self.handle_delete_files)

    def resizeEvent(self, event):
        super().resizeEvent(event)

        # Recalculate splitter proportions when the window is resized
        if hasattr(self, 'splitter'):
            sizes = self.splitter.sizes()
            total = sum(sizes)
            if total > 0:
                ratio = sizes[0] / total  # Preserve left panel ratio
                new_left = int(self.splitter.width() * ratio)
                new_right = self.splitter.width() - new_left
                self.splitter.setSizes([new_left, new_right])

    def select_root_folder(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Root Folder")
        if dir_path:
            self.root_dir_input.setText(dir_path)

    def select_favorite_dirs(self):
        current_dirs = getattr(self.app, 'favorite_dirs', [])

        dialog = FavoriteDirsDialog(self, current_dirs)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_dirs = dialog.get_selected_dirs()
            self.app.favorite_dirs = selected_dirs

            self.favorite_list_widget.clear()

            for path in selected_dirs:
                self.favorite_list_widget.addItem(path)
            QMessageBox.information(self, "Success", f"Selected {len(selected_dirs)} favorite folders.")

        else:
            pass

    def keep_one_file_per_group(self):
        duplicate_groups = self.app.get_duplicate_groups()
        if not duplicate_groups:
            QMessageBox.information(self, "Info", "No duplicate groups found.")
            return

        files_to_delete, updated_groups = DuplicateService.keep_only_one_file_per_group(duplicate_groups)

        if not files_to_delete:
            QMessageBox.information(self, "Info", "Nothing to delete.")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to move {len(files_to_delete)} files to trash?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.handle_delete_files(files_to_delete)

    def handle_delete_files(self, file_paths):
        if not file_paths:
            return

        total = len(file_paths)
        self.progress_dialog = QProgressDialog("Moving files to trash...", "Cancel", 0, total, self)
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setWindowTitle("Deleting Files")
        self.progress_dialog.show()

        try:
            for i, path in enumerate(file_paths):
                FileService.move_to_trash(path)
                self.progress_dialog.setValue(i + 1)
                self.progress_dialog.setLabelText(f"Deleting: {os.path.basename(path)}")
                QApplication.processEvents()  # Обновляем интерфейс

                if self.progress_dialog.wasCanceled():
                    raise Exception("Operation was cancelled by the user.")

            # Refresh
            updated_groups = DuplicateService.remove_files_from_groups(
                self.app.get_duplicate_groups(), file_paths
            )
            self.app.duplicate_groups = updated_groups
            self.groups_list.set_groups(updated_groups)

            QMessageBox.information(self, "Success", f"{total} files moved to trash.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to delete files:\n{e}")
        finally:
            self.progress_dialog.close()
            self.progress_dialog = None

    def show_about_dialog(self):
        QMessageBox.about(
            self,
            "About File Deduplicator",
            """<b>File Deduplicator</b><br><br>
            Version: 2.0<br>
            A tool to find and remove duplicate files.<br><br>
            <b>Features:</b><br><br>
            - Filtering by size and extension<br><br>
            - Using xxhash (it's very fast)<br><br>
            - 3 modes of searching duplicates(fast, normal, full)<br><br>
            - Deleting all duplicates by one click(Keep one file per group) <br><br>
            - Image preview, context menu, autosaving preferences, tooltips <br><br>
             - and much more<br><br>
            © Copyright (c) 2025 initumX (initum.x@gmail.com) <br><br>
            Licensed under the MIT License<br>
            """
        )

    def start_deduplication(self):
        root_dir = self.root_dir_input.text().strip()
        if not root_dir:
            QMessageBox.warning(self, "Input Error", "Please select a root directory.")
            return

        self.app.root_dir = root_dir

        # Size filters
        min_size_value = self.min_size_spin.value()
        min_unit = self.min_unit_combo.currentText()

        max_size_value = self.max_size_spin.value()
        max_unit = self.max_unit_combo.currentText()

        # Example: "10MB", "512KB"
        min_size_str = f"{min_size_value}{min_unit}"
        max_size_str = f"{max_size_value}{max_unit}"

        try:
            min_size = SizeUtils.human_to_bytes(min_size_str)
            max_size = SizeUtils.human_to_bytes(max_size_str)
        except ValueError as e:
            QMessageBox.warning(self, "Input Error", f"Invalid size format: {e}")
            return

        extensions = [
            ext.strip() for ext in self.extension_filter_input.text().split(",")
            if ext.strip()
        ]

        mode_name = self.dedupe_mode_combo.currentText()
        dedupe_mode = DeduplicationMode[mode_name]

        self.progress_dialog = QProgressDialog("Scanning and deduplicating...", "Cancel", 0, 100, self)
        self.progress_dialog.setModal(True)
        self.progress_dialog.setWindowTitle("Processing...")
        self.progress_dialog.show()
        QApplication.processEvents()

        def progress_callback(*args):
            stage, current, total = args
            percent = int((current / total) * 100) if total > 0 else 0
            self.progress_dialog.setValue(percent)
            self.progress_dialog.setLabelText(f"{stage}: {current}/{total}")

        def stopped_flag():
            return self.progress_dialog.wasCanceled()

        try:
            duplicate_groups, stats = self.app.find_duplicates(
                min_size=min_size,
                max_size=max_size,
                extensions=extensions,
                favorite_dirs=self.app.favorite_dirs,
                mode=dedupe_mode,
                stopped_flag=stopped_flag,
                progress_callback=progress_callback
            )

            self.groups_list.set_groups(duplicate_groups)

            # Forming Text for Statistics
            def format_value(value):
                if isinstance(value, float):
                    return f"{value:.2f}"
                return str(value)

            stats_text = "\n".join([
                f"{key.replace('_', ' ').title()}: {format_value(value)}"
                for key, value in stats.__dict__.items()
                if key not in ("stage_stats", "_listeners")
            ])
            stats_text += "\n\nStage (Criteria of comparing): GROUPS / FILES / TIME \n\n"
            for stage_key, data in stats.stage_stats.items():
                try:
                    stage_label = Stage[stage_key.upper()].value
                except KeyError:
                    stage_label = stage_key.title()

                stats_text += f"{stage_label}: {data['groups']} / {data['files']} / {data['time']:.2f}s\n\n"

            self.stats_window = QMessageBox(self)
            self.stats_window.setWindowTitle("Deduplication Statistics")
            self.stats_window.setText(stats_text)
            self.stats_window.setIcon(QMessageBox.Icon.Information)
            self.stats_window.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred:\n{str(e)}")

    def closeEvent(self, event):
        self.save_settings()
        super().closeEvent(event)

    def save_settings(self):
        self.settings_manager.save_settings("root_dir", self.root_dir_input.text())
        self.settings_manager.save_settings("min_size", self.min_size_spin.value())
        self.settings_manager.save_settings("max_size", self.max_size_spin.value())
        self.settings_manager.save_settings("min_unit_index", self.min_unit_combo.currentIndex())
        self.settings_manager.save_settings("max_unit_index", self.max_unit_combo.currentIndex())
        self.settings_manager.save_settings("dedupe_mode", self.dedupe_mode_combo.currentIndex())
        self.settings_manager.save_settings("extensions", self.extension_filter_input.text())
        self.settings_manager.save_settings("splitter_sizes", list(self.splitter.sizes()))
        self.settings_manager.save_settings("favorite_dirs", self.app.favorite_dirs)
        # favorite_dirs = getattr(self.app, 'favorite_dirs', [])
        # self.settings_manager.save_settings("favorite_dirs", list(favorite_dirs))

    def restore_settings(self):
        self.root_dir_input.setText(self.settings_manager.load_settings("root_dir", ""))

        min_size = self.settings_manager.load_settings("min_size", "100")
        self.min_size_spin.setValue(int(min_size))

        max_size = self.settings_manager.load_settings("max_size", "100")
        self.max_size_spin.setValue(int(max_size))

        min_unit_index = self.settings_manager.load_settings("min_unit_index", "0")
        self.min_unit_combo.setCurrentIndex(int(min_unit_index))

        max_unit_index = self.settings_manager.load_settings("max_unit_index", "1")  # default to MB
        self.max_unit_combo.setCurrentIndex(int(max_unit_index))

        dedupe_mode = self.settings_manager.load_settings("dedupe_mode", "1")
        self.dedupe_mode_combo.setCurrentIndex(int(dedupe_mode))

        extensions = self.settings_manager.load_settings("extensions", "")
        self.extension_filter_input.setText(extensions)

        splitter_sizes = self.settings_manager.load_settings("splitter_sizes", None)
        if splitter_sizes:
            self.splitter.setSizes([int(x) for x in splitter_sizes])
        else:
            self.splitter.setSizes([400, 600])

        saved_dirs = self.settings_manager.load_settings("favorite_dirs", [])
        if isinstance(saved_dirs, str):
            saved_dirs = [d.strip() for d in saved_dirs.split(";") if d.strip()]
        elif not isinstance(saved_dirs, list):
            saved_dirs = []
        self.app.favorite_dirs = saved_dirs

        # Заполняем список сразу при запуске
        self.favorite_list_widget.clear()
        for path in self.app.favorite_dirs:
            self.favorite_list_widget.addItem(path)

import sys
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())