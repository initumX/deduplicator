"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License
main_window.py
File Deduplicator GUI Application
A PyQt-based graphical interface for finding and removing duplicate files.
"""

from PySide6.QtWidgets import (
    QMainWindow, QFileDialog,
    QDialog, QMessageBox,
    QProgressDialog, QApplication,
)
from PySide6.QtCore import Qt, QSettings
from core.models import DeduplicationMode, DeduplicationParams, SortOrder
from utils.services import FileService, DuplicateService
from custom_widgets.favourite_dirs_dialog import FavoriteDirsDialog
from utils.convert_utils import ConvertUtils
from worker import DeduplicateWorker
import os
import sys
import logging

from main_window_ui import Ui_MainWindow
from texts import TEXTS

logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)


class SettingsManager:
    def __init__(self):
        self.settings = QSettings("MyCompany", "FileDeduplicator")

    def save_settings(self, key: str, value: any):
        self.settings.setValue(key, value)

    def load_settings(self, key: str, default: any = None) -> any:
        return self.settings.value(key, default)


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(TEXTS["window_title"])
        self.resize(900, 600)

        # Local state storage - app is stateless and does not store files/groups internally
        self.files = []
        self.duplicate_groups = []
        self.favorite_dirs = []

        # Initialize app with empty root_dir placeholder (required by current api.py signature)
        self.settings_manager = SettingsManager()
        self.worker_thread = None
        self.progress_dialog = None
        self.original_image_preview_size = None

        self.setupUi(self)
        self.init_ui()
        self.restore_settings()
        self.setup_connections()

    def setup_connections(self):
        self.groups_list.file_selected.connect(self.image_preview.set_file)
        self.select_dir_button.clicked.connect(self.select_root_folder)
        self.favorite_dirs_button.clicked.connect(self.select_favorite_dirs)
        self.find_duplicates_button.clicked.connect(self.start_deduplication)
        self.keep_one_button.clicked.connect(self.keep_one_file_per_group)
        self.groups_list.delete_requested.connect(self.handle_delete_files)
        self.about_button.clicked.connect(self.show_about_dialog)

        if not hasattr(self, '_ordering_connected'):
            self.ordering_combo.currentIndexChanged.connect(self.on_ordering_changed)
            self._ordering_connected = True

    def on_ordering_changed(self):
        """Re-sort all duplicate groups when ordering mode changes."""
        if not self.duplicate_groups:
            return

        order_mode = self.ordering_combo.currentData()
        reverse = order_mode == "NEWEST_FIRST"

        for group in self.duplicate_groups:
            group.files.sort(
                key=lambda f: (not f.is_from_fav_dir, f.creation_time or 0),
                reverse=reverse
            )

        self.groups_list.set_groups(self.duplicate_groups)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'splitter'):
            sizes = self.splitter.sizes()
            total = sum(sizes)
            if total > 0:
                ratio = sizes[0] / total
                new_left = int(self.splitter.width() * ratio)
                new_right = self.splitter.width() - new_left
                self.splitter.setSizes([new_left, new_right])

    def select_root_folder(self):
        dir_path = QFileDialog.getExistingDirectory(self, TEXTS["dialog_select_root_title"])
        if dir_path:
            self.root_dir_input.setText(dir_path)

    def select_favorite_dirs(self):
        dialog = FavoriteDirsDialog(self, self.favorite_dirs)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.favorite_dirs = dialog.get_selected_dirs()
            self.favorite_list_widget.clear()
            for path in self.favorite_dirs:
                self.favorite_list_widget.addItem(path)

            # Update favorite status for already-scanned files
            if self.files:
                DuplicateService.update_favorite_status(self.files, self.favorite_dirs)
                for group in self.duplicate_groups:
                    group.files.sort(key=lambda f: not f.is_from_fav_dir)
                self.groups_list.set_groups(self.duplicate_groups)

            QMessageBox.information(
                self,
                TEXTS["title_success"],
                TEXTS["message_favorite_folders_updated"].format(count=len(self.favorite_dirs))
            )

    def keep_one_file_per_group(self):
        if not self.duplicate_groups:
            QMessageBox.information(self, TEXTS["title_info"], TEXTS["message_no_duplicates_found"])
            return

        files_to_delete, updated_groups = DuplicateService.keep_only_one_file_per_group(self.duplicate_groups)
        if not files_to_delete:
            QMessageBox.information(self, TEXTS["title_info"], TEXTS["message_nothing_to_delete"])
            return

        reply = QMessageBox.question(
            self,
            TEXTS["title_confirm_deletion"],
            TEXTS["text_confirm_deletion"].format(count=len(files_to_delete)),
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
            TEXTS["text_progress_delete"],
            TEXTS["btn_cancel"],
            0, total, self
        )
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setWindowTitle(TEXTS["title_progress_dialog"])
        self.progress_dialog.show()

        try:
            for i, path in enumerate(file_paths):
                FileService.move_to_trash(path)
                self.progress_dialog.setValue(i + 1)
                self.progress_dialog.setLabelText(
                    TEXTS["text_progress_deletion"].format(filename=os.path.basename(path))
                )
                QApplication.processEvents()
                if self.progress_dialog.wasCanceled():
                    raise Exception("Operation was cancelled by the user.")

            # Update local state - app remains stateless
            self.files = DuplicateService.remove_files_from_file_list(self.files, file_paths)
            updated_groups = DuplicateService.remove_files_from_groups(self.duplicate_groups, file_paths)
            removed_group_count = len(self.duplicate_groups) - len(updated_groups)

            self.duplicate_groups = updated_groups
            self.groups_list.set_groups(updated_groups)

            if removed_group_count > 0:
                QMessageBox.information(
                    self,
                    TEXTS["title_removing_groups_from_a_list"],
                    TEXTS["text_removing_groups_from_a_list"].format(group_count=removed_group_count)
                )

            QMessageBox.information(
                self,
                TEXTS["title_success"],
                TEXTS["text_files_moved_to_trash"].format(count=total)
            )
        except Exception as e:
            QMessageBox.critical(self, TEXTS["title_error"], f"{TEXTS['error_occurred']}:\n{e}")
        finally:
            if self.progress_dialog:
                self.progress_dialog.close()
                self.progress_dialog = None

    def show_about_dialog(self):
        QMessageBox.about(self, TEXTS["title_about"], TEXTS["about_text"])

    def start_deduplication(self):
        root_dir = self.root_dir_input.text().strip()
        if not root_dir:
            QMessageBox.warning(self, "Input Error", TEXTS["error_please_select_root"])
            return

        # Parse size filters
        min_size_value = self.min_size_spin.value()
        min_unit = self.min_unit_combo.currentText()
        max_size_value = self.max_size_spin.value()
        max_unit = self.max_unit_combo.currentText()
        min_size_str = f"{min_size_value}{min_unit}"
        max_size_str = f"{max_size_value}{max_unit}"

        try:
            min_size = ConvertUtils.human_to_bytes(min_size_str)
            max_size = ConvertUtils.human_to_bytes(max_size_str)
        except ValueError as e:
            QMessageBox.warning(self, "Input Error", f"{TEXTS['error_invalid_size_format']}: {e}")
            return

        # Parse extensions
        extensions = [
            ext.strip() for ext in self.extension_filter_input.text().split(",")
            if ext.strip()
        ]
        extensions = [ext if ext.startswith(".") else f".{ext}" for ext in extensions]

        # Get mode and sort order from UI controls
        mode_key = self.dedupe_mode_combo.currentData()
        dedupe_mode = DeduplicationMode[mode_key]
        sort_order = SortOrder.NEWEST_FIRST if self.ordering_combo.currentData() == "NEWEST_FIRST" else SortOrder.OLDEST_FIRST

        # Cancel existing worker if any
        if self.worker_thread:
            self.worker_thread.stop()
            self.worker_thread.wait()
            self.worker_thread.deleteLater()
            self.worker_thread = None

        # Setup progress dialog
        self.progress_dialog = QProgressDialog(
            TEXTS["text_progress_scanning"],
            TEXTS["btn_cancel"],
            0, 100, self
        )
        self.progress_dialog.setMinimumDuration(1000)
        self.progress_dialog.setModal(True)
        self.progress_dialog.setWindowTitle(TEXTS["title_processing"])
        self.progress_dialog.setAutoReset(False)
        self.progress_dialog.show()

        def cancel_action():
            if self.worker_thread:
                self.worker_thread.stop()

        self.progress_dialog.canceled.connect(cancel_action)

        # Create unified parameters object - single source of truth for all settings
        params = DeduplicationParams(
            root_dir=root_dir,
            min_size_bytes=min_size,
            max_size_bytes=max_size,
            extensions=extensions,
            favorite_dirs=self.favorite_dirs,
            mode=dedupe_mode,
            sort_order=sort_order
        )

        # Launch worker thread with stateless app and unified parameters
        self.worker_thread = DeduplicateWorker(params)
        self.worker_thread.progress.connect(self.update_progress)
        self.worker_thread.finished.connect(self.on_deduplicate_finished)
        self.worker_thread.error.connect(self.on_deduplicate_error)
        self.worker_thread.start()

    def update_progress(self, stage, current, total):
        if not self.progress_dialog or not self.worker_thread:
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
        if self.progress_dialog:
            self.progress_dialog.deleteLater()
            self.progress_dialog = None

        # Store results in local state
        self.duplicate_groups = duplicate_groups

        # Re-sort groups based on current UI selection
        self.on_ordering_changed()

        # Show statistics dialog
        stats_text = stats.print_summary()
        self.stats_window = QMessageBox(self)
        self.stats_window.setWindowTitle(TEXTS["message_stats_title"])
        self.stats_window.setText(stats_text)
        self.stats_window.setIcon(QMessageBox.Icon.Information)
        self.stats_window.exec()

    def on_deduplicate_error(self, error_message):
        if self.progress_dialog:
            self.progress_dialog.deleteLater()
            self.progress_dialog = None
        QMessageBox.critical(
            self,
            TEXTS["title_error"],
            f"{TEXTS['error_occurred']}:\n{error_message}"
        )

    def closeEvent(self, event):
        if self.worker_thread:
            self.worker_thread.stop()
            if not self.worker_thread.wait(1000):
                self.worker_thread.terminate()
            self.worker_thread.deleteLater()

        if self.progress_dialog:
            self.progress_dialog.deleteLater()

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
        self.settings_manager.save_settings("favorite_dirs", self.favorite_dirs)
        self.settings_manager.save_settings("ordering_mode", self.ordering_combo.currentIndex())

    def restore_settings(self):
        self.root_dir_input.setText(self.settings_manager.load_settings("root_dir", ""))
        self.min_size_spin.setValue(int(self.settings_manager.load_settings("min_size", "100")))
        self.max_size_spin.setValue(int(self.settings_manager.load_settings("max_size", "100")))
        self.min_unit_combo.setCurrentIndex(int(self.settings_manager.load_settings("min_unit_index", "0")))
        self.max_unit_combo.setCurrentIndex(int(self.settings_manager.load_settings("max_unit_index", "1")))
        self.dedupe_mode_combo.setCurrentIndex(int(self.settings_manager.load_settings("dedupe_mode", "1")))
        self.extension_filter_input.setText(self.settings_manager.load_settings("extensions", ""))

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
        self.favorite_dirs = saved_dirs
        self.favorite_list_widget.clear()
        for path in self.favorite_dirs:
            self.favorite_list_widget.addItem(path)

        ordering_index = int(self.settings_manager.load_settings("ordering_mode", 0))
        self.ordering_combo.setCurrentIndex(ordering_index)
        self.on_ordering_changed()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())