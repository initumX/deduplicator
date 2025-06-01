import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow,
    QLabel, QPushButton,
    QVBoxLayout, QWidget,
    QAction, QMessageBox,
    QDialog, QFormLayout,
    QLineEdit, QDialogButtonBox,
    QSpinBox, QComboBox,
    QHBoxLayout, QFileDialog,
    QTreeWidget, QTreeWidgetItem,
    QStatusBar, QMenu, QSplitter,
)

from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import QSize

from worker import Worker
import os, json

from PyQt5.QtCore import Qt, QSettings, QThread, pyqtSignal
from api import FileDeduplicateApp
from core.models import DuplicateGroup, FileCollection, File
from utils.services import FileService

# ==============================
# Helper Functions
# ==============================

def human_readable(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes // 1024} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes // (1024 * 1024)} MB"
    else:
        return f"{size_bytes // (1024 * 1024 * 1024)} GB"


# ==============================
# Worker Thread Class
# ==============================

class Worker(QThread):
    started = pyqtSignal()
    finished = pyqtSignal(object)
    error_occurred = pyqtSignal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self._stop_flag = False

    def run(self):
        self.started.emit()
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            self._stop_flag = False

    def stop(self):
        self._stop_flag = True

    def stopped_flag(self):
        return self._stop_flag


# ==============================
# Preferences Dialog
# ==============================

class PreferencesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")

        layout = QFormLayout()

        # === Default Directory Input ===
        self.dir_input = QLineEdit()
        self.dir_input.setReadOnly(True)
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self.select_directory)
        self.setMinimumWidth(600)

        dir_layout = QHBoxLayout()
        dir_layout.addWidget(self.dir_input)
        dir_layout.addWidget(self.browse_button)
        layout.addRow("Default Directory:", dir_layout)

        # Load settings at start
        self.settings = QSettings("MyCompany", "FileDeduplicator")
        default_dir = self.settings.value("default_directory", "")

        # === Favourite Path Input ===
        self.fav_path_input = QLineEdit()
        self.fav_path_input.setReadOnly(True)
        self.fav_browse_button = QPushButton("Browse...")
        self.fav_browse_button.clicked.connect(self.select_favourite_directory)

        fav_layout = QHBoxLayout()
        fav_layout.addWidget(self.fav_path_input)
        fav_layout.addWidget(self.fav_browse_button)
        layout.addRow("Favourite Path (Originals):", fav_layout)

        # Load saved value
        fav_dir = self.settings.value("favourite_directory", "")
        self.fav_path_input.setText(fav_dir)

        # Always restore last known directory
        if not default_dir:
            default_dir = ""

        self.dir_input.setText(default_dir)

        # === Similar Images Threshold ===
        self.threshold_input = QSpinBox()
        self.threshold_input.setRange(1, 7)
        self.threshold_input.setValue(5)
        self.threshold_input.setToolTip(
            "Threshold determines how similar images must be to be grouped.\n"
            "Higher values allow more visual differences between images."
        )
        threshold_label = QLabel("Similar Image Threshold:")
        threshold_label.setToolTip(
            "Threshold determines how similar images must be to be grouped.\n"
            "Higher values allow more visual differences between images."
        )
        layout.addRow(threshold_label, self.threshold_input)

        # === Min Size Input ===
        self.min_size_input = QSpinBox()
        self.min_size_input.setRange(0, 1024 * 1024)
        self.min_size_input.setValue(1)

        self.min_unit_combo = QComboBox()
        self.min_unit_combo.addItems(["KB", "MB", "GB"])

        min_size_layout = QHBoxLayout()
        min_size_layout.addWidget(self.min_size_input)
        min_size_layout.addWidget(self.min_unit_combo)
        layout.addRow("Minimum File Size:", min_size_layout)

        # Load saved min size in bytes
        self.settings = QSettings("MyCompany", "FileDeduplicator")
        min_size_bytes = int(self.settings.value("min_size", 102400))  # Default: 100 KB
        self._set_min_size_fields(min_size_bytes)

        # === Max Size Input ===
        self.max_size_input = QSpinBox()
        self.max_size_input.setRange(0, 1024 * 1024)
        self.max_size_input.setValue(15)  # Default is now 15 MB

        self.max_unit_combo = QComboBox()
        self.max_unit_combo.addItems(["KB", "MB", "GB"])

        max_size_layout = QHBoxLayout()
        max_size_layout.addWidget(self.max_size_input)
        max_size_layout.addWidget(self.max_unit_combo)
        layout.addRow("Maximum File Size:", max_size_layout)

        max_size_bytes = int(self.settings.value("max_size", 15728640))  # Default: 15 MB
        if max_size_bytes > 0:
            self._set_max_size_fields(max_size_bytes)

        # === Extensions Input ===
        self.ext_input = QLineEdit()
        ext_value = self.settings.value("extensions", ".jpg")
        self.ext_input.setText(ext_value)
        layout.addRow("Extensions (comma-separated):", self.ext_input)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.save_and_accept)
        buttons.rejected.connect(self.reject)

        reset_button = QPushButton("Reset to Defaults")
        reset_button.clicked.connect(self.reset_to_defaults)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(reset_button)
        btn_layout.addWidget(buttons)

        layout.addRow(btn_layout)

        self.setLayout(layout)

    def select_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Default Directory")
        if dir_path:
            self.dir_input.setText(dir_path)

    def select_favourite_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Favourite Directory")
        if dir_path:
            self.fav_path_input.setText(dir_path)

    def _set_min_size_fields(self, bytes_value):
        """Set the UI for minimum size"""
        if bytes_value <= 0:
            self.min_size_input.setValue(0)
            self.min_unit_combo.setCurrentText("KB")
        elif bytes_value >= (1 << 30):  # GB
            self.min_size_input.setValue(bytes_value >> 30)
            self.min_unit_combo.setCurrentText("GB")
        elif bytes_value >= (1 << 20):  # MB
            self.min_size_input.setValue(bytes_value >> 20)
            self.min_unit_combo.setCurrentText("MB")
        else:  # KB
            self.min_size_input.setValue((bytes_value + 512) >> 10)
            self.min_unit_combo.setCurrentText("KB")

    def _set_max_size_fields(self, bytes_value):
        """Set the UI for maximum size"""
        if bytes_value is None or bytes_value <= 0:
            self.max_size_input.setValue(15)  # Default: 15 MB
            self.max_unit_combo.setCurrentText("MB")
        elif bytes_value >= (1 << 30):  # GB
            self.max_size_input.setValue(bytes_value >> 30)
            self.max_unit_combo.setCurrentText("GB")
        elif bytes_value >= (1 << 20):  # MB
            self.max_size_input.setValue(bytes_value >> 20)
            self.max_unit_combo.setCurrentText("MB")
        else:  # KB
            self.max_size_input.setValue((bytes_value + 512) >> 10)
            self.max_unit_combo.setCurrentText("KB")

    def get_min_size_in_bytes(self):
        value = self.min_size_input.value()
        unit = self.min_unit_combo.currentText()
        if value <= 0:
            return None
        if unit == "KB":
            return value * 1024
        elif unit == "MB":
            return value * 1024 * 1024
        elif unit == "GB":
            return value * 1024 * 1024 * 1024

    def get_max_size_in_bytes(self):
        value = self.max_size_input.value()
        unit = self.max_unit_combo.currentText()
        if value <= 0:
            return None
        if unit == "KB":
            return value * 1024
        elif unit == "MB":
            return value * 1024 * 1024
        elif unit == "GB":
            return value * 1024 * 1024 * 1024

    def get_image_threshold(self):
        return self.threshold_input.value()

    def save_and_accept(self):
        self.settings.setValue("default_directory", self.dir_input.text())  # Only save if user picked one
        self.settings.setValue("favourite_directory", self.fav_path_input.text())
        self.settings.setValue("min_size", self.get_min_size_in_bytes() or 0)
        self.settings.setValue("max_size", self.get_max_size_in_bytes() or 0)
        self.settings.setValue("extensions", self.ext_input.text())
        self.settings.setValue("image_threshold", self.threshold_input.value())
        self.accept()

    def reset_to_defaults(self):
        """Reset all inputs to predefined default values"""
        # Set directory blank
        self.dir_input.setText("")

        self.fav_path_input.setText("")

        # Min size = 100 KB
        self.min_size_input.setValue(100)
        self.min_unit_combo.setCurrentText("KB")

        # Max size = 15 MB
        self.max_size_input.setValue(15)
        self.max_unit_combo.setCurrentText("MB")

        # Extensions = .jpg
        self.ext_input.setText(".jpg")

        # Threshold = 5
        self.threshold_input.setValue(5)

