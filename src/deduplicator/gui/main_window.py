"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License
main_window.py
File Deduplicator GUI Application
A PyQt-based graphical interface for finding and removing duplicate files.
"""
import os
from typing import Any

from PySide6.QtWidgets import (
    QMainWindow, QFileDialog,
    QDialog, QMessageBox,
    QProgressDialog, QApplication,
)
from PySide6.QtCore import Qt, QSettings, QThreadPool
from deduplicator.core.models import DeduplicationMode, DeduplicationParams
from deduplicator.core.sorter import Sorter
from deduplicator.services.file_service import FileService
from deduplicator.services.duplicate_service import DuplicateService
from deduplicator.gui.custom_widgets.favourite_dirs_dialog import FavouriteDirsDialog
from deduplicator.utils.convert_utils import ConvertUtils
from deduplicator.gui.worker import DeduplicateWorker
from deduplicator.gui.main_window_ui import Ui_MainWindow

class SettingsManager:
    def __init__(self):
        self.settings = QSettings("InitumSoft", "FileDeduplicator")

    def save_settings(self, key: str, value: Any):
        self.settings.setValue(key, value)

    def load_settings(self, key: str, default: Any = None) -> Any:
        return self.settings.value(key, default)

class MainWindow(QMainWindow):
    """Main application window using composition with Ui_MainWindow."""

    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Local state storage
        self.files = []
        self.duplicate_groups = []
        self.favourite_dirs = []
        self.settings_manager = SettingsManager()
        self.worker = None  # Holds reference to current worker for cancellation
        self.progress_dialog = None
        self.original_image_preview_size = None

        self._ordering_connected = False
        self.stats_window = None
        self.restore_settings()
        self.setup_connections()

        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self.restore_settings)

    def setup_connections(self):
        self.ui.groups_list.file_selected.connect(self.ui.image_preview.set_file)
        self.ui.select_dir_button.clicked.connect(self.select_root_folder)
        self.ui.favourite_dirs_button.clicked.connect(self.select_favourite_dirs)
        self.ui.find_duplicates_button.clicked.connect(self.start_deduplication)
        self.ui.keep_one_button.clicked.connect(self.keep_one_file_per_group)
        self.ui.groups_list.delete_requested.connect(self.handle_delete_files)
        self.ui.about_button.clicked.connect(self.show_about_dialog)

        if not self._ordering_connected:
            self.ui.ordering_combo.currentIndexChanged.connect(self.on_ordering_changed)
            self._ordering_connected = True

    def on_ordering_changed(self):
        """Re-sort all duplicate groups when ordering mode changes."""
        sort_order = self.ui.ordering_combo.currentData()
        Sorter.sort_files_inside_groups(self.duplicate_groups, sort_order)
        self.ui.groups_list.set_groups(self.duplicate_groups)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        sizes = self.ui.splitter.sizes()
        total = sum(sizes)
        if total > 0:
            ratio = sizes[0] / total
            new_left = int(self.ui.splitter.width() * ratio)
            new_right = self.ui.splitter.width() - new_left
            self.ui.splitter.setSizes([new_left, new_right])

    def select_root_folder(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Root Folder")
        if dir_path:
            self.ui.root_dir_input.setText(dir_path)

    def select_favourite_dirs(self):
        dialog = FavouriteDirsDialog(self, self.favourite_dirs)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.favourite_dirs = dialog.get_selected_dirs()
            self.ui.favourite_list_widget.clear()
            for path in self.favourite_dirs:
                self.ui.favourite_list_widget.addItem(path)

            if self.files:
                DuplicateService.update_favourite_status(self.files, self.favourite_dirs)
                for group in self.duplicate_groups:
                    group.files.sort(key=lambda f: not f.is_from_fav_dir)
                self.ui.groups_list.set_groups(self.duplicate_groups)

            QMessageBox.information(
                self,
                "Success",
                f"Favourite Folders Updated: {len(self.favourite_dirs)}"
            )

    def keep_one_file_per_group(self):
        if not self.duplicate_groups:
            QMessageBox.information(self, "Information", "No duplicate groups found")
            return

        files_to_delete, updated_groups = DuplicateService.keep_only_one_file_per_group(self.duplicate_groups)
        if not files_to_delete:
            QMessageBox.information(self, "Information", "Nothing to delete")
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
        self.progress_dialog = QProgressDialog(
            "Moving files to trash...",
            "Cancel",
            0, total, self
        )
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setWindowTitle("Deleting files")
        self.progress_dialog.show()

        failed_files = []  # List of (path, error) for files that could not be deleted
        deleted_count = 0

        try:
            for i, path in enumerate(file_paths):
                if self.progress_dialog.wasCanceled():
                    raise Exception("Operation was cancelled by the user.")

                try:
                    FileService.move_to_trash(path)
                    deleted_count += 1
                except Exception as e:
                    # Continue deleting other files even if one fails
                    failed_files.append((path, str(e)))
                    continue

                # Update progress ONLY for successfully deleted files
                self.progress_dialog.setValue(deleted_count)
                self.progress_dialog.setLabelText(
                    f"Deleting: {os.path.basename(path)}"
                )
                QApplication.processEvents()

            # Update file lists ONLY for successfully deleted files
            successful_files = [path for path in file_paths if path not in [f[0] for f in failed_files]]
            self.files = DuplicateService.remove_files_from_file_list(self.files, successful_files)
            updated_groups = DuplicateService.remove_files_from_groups(self.duplicate_groups, successful_files)
            removed_group_count = len(self.duplicate_groups) - len(updated_groups)

            self.duplicate_groups = updated_groups
            self.ui.groups_list.set_groups(updated_groups)

            # Build informative message for the user
            messages = []
            if removed_group_count > 0:
                messages.append(
                    f"{removed_group_count} groups had no duplicates left and were therefore removed from the list"
                )

            if failed_files:
                # Show first 5 errors + count of remaining failures
                error_list = "\n".join([
                    f"• {os.path.basename(path)}: {error.split(':')[-1].strip()}"
                    for path, error in failed_files[:5]
                ])
                if len(failed_files) > 5:
                    error_list += f"\n• ...and {len(failed_files) - 5} more files"

                messages.append(
                    f"⚠️ Could not delete {len(failed_files)} file(s):\n{error_list}\n\n"
                    "These files may be in use, protected by the system, or require administrator privileges."
                )
                title = "Partial Success"
            else:
                messages.append(f"{deleted_count} files moved to trash.")
                title = "Success"

            QMessageBox.information(
                self,
                title,
                "\n\n".join(messages)
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"{"Error occurred"}:\n{e}")
        finally:
            if self.progress_dialog:
                self.progress_dialog.close()
                self.progress_dialog = None

    def show_about_dialog(self):
        QMessageBox.about(
            self,
        "About",
        """
            <b>File Deduplicator</b><br><br>
            Version: 2.2.4<br>A tool to find and remove duplicate files.<br><br><b>
            Features:</b><br><br>
            -Filtering by size and extension<br><br>
            -Using xxhash (very fast)<br><br>
            -Three deduplication modes (fast, normal, full)<br><br>
            -Delete all duplicates with one click (keep one file per group)<br><br>
            -Image preview, context menu, auto-save settings, tooltips<br><br>
            -and much more<br><br>
            © Copyright (c) 2025 initumX (initum.x@gmail.com)<br><br>
            License: MIT License<br>
            """
        )

    def start_deduplication(self):
        root_dir = self.ui.root_dir_input.text().strip()
        if not root_dir:
            QMessageBox.warning(self, "Input Error", "Please, select folder to scan!")
            return

        # Cancel existing worker if any
        if self.worker:
            self.worker.stop()
            self.worker = None

        # Parse size filters
        min_size_value = self.ui.min_size_spin.value()
        min_unit = self.ui.min_unit_combo.currentText()
        max_size_value = self.ui.max_size_spin.value()
        max_unit = self.ui.max_unit_combo.currentText()
        min_size_str = f"{min_size_value}{min_unit}"
        max_size_str = f"{max_size_value}{max_unit}"

        try:
            min_size = ConvertUtils.human_to_bytes(min_size_str)
            max_size = ConvertUtils.human_to_bytes(max_size_str)
        except ValueError as e:
            QMessageBox.warning(self, "Input Error", f"Invalid size format: {e}")
            return

        # Parse extensions
        extensions = [
            ext.strip() for ext in self.ui.extension_filter_input.text().split(",")
            if ext.strip()
        ]
        extensions = [ext if ext.startswith(".") else f".{ext}" for ext in extensions]

        # Get mode and sort order from UI controls
        mode_key = self.ui.dedupe_mode_combo.currentData()
        dedupe_mode = DeduplicationMode[mode_key]
        sort_order = self.ui.ordering_combo.currentData()

        # Setup progress dialog
        self.progress_dialog = QProgressDialog(
            "Scanning...",
            "Cancel",
            0, 100, self
        )
        self.progress_dialog.setMinimumDuration(1000)
        self.progress_dialog.setModal(True)
        self.progress_dialog.setWindowTitle("Processing")
        self.progress_dialog.setAutoReset(False)
        self.progress_dialog.show()

        # Connect cancel action to worker.stop()
        def cancel_action():
            if self.worker:
                self.worker.stop()
                self.worker = None  # Release reference immediately

        self.progress_dialog.canceled.connect(cancel_action)  #

        # Create unified parameters object
        params = DeduplicationParams(
            root_dir=root_dir,
            min_size_bytes=min_size,
            max_size_bytes=max_size,
            extensions=extensions,
            favourite_dirs=self.favourite_dirs,
            mode=dedupe_mode,
            sort_order=sort_order
        )

        # Launch worker via thread pool
        self.worker = DeduplicateWorker(params)
        self.worker.signals.progress.connect(self.update_progress)
        self.worker.signals.finished.connect(self.on_deduplicate_finished)
        self.worker.signals.error.connect(self.on_deduplicate_error)
        QThreadPool.globalInstance().start(self.worker)

    def update_progress(self, stage, current, total):
        if not self.progress_dialog or not self.worker:
            return

        try:
            if total is not None and total > 0:
                percent = int((current / total) * 100)
                self.progress_dialog.setValue(percent)
                self.progress_dialog.setLabelText(f"{stage}: {current}/{total}")
            else:
                fake_percent = min(int(current / 500), 100)
                self.progress_dialog.setValue(fake_percent)
                self.progress_dialog.setLabelText(f"{stage}: {current} files processed...")
        except (TypeError, RuntimeError, AttributeError):
            if self.progress_dialog:
                self.progress_dialog.deleteLater()
                self.progress_dialog = None

    def on_deduplicate_finished(self, duplicate_groups, stats):
        self.worker = None  # Release reference - worker auto-deleted by pool

        if self.progress_dialog:
            self.progress_dialog.deleteLater()
            self.progress_dialog = None

        self.duplicate_groups = duplicate_groups
        self.on_ordering_changed()

        stats_text = stats.print_summary()
        self.stats_window = QMessageBox(self)
        self.stats_window.setWindowTitle("Deduplication Statistics")
        self.stats_window.setText(stats_text)
        self.stats_window.setIcon(QMessageBox.Icon.Information)
        self.stats_window.exec()

    def on_deduplicate_error(self, error_message):
        self.worker = None  # Release reference

        if self.progress_dialog:
            self.progress_dialog.deleteLater()
            self.progress_dialog = None

        QMessageBox.critical(
            self,
            "Error",
            f"{"Error occurred"}:\n{error_message}"
        )

    def closeEvent(self, event):
        # Request cancellation of running worker
        if self.worker:
            self.worker.stop()
            self.worker = None

        if self.progress_dialog:
            self.progress_dialog.deleteLater()

        self.save_settings()
        super().closeEvent(event)

    def save_settings(self):
        self.settings_manager.save_settings("root_dir", self.ui.root_dir_input.text())
        self.settings_manager.save_settings("min_size", self.ui.min_size_spin.value())
        self.settings_manager.save_settings("max_size", self.ui.max_size_spin.value())
        self.settings_manager.save_settings("min_unit_index", self.ui.min_unit_combo.currentIndex())
        self.settings_manager.save_settings("max_unit_index", self.ui.max_unit_combo.currentIndex())
        self.settings_manager.save_settings("dedupe_mode", self.ui.dedupe_mode_combo.currentIndex())
        self.settings_manager.save_settings("extensions", self.ui.extension_filter_input.text())
        self.settings_manager.save_settings("splitter_sizes", list(self.ui.splitter.sizes()))
        self.settings_manager.save_settings("favourite_dirs", self.favourite_dirs)
        self.settings_manager.save_settings("ordering_mode", self.ui.ordering_combo.currentIndex())

    def restore_settings(self):
        self.ui.root_dir_input.setText(self.settings_manager.load_settings("root_dir", ""))
        self.ui.min_size_spin.setValue(int(self.settings_manager.load_settings("min_size", "100")))
        self.ui.max_size_spin.setValue(int(self.settings_manager.load_settings("max_size", "100")))
        self.ui.min_unit_combo.setCurrentIndex(int(self.settings_manager.load_settings("min_unit_index", "0")))
        self.ui.max_unit_combo.setCurrentIndex(int(self.settings_manager.load_settings("max_unit_index", "1")))
        self.ui.dedupe_mode_combo.setCurrentIndex(int(self.settings_manager.load_settings("dedupe_mode", "1")))
        self.ui.extension_filter_input.setText(self.settings_manager.load_settings("extensions", ""))

        splitter_sizes = self.settings_manager.load_settings("splitter_sizes", None)
        if splitter_sizes:
            self.ui.splitter.setSizes([int(x) for x in splitter_sizes])
        else:
            self.ui.splitter.setSizes([400, 600])

        saved_dirs = self.settings_manager.load_settings("favourite_dirs", [])
        if isinstance(saved_dirs, str):
            saved_dirs = [d.strip() for d in saved_dirs.split(";") if d.strip()]
        elif not isinstance(saved_dirs, list):
            saved_dirs = []
        self.favourite_dirs = saved_dirs
        self.ui.favourite_list_widget.clear()
        for path in self.favourite_dirs:
            self.ui.favourite_list_widget.addItem(path)

        ordering_index = int(self.settings_manager.load_settings("ordering_mode", 0))
        self.ui.ordering_combo.setCurrentIndex(ordering_index)
        self.on_ordering_changed()