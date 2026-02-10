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
from typing import Any
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
        self.favorite_dirs = []
        self.settings_manager = SettingsManager()
        self.worker_thread = None
        self.progress_dialog = None
        self.original_image_preview_size = None

        self.restore_settings()
        self.setup_connections()

    def setup_connections(self):
        self.ui.groups_list.file_selected.connect(self.ui.image_preview.set_file)
        self.ui.select_dir_button.clicked.connect(self.select_root_folder)
        self.ui.favorite_dirs_button.clicked.connect(self.select_favorite_dirs)
        self.ui.find_duplicates_button.clicked.connect(self.start_deduplication)
        self.ui.keep_one_button.clicked.connect(self.keep_one_file_per_group)
        self.ui.groups_list.delete_requested.connect(self.handle_delete_files)
        self.ui.about_button.clicked.connect(self.show_about_dialog)

        if not hasattr(self, '_ordering_connected'):
            self.ui.ordering_combo.currentIndexChanged.connect(self.on_ordering_changed)
            self._ordering_connected = True

    def on_ordering_changed(self):
        """Re-sort all duplicate groups when ordering mode changes."""
        if not self.duplicate_groups:
            return

        order_mode = self.ui.ordering_combo.currentData()
        reverse = order_mode == "NEWEST_FIRST"

        for group in self.duplicate_groups:
            group.files.sort(
                key=lambda f: (not f.is_from_fav_dir, f.creation_time or 0),
                reverse=reverse
            )

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
        dir_path = QFileDialog.getExistingDirectory(self, TEXTS["dialog_select_root_title"])
        if dir_path:
            self.ui.root_dir_input.setText(dir_path)

    def select_favorite_dirs(self):
        dialog = FavoriteDirsDialog(self, self.favorite_dirs)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.favorite_dirs = dialog.get_selected_dirs()
            self.ui.favorite_list_widget.clear()
            for path in self.favorite_dirs:
                self.ui.favorite_list_widget.addItem(path)

            if self.files:
                DuplicateService.update_favorite_status(self.files, self.favorite_dirs)
                for group in self.duplicate_groups:
                    group.files.sort(key=lambda f: not f.is_from_fav_dir)
                self.ui.groups_list.set_groups(self.duplicate_groups)

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

            self.files = DuplicateService.remove_files_from_file_list(self.files, file_paths)
            updated_groups = DuplicateService.remove_files_from_groups(self.duplicate_groups, file_paths)
            removed_group_count = len(self.duplicate_groups) - len(updated_groups)

            self.duplicate_groups = updated_groups
            self.ui.groups_list.set_groups(updated_groups)

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
        root_dir = self.ui.root_dir_input.text().strip()
        if not root_dir:
            QMessageBox.warning(self, "Input Error", TEXTS["error_please_select_root"])
            return

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
            QMessageBox.warning(self, "Input Error", f"{TEXTS['error_invalid_size_format']}: {e}")
            return

        extensions = [
            ext.strip() for ext in self.ui.extension_filter_input.text().split(",")
            if ext.strip()
        ]
        extensions = [ext if ext.startswith(".") else f".{ext}" for ext in extensions]

        mode_key = self.ui.dedupe_mode_combo.currentData()
        dedupe_mode = DeduplicationMode[mode_key]
        sort_order = SortOrder.NEWEST_FIRST if self.ui.ordering_combo.currentData() == "NEWEST_FIRST" else SortOrder.OLDEST_FIRST

        if self.worker_thread:
            self.worker_thread.stop()
            self.worker_thread.wait()
            self.worker_thread.deleteLater()
            self.worker_thread = None

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

        params = DeduplicationParams(
            root_dir=root_dir,
            min_size_bytes=min_size,
            max_size_bytes=max_size,
            extensions=extensions,
            favorite_dirs=self.favorite_dirs,
            mode=dedupe_mode,
            sort_order=sort_order
        )

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

        self.duplicate_groups = duplicate_groups
        self.on_ordering_changed()

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
        self.settings_manager.save_settings("root_dir", self.ui.root_dir_input.text())
        self.settings_manager.save_settings("min_size", self.ui.min_size_spin.value())
        self.settings_manager.save_settings("max_size", self.ui.max_size_spin.value())
        self.settings_manager.save_settings("min_unit_index", self.ui.min_unit_combo.currentIndex())
        self.settings_manager.save_settings("max_unit_index", self.ui.max_unit_combo.currentIndex())
        self.settings_manager.save_settings("dedupe_mode", self.ui.dedupe_mode_combo.currentIndex())
        self.settings_manager.save_settings("extensions", self.ui.extension_filter_input.text())
        self.settings_manager.save_settings("splitter_sizes", list(self.ui.splitter.sizes()))
        self.settings_manager.save_settings("favorite_dirs", self.favorite_dirs)
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

        saved_dirs = self.settings_manager.load_settings("favorite_dirs", [])
        if isinstance(saved_dirs, str):
            saved_dirs = [d.strip() for d in saved_dirs.split(";") if d.strip()]
        elif not isinstance(saved_dirs, list):
            saved_dirs = []
        self.favorite_dirs = saved_dirs
        self.ui.favorite_list_widget.clear()
        for path in self.favorite_dirs:
            self.ui.favorite_list_widget.addItem(path)

        ordering_index = int(self.settings_manager.load_settings("ordering_mode", 0))
        self.ui.ordering_combo.setCurrentIndex(ordering_index)
        self.on_ordering_changed()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())