# ==============================
# Main Window Class
# ==============================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("File Deduplicator")
        self.resize(800, 600)

        self.app = None
        self.file_collection = None
        self.duplicate_groups = []

        # Settings
        self.settings = QSettings("MyCompany", "FileDeduplicator")

        # Info labels
        self.path_label = QLabel("📁 Path to Scan: Not selected")
        self.min_size_label = QLabel("📏 Min Size: not set")
        self.max_size_label = QLabel("📏 Max Size: not set")
        self.ext_label = QLabel("📎 Extensions: .jpg, .png")

        # Status bar
        self.status_label = QLabel("Status: Ready")
        self.setStatusBar(QStatusBar())
        self.statusBar().addWidget(self.status_label, 1)

        # Tree widget (left panel)
        self.tree = QTreeWidget()
        self.tree.setMinimumWidth(300)
        self.tree.setHeaderLabel("Scanned Files / Groups")
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        self.tree.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.tree.itemSelectionChanged.connect(self.on_tree_selection_changed)
        self.tree.itemDoubleClicked.connect(self.on_tree_item_double_clicked)


        # Image preview label (right panel)
        self.image_preview = QLabel("No image selected")
        self.image_preview.setAlignment(Qt.AlignCenter)
        self.image_preview.setStyleSheet("background-color: #f0f0f0;")

        # === Splitter layout ===
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.tree)
        splitter.addWidget(self.image_preview)

        # Set initial sizes
        splitter.setSizes([500, 500])  # ← Allocate more space to the tree

        # === Info panel ===
        info_container = QWidget()
        info_layout = QVBoxLayout()
        info_layout.addWidget(self.path_label)
        info_layout.addWidget(self.min_size_label)
        info_layout.addWidget(self.max_size_label)
        info_layout.addWidget(self.ext_label)
        info_container.setLayout(info_layout)

        # === Main layout ===
        main_layout = QVBoxLayout()
        main_layout.addWidget(info_container)
        main_layout.addWidget(splitter)

        # Give more vertical space to the splitter area
        main_layout.setStretch(0, 1)  # info_container
        main_layout.setStretch(1, 4)  # splitter (tree + preview)

        # Wrap layout in central widget
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # Set some minimum height for the tree if needed
        self.tree.setMinimumHeight(400)

        self.actions_to_disable = []

        # Menu
        self.create_menu()

        # Load settings
        self.update_scan_info()
        self.check_default_directory()

    def on_tree_selection_changed(self):
        selected_items = self.tree.selectedItems()
        if not selected_items:
            self.image_preview.setText("No image selected")
            return

        item = selected_items[0]
        path = item.toolTip(0)

        if not FileService.is_valid_image(path):
            self.image_preview.setText("Not an image")
            return

        try:
            pixmap = QPixmap(path)
            if pixmap.isNull():
                raise ValueError(f"Failed to load {path}")

            # Maximum preview size (e.g., 600x600)
            max_preview_size = self.image_preview.size().boundedTo(QSize(1024, 1024))

            scaled_pixmap = pixmap.scaled(
                max_preview_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

            self.image_preview.setPixmap(scaled_pixmap)
            self.image_preview.setToolTip(path)
        except Exception as e:
            self.image_preview.setText(f"Error\n{str(e)}")
            self.image_preview.setToolTip("")

    def on_tree_item_double_clicked(self, item, column):
        path = item.toolTip(0)
        try:
            if FileService.is_valid_image(path):
                FileService.open_file(path)
            else:
                FileService.reveal_in_explorer(path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open file:\n{e}")

    def show_context_menu(self, position):
        selected_items = self.tree.selectedItems()
        if not selected_items:
            return

        # Create menu
        menu = QMenu(self)

        if len(selected_items) == 1:
            # Single file selected: show all options
            open_action = QAction("Open File", self)
            reveal_action = QAction("Reveal in Explorer", self)
            delete_action = QAction("Move to Trash", self)

            open_action.triggered.connect(lambda: self.open_selected_files(selected_items))
            reveal_action.triggered.connect(lambda: self.reveal_in_explorer(selected_items))
            delete_action.triggered.connect(lambda: self.delete_selected_files(selected_items))

            menu.addAction(open_action)
            menu.addAction(reveal_action)
            menu.addAction(delete_action)

        else:
            # Multiple files selected: only allow deletion
            delete_action = QAction(f"Move {len(selected_items)} files to Trash", self)
            delete_action.triggered.connect(lambda: self.delete_selected_files(selected_items))
            menu.addAction(delete_action)

        # Show menu
        menu.exec_(self.tree.viewport().mapToGlobal(position))


    def open_selected_files(self, items):
        for item in items:
            path = item.toolTip(0)
            try:
                FileService.open_file(path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open file:\n{e}")

    def reveal_in_explorer(self, items):
        for item in items:
            path = item.toolTip(0)
            try:
                FileService.reveal_in_explorer(path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to reveal file:\n{e}")

    def delete_selected_files(self, items):
        paths = [item.toolTip(0) for item in items]
        reply = QMessageBox.question(
            self,
            'Confirm Deletion',
            f"Are you sure you want to move {len(paths)} files to trash?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                FileService.move_multiple_to_trash(paths)
                self.status_label.setText(f"Moved {len(paths)} files to trash.")

                # 1. Update file collection
                remaining_files = [f for f in self.file_collection.files if f.path not in paths]
                self.file_collection = FileCollection(remaining_files)

                # 2. Update duplicate groups
                updated_groups = []
                for group in self.duplicate_groups:
                    filtered_files = [f for f in group.files if f.path not in paths]
                    if len(filtered_files) > 1:
                        group.files = filtered_files
                        updated_groups.append(group)

                self.duplicate_groups = updated_groups

                # 3. Decide what to show next:
                if self.tree.topLevelItemCount() > 0 and isinstance(self.tree.topLevelItem(0),
                                                                    QTreeWidgetItem) and self.tree.topLevelItem(
                        0).childCount() > 0:
                    # We were showing groups before, so refresh group view
                    self.populate_tree_with_groups(self.duplicate_groups)
                    self.status_label.setText(f"Updated {len(self.duplicate_groups)} duplicate group(s).")
                else:
                    # Fall back to file list if no groups exist
                    self.populate_tree_with_files(remaining_files)
                    self.status_label.setText(f"{len(remaining_files)} files remaining.")

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete files:\n{e}")

    def create_menu(self):
        menubar = self.menuBar()

        # === File Menu ===
        file_menu = menubar.addMenu("File")

        self.save_action = file_menu.addAction("Save Results")
        self.save_action.triggered.connect(self.save_results)
        self.actions_to_disable.append(self.save_action)

        self.load_action = file_menu.addAction("Load Results")
        self.load_action.triggered.connect(self.load_results)
        self.actions_to_disable.append(self.load_action)

        self.keep_one_action = file_menu.addAction("Keep One File Per Group")
        self.keep_one_action.triggered.connect(self.keep_one_file_per_group)
        self.actions_to_disable.append(self.keep_one_action)

        scan_menu = menubar.addMenu("Scan")
        self.start_action = scan_menu.addAction("Start Scan")
        self.start_action.triggered.connect(self.start_scan)
        self.actions_to_disable.append(self.start_action)

        prefs_action = scan_menu.addAction("Preferences...")
        prefs_action.triggered.connect(self.show_preferences)
        self.actions_to_disable.append(prefs_action)

        self.stop_action = scan_menu.addAction("Stop Scan")
        self.stop_action.triggered.connect(self.stop_scan)
        # Stop action will be managed separately – not disabled initially

        look_for_menu = menubar.addMenu("Look For")
        self.find_duplicates_action = look_for_menu.addAction("Duplicates")
        self.find_duplicates_action.triggered.connect(self.show_duplicates)
        self.actions_to_disable.append(self.find_duplicates_action)

        self.find_similar_pictures_action = look_for_menu.addAction("Similar Pictures (SLOW)")
        self.find_similar_pictures_action.triggered.connect(self.find_similar_pictures)
        self.actions_to_disable.append(self.find_similar_pictures_action)

        help_menu = menubar.addMenu("Help")
        self.about_action = help_menu.addAction("About")
        self.about_action.triggered.connect(self.show_about)
        self.actions_to_disable.append(self.about_action)

        about_me_action = help_menu.addAction("Contact")
        about_me_action.triggered.connect(self.show_about_me)
        self.actions_to_disable.append(about_me_action)

        # Add all actions to disable list
        self.actions_to_disable = [
            self.save_action,
            self.load_action,
            self.start_action,
            self.find_duplicates_action,
            self.find_similar_pictures_action,
            prefs_action,
        ]

    def disable_ui(self):
        """Disable most UI elements during background tasks"""
        for action in self.actions_to_disable:
            action.setEnabled(False)
        self.stop_action.setEnabled(True)

    def enable_ui(self):
        """Re-enable UI elements after task completes"""
        for action in self.actions_to_disable:
            action.setEnabled(True)
        self.stop_action.setEnabled(False)

    def check_default_directory(self):
        default_dir = self.settings.value("default_directory", "")
        self.start_action.setEnabled(os.path.isdir(default_dir))

    def save_results(self):
        if not self.file_collection and not self.duplicate_groups:
            QMessageBox.information(self, "Nothing to Save", "No files or groups found. Run 'Start Scan' first.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Results", "results.json", "JSON Files (*.json)"
        )
        if not file_path:
            return

        try:
            result_data = {
                "root_dir": self.app.root_dir if self.app else "",
                "files": [f.to_dict() for f in self.file_collection.files] if self.file_collection else [],
                "groups": [g.to_dict() for g in self.duplicate_groups]
            }

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(result_data, f, ensure_ascii=False, indent=4)

            self.status_label.setText(f"Results saved to {os.path.basename(file_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save results:\n{e}")

    def load_results(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Results", "", "JSON Files (*.json)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Clear current state
            self.file_collection = None
            self.duplicate_groups = []
            self.tree.clear()

            # Restore root directory
            root_dir = data.get("root_dir", "")
            if root_dir and os.path.isdir(root_dir):
                self.settings.setValue("default_directory", root_dir)
                self.update_scan_info()
                self.check_default_directory()
            else:
                QMessageBox.warning(self, "Invalid Directory", f"Root directory not found: {root_dir}")

            # Restore files
            loaded_files = [File.from_dict(fd) for fd in data.get("files", [])]
            if loaded_files:
                self.file_collection = FileCollection(loaded_files)
                self.populate_tree_with_files(loaded_files)
                self.status_label.setText(f"Loaded {len(loaded_files)} files")

            # Restore groups
            if "groups" in data:
                self.duplicate_groups = [DuplicateGroup.from_dict(gd) for gd in data["groups"]]
                if self.duplicate_groups:
                    self.populate_tree_with_groups(self.duplicate_groups)
                    self.status_label.setText(f"Loaded {len(self.duplicate_groups)} duplicate group(s)")

            # Re-init app with directory from first file (if available)
            if loaded_files:
                default_dir = os.path.dirname(loaded_files[0].path)
                self.app = FileDeduplicateApp(root_dir=default_dir)
                self.app.files = loaded_files

            self.status_label.setText(f"Results loaded from {os.path.basename(file_path)}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load results:\n{e}")

    def update_scan_info_after_load(self):
        min_size_bytes = 0
        max_size_bytes = 0
        ext_text = ".jpg"

        def format_size(val):
            return "not set" if val <= 0 else human_readable(val)

        self.path_label.setText("📁 Path to Scan: (loaded from file)")
        self.min_size_label.setText(f"📏 Min Size: {format_size(min_size_bytes)}")
        self.max_size_label.setText(f"📏 Max Size: {format_size(max_size_bytes)}")
        self.ext_label.setText(f"📎 Extensions: {ext_text}")


    def show_preferences(self):
        dialog = PreferencesDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.update_scan_info()
            self.check_default_directory()
            self.status_label.setText("Preferences updated.")

    def update_scan_info(self):
        settings = QSettings("MyCompany", "FileDeduplicator")
        default_dir = settings.value("default_directory", "Not selected")
        min_size_bytes = int(settings.value("min_size", 102400))  # 100 KB
        max_size_bytes = int(settings.value("max_size", 15728640))  # 15 MB
        extensions = settings.value("extensions", ".jpg,.png").split(",")
        extensions = [e.strip() for e in extensions if e.strip()]

        def format_size(val):
            return "not set" if val <= 0 else human_readable(val)

        self.path_label.setText(f"📁 Path to Scan: {default_dir}")
        self.fav_dir = settings.value("favourite_directory", "")
        self.min_size_label.setText(f"📏 Min Size: {format_size(min_size_bytes)}")
        self.max_size_label.setText(f"📏 Max Size: {format_size(max_size_bytes)}")
        self.ext_label.setText(f"📎 Extensions: {', '.join(extensions)}")

    def keep_one_file_per_group(self):
        if not self.duplicate_groups:
            QMessageBox.information(self, "No Groups", "No duplicate groups found.")
            return

        reply = QMessageBox.question(
            self,
            'Confirm Operation',
            f"Are you sure you want to keep only one file per group and move the rest to trash? ({len(self.duplicate_groups)} groups)",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        try:
            # Collect all files to delete
            files_to_delete = []
            for group in self.duplicate_groups:
                # Keep the first file (already sorted: original comes first)
                files_to_delete.extend(group.files[1:])  # All but the first

            paths_to_delete = [f.path for f in files_to_delete]
            if not paths_to_delete:
                self.status_label.setText("Nothing to delete – every group has only one file.")
                return

            FileService.move_multiple_to_trash(paths_to_delete)
            self.status_label.setText(f"Moved {len(paths_to_delete)} files to trash.")

            # Update file collection
            remaining_files = [f for f in self.file_collection.files if f.path not in paths_to_delete]
            self.file_collection = FileCollection(remaining_files)

            # Update groups to contain only kept files
            updated_groups = []
            for group in self.duplicate_groups:
                kept_file = group.files[0]
                group.files = [kept_file]
                updated_groups.append(group)

            self.duplicate_groups = updated_groups
            self.populate_tree_with_groups(updated_groups)
            self.status_label.setText(f"Kept {len(updated_groups)} files – one per group.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to process files:\n{e}")


    def start_scan(self):
        if hasattr(self, 'worker') and self.worker.isRunning():
            return

        self.disable_ui()
        settings = QSettings("MyCompany", "FileDeduplicator")
        default_dir = settings.value("default_directory", ".")
        min_size = int(settings.value("min_size", 0)) or None
        max_size = int(settings.value("max_size", 0)) or None
        ext_text = settings.value("extensions", ".jpg,.png")
        extensions = [e.strip() for e in ext_text.split(",") if e.strip()]

        if not os.path.isdir(default_dir):
            QMessageBox.critical(self, "Error", f"Directory does not exist: {default_dir}")
            self.enable_ui()
            return

        self.status_label.setText(f"Starting scan in: {default_dir}")
        self.app = FileDeduplicateApp(root_dir=default_dir)

        self.worker = Worker(
            self.app.scan_directory,
            min_size=min_size,
            max_size=max_size,
            extensions=extensions,
            stopped_flag=lambda: self.worker.stopped_flag() if self.worker else False
        )

        self.worker.finished.connect(lambda result: self.on_scan_complete(result))
        self.worker.finished.connect(self.enable_ui)  # ← Enable UI when done
        self.worker.error_occurred.connect(self.enable_ui)  # ← Also enable on error
        self.worker.error_occurred.connect(lambda msg: QMessageBox.critical(self, "Error", msg))
        self.worker.start()

    def on_scan_complete(self, file_collection):
        self.file_collection = file_collection
        self.status_label.setText(f"Found {len(file_collection.files)} files.")
        self.populate_tree_with_files(file_collection.files)

        if self.app:
            self.app.files = file_collection.files

    def populate_tree_with_files(self, files):
        self.tree.clear()
        for idx, file in enumerate(files, 1):
            item = QTreeWidgetItem(self.tree)
            item.setText(0, f"{idx}. {os.path.basename(file.path)} ({human_readable(file.size)})")
            item.setToolTip(0, file.path)

    def populate_tree_with_groups(self, groups):
        self.tree.clear()
        for idx, group in enumerate(groups, 1):
            group_item = QTreeWidgetItem(self.tree)
            group_item.setText(0, f"📁 Group {idx} ({len(group.files)} files)")

            for file in group.files:
                label = f"{os.path.basename(file.path)} ({human_readable(file.size)})"
                if self.is_in_favourite_path(file.path):
                    label += " ✅ (Original)"
                file_item = QTreeWidgetItem(group_item)
                file_item.setText(0, label)
                file_item.setToolTip(0, file.path)


    def show_duplicates(self, checked=False):
        if not self.file_collection:
            self.status_label.setText("No files scanned yet. Run 'Start Scan' first.")
            return

        if self.app is None:
            QMessageBox.critical(self, "Error", "File app instance is not initialized. Please scan files first.")
            return

        self.disable_ui()
        self.status_label.setText("Finding duplicates...")
        self.worker = Worker(self.app.find_duplicates)
        self.worker.finished.connect(self.on_analysis_complete)
        self.worker.finished.connect(self.enable_ui)
        self.worker.error_occurred.connect(self.enable_ui)
        self.worker.error_occurred.connect(lambda msg: QMessageBox.critical(self, "Error", msg))
        self.worker.start()

    def find_similar_pictures(self, checked=False):
        if not self.file_collection:
            self.status_label.setText("No files scanned yet. Run 'Start Scan' first.")
            return

        self.disable_ui()
        self.status_label.setText("Finding similar pictures...")

        settings = QSettings("MyCompany", "FileDeduplicator")
        threshold = int(settings.value("image_threshold", "5"))

        self.worker = Worker(
            self.app.find_similar_images,
            files=self.file_collection.files,
            threshold=threshold,
            stopped_flag=lambda: self.worker.stopped_flag() if self.worker else False
        )
        self.worker.finished.connect(self.on_analysis_complete)
        self.worker.finished.connect(self.enable_ui)
        self.worker.error_occurred.connect(self.enable_ui)
        self.worker.error_occurred.connect(lambda msg: QMessageBox.critical(self, "Error", msg))
        self.worker.start()

    def is_in_favourite_path(self, file_path):
        fav_dir = self.settings.value("favourite_directory", "")
        if not fav_dir:
            return False
        return os.path.commonpath([fav_dir, file_path]) == fav_dir

    def on_analysis_complete(self, result):
        if isinstance(result, list) and len(result) > 0 and isinstance(result[0], DuplicateGroup):
            # Sort files within each group: those in favourite path come first
            for group in result:
                group.files.sort(
                    key=lambda f: 0 if self.is_in_favourite_path(f.path) else 1
                )
            self.duplicate_groups = result
            self.populate_tree_with_groups(result)
            self.status_label.setText(f"Found {len(result)} groups.")
        else:
            self.status_label.setText("No matches found.")

    def stop_scan(self):
        if hasattr(self, "worker"):
            self.worker.stop()
            self.status_label.setText("Scan stopping...")

    def closeEvent(self, event):
        if hasattr(self, "worker") and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
        self.enable_ui()
        super().closeEvent(event)

    def on_worker_error(self, message):
        self.enable_ui()
        QMessageBox.critical(self, "Error", message)


    def show_about_me(self):
        QMessageBox.about(
            self,
            "About Me",
            """
            <i>Feel free to contact me<br><br>
            <b>Email:</b> initum.x@gmail.com<br><br>
            <b>Location:</b> Belarus / Earth<br><br>
            <i>Thanks for using my app!</i>
            """
        )

    def show_about(self):
        QMessageBox.about(
            self,
            "About File Deduplicator",
            "File Deduplicator v1.0\n\n"
            "A tool for finding duplicate and similar files.\n\n"
            "Built using Python & PyQt5.\n\n"
            "NOTE: Analyzes only the files currently visible in the list.\n"
            "Use 'Start Scan' to load a new file list before searching \n"
            "dupes or similar pics"
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())