"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License
main_window.py
OnlyOne GUI Application
A PySide6-based graphical interface for finding and removing duplicate files.
"""
import os
import logging
from typing import Any, List

from PySide6.QtWidgets import (
    QMainWindow, QFileDialog,
    QDialog, QMessageBox,
    QProgressDialog, QApplication, QListWidgetItem,
)
from PySide6.QtCore import Qt, QSettings, QThreadPool, QTimer
from onlyone.core.models import DeduplicationParams, File
from onlyone.core.sorter import Sorter
from onlyone.core.measurer import bytes_to_human
from onlyone.services.file_service import FileService
from onlyone.services.duplicate_service import DuplicateService
from onlyone.gui.custom_widgets.favourite_dirs_dialog import FavouriteDirsDialog
from onlyone.gui.worker import DeduplicateWorker
from onlyone.gui.main_window_ui import Ui_MainWindow
from onlyone.reporter import format_deletion_preview
from onlyone.gui.custom_widgets.deletion_confirm_dialog import DeletionConfirmDialog
from onlyone import __version__


class SettingsManager:
    """Manages application settings persistence using QSettings."""
    def __init__(self):
        self.settings = QSettings("InitumSoft", "OnlyOne")

    def save_settings(self, key: str, value: Any) -> None:
        """Save a setting value by key."""
        self.settings.setValue(key, value)

    def load_settings(self, key: str, default: Any = None) -> Any:
        """Load a setting value by key with optional default."""
        return self.settings.value(key, default)


class MainWindow(QMainWindow):
    """Main application window using composition with Ui_MainWindow."""

    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Local state storage
        self.files: List = []
        self.duplicate_groups: List = []
        self.favourite_dirs: List[str] = []
        self.excluded_dirs: List[str] = []
        self.settings_manager = SettingsManager()
        self.worker = None  # Holds reference to current worker for cancellation
        self.progress_dialog = None
        self.original_image_preview_size = None

        self.logger = logging.getLogger(__name__)

        self._block_statusbar_from_file_selected = False
        self._statusbar_unlock_timer = QTimer(self)
        self._statusbar_unlock_timer.setSingleShot(True)
        self._statusbar_unlock_timer.timeout.connect(self._unlock_statusbar)


        self._ordering_connected = False
        self.setup_connections()
        # Defer settings restore to ensure UI is fully initialized
        QTimer.singleShot(0, self.restore_settings)

    def setup_connections(self):
        """Connect UI signals to handler methods."""
        self.ui.groups_list.file_selected.connect(self.ui.image_preview.set_file)
        self.ui.groups_list.file_selected.connect(self.on_file_selected_statusbar)
        self.ui.select_dir_button.clicked.connect(self.select_root_folder)
        self.ui.remove_dir_button.clicked.connect(self.remove_selected_folder)
        self.ui.favourite_dirs_button.clicked.connect(self.select_favourite_dirs)
        self.ui.excluded_dirs_button.clicked.connect(self.select_excluded_dirs)
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
        """Handle window resize to maintain splitter proportions."""
        super().resizeEvent(event)
        sizes = self.ui.splitter.sizes()
        total = sum(sizes)
        if total > 0:
            ratio = sizes[0] / total
            new_left = int(self.ui.splitter.width() * ratio)
            new_right = self.ui.splitter.width() - new_left
            self.ui.splitter.setSizes([new_left, new_right])

    def select_root_folder(self):
        """Open folder dialog and add selected path to the list."""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Folder to Scan")
        if dir_path:
            # Check for duplicates in the list
            for i in range(self.ui.root_dir_list.count()):
                if self.ui.root_dir_list.item(i).text() == dir_path:
                    QMessageBox.information(self, "Info", "This folder is already in the list")
                    return

            # Remove placeholder item if it exists (disabled item used for empty state)
            if self.ui.root_dir_list.count() > 0:
                first_item = self.ui.root_dir_list.item(0)
                if first_item and not (first_item.flags() & Qt.ItemFlag.ItemIsEnabled):
                    self.ui.root_dir_list.takeItem(0)

            self.ui.root_dir_list.addItem(dir_path)

    def remove_selected_folder(self):
        """Remove selected folder(s) from the scan list."""
        selected_items = self.ui.root_dir_list.selectedItems()
        if not selected_items:
            # If nothing selected, remove the current row as fallback
            current_row = self.ui.root_dir_list.currentRow()
            if current_row >= 0:
                self.ui.root_dir_list.takeItem(current_row)
            return

        for item in selected_items:
            row = self.ui.root_dir_list.row(item)
            if row >= 0:
                self.ui.root_dir_list.takeItem(row)

    def select_favourite_dirs(self):
        """Open dialog to manage priority (favourite) directories."""
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
                f"Priority Folders Updated: {len(self.favourite_dirs)}"
            )

    def select_excluded_dirs(self):
        """Open dialog to manage excluded directories."""
        from onlyone.gui.custom_widgets.excluded_dirs_dialog import ExcludedDirsDialog
        dialog = ExcludedDirsDialog(self, self.excluded_dirs)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.excluded_dirs = dialog.get_selected_dirs()
            self.ui.excluded_list_widget.clear()
            for path in self.excluded_dirs:
                self.ui.excluded_list_widget.addItem(path)
            QMessageBox.information(
                self,
                "Success",
                f"Excluded Folders Updated: {len(self.excluded_dirs)}"
            )

    def keep_one_file_per_group(self):
        """Keep one file per duplicate group and move the rest to trash."""
        if not self.duplicate_groups:
            QMessageBox.information(self, "Information", "No duplicate groups found")
            return

        files_to_delete, updated_groups = DuplicateService.keep_only_one_file_per_group(self.duplicate_groups)
        if not files_to_delete:
            QMessageBox.information(self, "Information", "Nothing to delete")
            return

        space_saved = sum(f.size for g in self.duplicate_groups for f in g.files if f.path in files_to_delete)
        preview_text = format_deletion_preview(self.duplicate_groups, files_to_delete, space_saved)
        dialog = DeletionConfirmDialog(
            parent=self,
            files_count=len(files_to_delete),
            space_saved=bytes_to_human(space_saved),
            preview_text=preview_text
        )

        reply = dialog.exec()
        if reply != QDialog.DialogCode.Accepted:
            return

        self.handle_delete_files(files_to_delete)

    def handle_delete_files(self, file_paths):
        """Execute file deletion with progress tracking and error handling."""
        if not file_paths:
            self.ui.statusbar.showMessage("Nothing to delete", 3000)
            return

        self._block_statusbar_from_file_selected = True

        file_sizes = {}
        for group in self.duplicate_groups:
            for f in group.files:
                file_sizes[f.path] = f.size

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

                    file_size = file_sizes.get(path, 0)
                    self._log_file_deletion(path, file_size)

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


            if failed_files:
                # Show first 5 errors + count of remaining failures
                error_list = "\n".join([
                    f"• {os.path.basename(path)}: {error.split(':')[-1].strip()}"
                    for path, error in failed_files[:5]
                ])
                if len(failed_files) > 5:
                    error_list += f"\n• ...and {len(failed_files) - 5} more files"

                msg = f"⚠️ Could not delete {len(failed_files)} file(s):\n{error_list}"
                if removed_group_count > 0:
                    msg += f"\n{removed_group_count} groups removed successfully."

                QMessageBox.warning(
                    self,
                    "Partial Success",
                    msg
                )
            else:
                self.ui.statusbar.clearMessage()
                file_names = [os.path.basename(path) for path in successful_files[:3]]
                status_msg = f"✅ Deleted {deleted_count} file: {', '.join(file_names)}. " \
                    if len(successful_files) <= 3 \
                    else f"Deleted {deleted_count} files: {', '.join(file_names)} and {deleted_count - 3} more."

                if removed_group_count > 0:
                    status_msg += f" Removed {removed_group_count} group."

                self.ui.statusbar.showMessage(status_msg)
            self._statusbar_unlock_timer.start(500)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error occurred:\n{e}")
            self._statusbar_unlock_timer.start(500)
        finally:
            if self.progress_dialog:
                self.progress_dialog.close()
                self.progress_dialog = None

        self._statusbar_unlock_timer.start(500)

    def _unlock_statusbar(self):
        """Unblock statusbar."""
        self._block_statusbar_from_file_selected = False

    def show_about_dialog(self):
        """Display application information dialog."""
        QMessageBox.about(
            self,
            "About",
            f'''
            <b>OnlyOne v{__version__}</b><br>
            A tool to find and remove duplicate files.<br><br>
            
            Check <a href="https://github.com/initumX/onlyone">OnlyOne GitHub</a> for help<br><br>
            Leave a star on the GitHub page if you like this app<br><br>
            
            © Copyright (c) 2026 initumX (initum.x@gmail.com)<br><br>
            License: MIT License<br>
            '''
        )

    def _log_file_deletion(self, file_path: str, file_size: int = 0) -> None:
        """Log file deletion."""
        try:
            from onlyone.core.measurer import bytes_to_human
            size_human = bytes_to_human(file_size)
            self.logger.info(f"DELETED | {file_path} | {size_human}")
        except (ValueError, OSError) as e:
            self.logger.debug(f"Failed to log deletion of {file_path}: {e}", exc_info=True)
        except Exception as e:
            self.logger.warning(
                f"Unexpected error logging deletion of {file_path}: {type(e).__name__}: {e}",
                exc_info=True
            )


    def _cleanup_progress_dialog(self):
        """
        Safely closes, disconnects, and schedules deletion of the progress dialog.
        Prevents race conditions and visual artifacts.
        """
        if not hasattr(self, 'progress_dialog') or self.progress_dialog is None:
            return

        dialog = self.progress_dialog
        self.progress_dialog = None  # Reset immediately to prevent re-entrancy

        # Safely disconnect dialog signals
        try:
            dialog.canceled.disconnect()
        except (RuntimeError, TypeError):
            pass

        # Safely disconnect worker signals
        if hasattr(self, 'worker') and self.worker:
            try:
                self.worker.signals.progress.disconnect()
                self.worker.signals.finished.disconnect()
                self.worker.signals.error.disconnect()
            except (RuntimeError, TypeError):
                pass

        # Safely close and delete dialog
        try:
            dialog.close()
            dialog.deleteLater()
        except (RuntimeError, AttributeError):
            pass

    def _collect_root_dirs(self) -> List[str]:
        """Collect all root directories from the UI list widget."""
        root_dirs = []
        for i in range(self.ui.root_dir_list.count()):
            item = self.ui.root_dir_list.item(i)
            if item and item.flags() & Qt.ItemFlag.ItemIsEnabled:
                path = item.text().strip()
                if path:
                    root_dirs.append(path)
        return root_dirs

    def start_deduplication(self):
        """Start the deduplication process with current UI settings."""
        # Collect all root directories from the list widget
        root_dirs = self._collect_root_dirs()
        if not root_dirs:
            QMessageBox.warning(self, "Input Error", "Please, select at least one folder to scan!")
            return

        # Cancel existing worker if any
        if self.worker:
            self.worker.stop()
            self.worker = None

        # Ensure previous dialog is cleaned up
        self._cleanup_progress_dialog()

        # Parse size filters
        min_size_value = self.ui.min_size_spin.value()
        min_unit = self.ui.min_unit_combo.currentText()
        max_size_value = self.ui.max_size_spin.value()
        max_unit = self.ui.max_unit_combo.currentText()
        min_size_str = f"{min_size_value}{min_unit}"
        max_size_str = f"{max_size_value}{max_unit}"

        extensions = self.ui.extension_filter_input.text().split()

        # Get boost, mode and sort order from UI controls
        boost_mode = self.ui.boost_combo.currentData()
        dedupe_mode = self.ui.dedupe_mode_combo.currentData()
        sort_order = self.ui.ordering_combo.currentData()

        # Create unified parameters object with multiple root directories
        try:
            params = DeduplicationParams.from_human_readable(
                root_dirs=root_dirs,
                min_size_str=min_size_str,
                max_size_str=max_size_str,
                extensions=extensions,
                favourite_dirs=self.favourite_dirs,
                excluded_dirs=self.excluded_dirs,
                mode=dedupe_mode,
                sort_order=sort_order,
                boost=boost_mode
            )
        except ValueError as e:
            QMessageBox.critical(
                self,
                "Parameter Error",
                f"{str(e)}"
            )
            return

        # Setup progress dialog
        self.progress_dialog = QProgressDialog(
            "Scanning...",
            "Cancel",
            0, 100, self
        )
        self.progress_dialog.setMinimumDuration(1000)
        self.progress_dialog.setWindowTitle("Processing")
        self.progress_dialog.setAutoReset(False)
        self.progress_dialog.show()

        # Connect cancel action
        self.progress_dialog.canceled.connect(self._cancel_worker)

        # Launch worker via thread pool
        self.worker = DeduplicateWorker(params)
        self.worker.signals.progress.connect(self.update_progress)
        self.worker.signals.finished.connect(self.on_deduplicate_finished)
        self.worker.signals.error.connect(self.on_deduplicate_error)
        QThreadPool.globalInstance().start(self.worker)

    def _cancel_worker(self):
        """Handles user cancellation request."""
        if self.worker:
            self.worker.stop()

        # Close dialog immediately for responsive UI
        self._cleanup_progress_dialog()

    def update_progress(self, stage, current, total):
        """Updates progress dialog safely."""
        if not hasattr(self, 'progress_dialog') or self.progress_dialog is None:
            return

        try:
            if total is not None and total > 0:
                percent = int((current / total) * 100)
                self.progress_dialog.setValue(percent)
                self.progress_dialog.setLabelText(f"{stage}: {current}/{total}")
            else:
                fake_percent = min(int(current / 5000), 100)
                self.progress_dialog.setValue(fake_percent)
                self.progress_dialog.setLabelText(f"{stage}: {current} files processed...")
        except (TypeError, RuntimeError, AttributeError):
            self._cleanup_progress_dialog()

    def on_deduplicate_finished(self, duplicate_groups, stats):
        """Handles successful completion of the worker."""
        # Cleanup UI first
        self._cleanup_progress_dialog()

        # Reset worker reference (worker auto-deletes itself)
        self.worker = None

        # Process results
        self.duplicate_groups = duplicate_groups
        self.on_ordering_changed()

        # Show statistics AFTER event loop processes dialog cleanup
        def show_stats():
            stats_text = stats.print_summary()
            stats_box = QMessageBox(self)
            stats_box.setWindowTitle("Deduplication Statistics")
            stats_box.setText(stats_text)
            stats_box.setIcon(QMessageBox.Icon.Information)
            stats_box.exec()

        QTimer.singleShot(0, show_stats)

    def on_deduplicate_error(self, error_message):
        """Handles error completion of the worker."""
        # Cleanup UI first
        self._cleanup_progress_dialog()

        # Reset worker reference
        self.worker = None

        QMessageBox.critical(
            self,
            "Error",
            f"Error occurred:\n{error_message}"
        )

    def closeEvent(self, event):
        """Handles application close event."""
        # Request cancellation of running worker
        if hasattr(self, 'worker') and self.worker:
            self.worker.stop()
            self.worker = None

        # Safely cleanup progress dialog (handles already-None case)
        self._cleanup_progress_dialog()

        self.save_settings()
        super().closeEvent(event)

    def on_file_selected_statusbar(self, file: File):
        """Updates file selection status bar."""
        if self._block_statusbar_from_file_selected:
            return
        if file and hasattr(file, 'path') and file.path:
            self.ui.statusbar.showMessage(file.path)

    def save_settings(self):
        """Persist current UI state to settings."""
        # Save root directories as a list
        root_dirs = self._collect_root_dirs()
        self.settings_manager.save_settings("root_dirs", root_dirs)

        self.settings_manager.save_settings("min_size", self.ui.min_size_spin.value())
        self.settings_manager.save_settings("max_size", self.ui.max_size_spin.value())
        self.settings_manager.save_settings("min_unit_index", self.ui.min_unit_combo.currentIndex())
        self.settings_manager.save_settings("max_unit_index", self.ui.max_unit_combo.currentIndex())
        self.settings_manager.save_settings("boost_mode", self.ui.boost_combo.currentIndex())
        self.settings_manager.save_settings("dedupe_mode", self.ui.dedupe_mode_combo.currentIndex())
        self.settings_manager.save_settings("extensions", self.ui.extension_filter_input.text())
        self.settings_manager.save_settings("splitter_sizes", list(self.ui.splitter.sizes()))
        self.settings_manager.save_settings("favourite_dirs", self.favourite_dirs)
        self.settings_manager.save_settings("excluded_dirs", self.excluded_dirs)
        self.settings_manager.save_settings("ordering_mode", self.ui.ordering_combo.currentIndex())

    def restore_settings(self):
        """Restore UI state from persisted settings with migration support."""
        # Load root directories with migration from old single 'root_dir' setting
        saved_dirs = self.settings_manager.load_settings("root_dirs", None)

        # Migration: if new format doesn't exist, try old format
        if saved_dirs is None:
            old_dir = self.settings_manager.load_settings("root_dir", "")
            if old_dir and isinstance(old_dir, str) and old_dir.strip():
                saved_dirs = [old_dir.strip()]
            else:
                saved_dirs = []

        # Handle different possible types from QSettings
        if isinstance(saved_dirs, str):
            # Might be serialized as semicolon-separated string
            saved_dirs = [d.strip() for d in saved_dirs.split(";") if d.strip()]
        elif not isinstance(saved_dirs, list):
            saved_dirs = []

        # Populate the list widget
        self.ui.root_dir_list.clear()
        if saved_dirs:
            for path in saved_dirs:
                self.ui.root_dir_list.addItem(path)
        else:
            # Add disabled placeholder item for empty state
            placeholder = QListWidgetItem("No folders selected — click 'Add Folder' to begin")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.ui.root_dir_list.addItem(placeholder)

        self.ui.min_size_spin.setValue(int(self.settings_manager.load_settings("min_size", 100)))
        self.ui.max_size_spin.setValue(int(self.settings_manager.load_settings("max_size", 100)))
        self.ui.min_unit_combo.setCurrentIndex(int(self.settings_manager.load_settings("min_unit_index", 0)))
        self.ui.max_unit_combo.setCurrentIndex(int(self.settings_manager.load_settings("max_unit_index", 1)))
        self.ui.boost_combo.setCurrentIndex(int(self.settings_manager.load_settings("boost_mode", 0)))
        self.ui.dedupe_mode_combo.setCurrentIndex(int(self.settings_manager.load_settings("dedupe_mode", 1)))
        self.ui.extension_filter_input.setText(self.settings_manager.load_settings("extensions", ""))

        splitter_sizes = self.settings_manager.load_settings("splitter_sizes", None)
        if splitter_sizes and isinstance(splitter_sizes, (list, tuple)):
            self.ui.splitter.setSizes([int(x) for x in splitter_sizes])
        else:
            self.ui.splitter.setSizes([400, 600])

        # Restore favourite directories
        saved_fav = self.settings_manager.load_settings("favourite_dirs", [])
        if isinstance(saved_fav, str):
            saved_fav = [d.strip() for d in saved_fav.split(";") if d.strip()]
        elif not isinstance(saved_fav, list):
            saved_fav = []
        self.favourite_dirs = saved_fav
        self.ui.favourite_list_widget.clear()
        for path in self.favourite_dirs:
            self.ui.favourite_list_widget.addItem(path)

        # Restore excluded directories
        saved_excl = self.settings_manager.load_settings("excluded_dirs", [])
        if isinstance(saved_excl, str):
            saved_excl = [d.strip() for d in saved_excl.split(";") if d.strip()]
        elif not isinstance(saved_excl, list):
            saved_excl = []
        self.excluded_dirs = saved_excl
        self.ui.excluded_list_widget.clear()
        for path in self.excluded_dirs:
            self.ui.excluded_list_widget.addItem(path)

        # Restore ordering mode
        ordering_index = int(self.settings_manager.load_settings("ordering_mode", 0))
        self.ui.ordering_combo.setCurrentIndex(ordering_index)
        self.on_ordering_changed()