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
    QSizePolicy
)
from PySide6.QtCore import Qt, QSettings
from core.models import DeduplicationMode
from api import FileDeduplicateApp
from utils.services import FileService
from dialogs import FavoriteDirsDialog
from preview import ImagePreviewLabel
from utils.services import DuplicateService
from utils.size_utils import SizeUtils
from duplicate_groups_list import DuplicateGroupsList
from core.interfaces import TranslatorProtocol
from worker import DeduplicateWorker
import os, sys


class SettingsManager:
    def __init__(self):
        self.settings = QSettings("MyCompany", "FileDeduplicator")

    def save_settings(self, key: str, value: any):
        self.settings.setValue(key, value)

    def load_settings(self, key: str, default: any = None) -> any:
        return self.settings.value(key, default)


class MainWindow(QMainWindow):
    def __init__(self, ui_translator: TranslatorProtocol = None):
        super().__init__()
        self.translator = ui_translator or DictTranslator("en")  # Use injected translator or default
        self.worker_thread = None
        self.setWindowTitle(self.translator.tr("window_title"))
        self.resize(900, 600)
        self.app = FileDeduplicateApp("")
        self.settings_manager = SettingsManager()
        self.settings = QSettings("MyCompany", "FileDeduplicator")
        self.supported_languages = ["en", "ru"]
        #saved_lang = self.settings.value("language", "en")
        self.original_image_preview_size = None

        # Widgets
        self.root_layout = QHBoxLayout()
        self.label_root_folder = QLabel(self.translator.tr("label_root_folder"))
        self.root_layout.addWidget(self.label_root_folder)


        self.root_dir_input = QLineEdit()
        self.select_dir_button = QPushButton("Select Root Folder")
        self.extension_filter_input = QLineEdit()
        self.lang_combo = QComboBox()

        self.filters_group = QGroupBox(self.translator.tr("group_box_filters"))

        self.min_size_layout = QHBoxLayout()
        self.label_min_size = QLabel(self.translator.tr("label_min_size"))
        self.min_size_layout.addWidget(self.label_min_size)
        self.min_size_spin, self.min_unit_combo = self.create_size_input(100)


        self.max_size_layout = QHBoxLayout()
        self.label_max_size = QLabel(self.translator.tr("label_max_size"))
        self.max_size_layout.addWidget(self.label_max_size)
        self.max_size_spin, self.max_unit_combo = self.create_size_input(100)

        self.extension_layout_inside = QHBoxLayout()
        self.label_extensions = QLabel(self.translator.tr("label_extensions"))
        self.extension_layout_inside.addWidget(self.label_extensions)

        self.favorite_group = QGroupBox(self.translator.tr("group_box_favorites"))
        self.favorite_dirs_button = QPushButton("Manage Favorite Folders List")
        self.dedupe_mode_combo = QComboBox()
        self.find_duplicates_button = QPushButton("Find Duplicates")
        self.progress_dialog = None
        self.stats_window = None
        self.keep_one_button = QPushButton("Keep One File Per Group")
        self.about_button = QPushButton("About")
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # QListWidget with scroll
        self.favorite_list_widget = QListWidget()
        self.favorite_list_widget.setContentsMargins(0, 0, 0, 0)
        self.favorite_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)

        # Output widgets
        self.groups_list = DuplicateGroupsList(self)
        self.image_preview = ImagePreviewLabel()

        # Layouts
        self.init_ui()
        self.restore_settings()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        # --- Root Directory Layout ---
        self.root_dir_input.setPlaceholderText(self.translator.tr("select_root_dir"))
        self.root_layout.addWidget(self.root_dir_input)
        self.select_dir_button.setText(self.translator.tr("btn_select_root"))
        self.select_dir_button.clicked.connect(self.select_root_folder)
        self.root_layout.addWidget(self.select_dir_button)

        # --- Filters Group Box ---
        self.filters_group.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # Min Size Layout
        self.min_size_spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.min_unit_combo.setCurrentText("KB")
        self.max_unit_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.min_size_layout.addWidget(self.min_size_spin)
        self.min_size_layout.addWidget(self.min_unit_combo)

        # Max Size Layout
        self.max_size_spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.max_unit_combo.setCurrentText("MB")
        self.max_unit_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.max_size_layout.addWidget(self.max_size_spin)
        self.max_size_layout.addWidget(self.max_unit_combo)

        # Extension filter layout
        self.extension_filter_input.setPlaceholderText(self.translator.tr("placeholder_extensions"))
        self.extension_filter_input.setToolTip(self.translator.tr("tooltip_extensions"))
        self.extension_layout_inside.addWidget(self.extension_filter_input)

        # Vertical layout inside group box
        filters_group_layout = QVBoxLayout()
        filters_group_layout.addLayout(self.min_size_layout)
        filters_group_layout.addLayout(self.max_size_layout)
        filters_group_layout.addLayout(self.extension_layout_inside)
        self.filters_group.setLayout(filters_group_layout)

        # --- End of Filters Group Box ---

        # --- Favorite Folders UI Block ---
        self.filters_group.updateGeometry()
        self.favorite_group.updateGeometry()
        self.favorite_group.setMaximumHeight(self.filters_group.sizeHint().height() + 20)
        self.favorite_group.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        favorite_layout = QVBoxLayout()
        self.favorite_dirs_button.setToolTip(self.translator.tr("tooltip_favorite_dirs"))
        self.favorite_dirs_button.clicked.connect(self.select_favorite_dirs)
        favorite_layout.addWidget(self.favorite_dirs_button)

        self.favorite_list_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.favorite_list_widget.setContentsMargins(0, 0, 0, 0)
        self.favorite_list_widget.setStyleSheet("padding: 0px; margin: 0px;")
        favorite_layout.addWidget(self.favorite_list_widget)
        self.favorite_group.setLayout(favorite_layout)

        # --- Level layout: Size Filter + Favorite Folders ---
        level_layout = QHBoxLayout()
        level_layout.addWidget(self.filters_group)
        level_layout.addWidget(self.favorite_group)
        level_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # --- Unified Control Layout (Buttons and Deduplication Mode) ---
        control_layout = QHBoxLayout()
        self.find_duplicates_button.setText(self.translator.tr("btn_start_deduplication"))
        self.find_duplicates_button.setToolTip(self.translator.tr("tooltip_find_duplicates"))
        self.find_duplicates_button.clicked.connect(self.start_deduplication)
        control_layout.addWidget(self.find_duplicates_button)

        mode_label = QLabel(self.translator.tr("label_dedupe_mode"))
        control_layout.addWidget(mode_label)
        self.dedupe_mode_combo.addItems([mode.value.upper() for mode in DeduplicationMode])
        self.dedupe_mode_combo.setToolTip(self.translator.tr("tooltip_dedupe_mode"))
        control_layout.addWidget(self.dedupe_mode_combo)

        self.keep_one_button.setText(self.translator.tr("btn_keep_one"))
        self.keep_one_button.setToolTip(self.translator.tr("tooltip_delete_duplicates"))
        self.keep_one_button.clicked.connect(self.keep_one_file_per_group)
        control_layout.addWidget(self.keep_one_button)

        self.about_button.setText(self.translator.tr("btn_about"))
        self.about_button.setToolTip(self.translator.tr("tooltip_about"))
        self.about_button.clicked.connect(self.show_about_dialog)
        control_layout.addWidget(self.about_button)

        self.lang_combo.addItems(["English", "Русский"])
        self.lang_combo.currentIndexChanged.connect(self.change_language)
        control_layout.addWidget(self.lang_combo)
        control_layout.addStretch()  # Все элементы слева
        control_layout.setContentsMargins(0, 20, 0, 0)  # top=20

        # --- Splitter for groups list and image preview ---
        self.splitter.addWidget(self.groups_list)
        self.splitter.addWidget(self.image_preview)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        self.splitter.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.groups_list.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        # --- Main Layout Assembly ---
        main_layout = QVBoxLayout()
        main_layout.addLayout(self.root_layout)
        main_layout.addLayout(level_layout)
        main_layout.addLayout(control_layout)
        main_layout.addWidget(self.splitter, stretch=1)
        main_widget.setLayout(main_layout)

        self.groups_list.file_selected.connect(self.image_preview.set_file)
        self.groups_list.delete_requested.connect(self.handle_delete_files)

    @staticmethod
    def create_size_input(default_value=100):
        spin = QSpinBox()
        spin.setRange(0, 1024 * 1024)
        spin.setValue(default_value)
        unit_combo = QComboBox()
        unit_combo.addItems(["KB", "MB", "GB"])
        return spin, unit_combo

    def change_language(self, index):
        lang_code = "en" if index == 0 else "ru"
        self.translator = DictTranslator(lang_code)
        self.update_ui_texts()

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
        dir_path = QFileDialog.getExistingDirectory(self, self.translator.tr("dialog_select_root_title"))
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
            # Update flag
            DuplicateService.update_favorite_status(self.app.files, selected_dirs)
            # Resort original groups
            for group in self.app.duplicate_groups:
                group.files.sort(key=lambda f: not f.is_from_fav_dir)
            # Update groups on list widget
            self.groups_list.set_groups(self.app.duplicate_groups)
            QMessageBox.information(self, self.translator.tr("title_success"), self.translator.tr("message_favorite_folders_updated").format(count=len(selected_dirs)))

    def refresh_duplicate_groups_display(self):
        duplicate_groups = self.app.get_duplicate_groups()
        self.groups_list.set_groups(duplicate_groups)

    def keep_one_file_per_group(self):
        tr = self.translator.tr
        duplicate_groups = self.app.get_duplicate_groups()
        if not duplicate_groups:
            QMessageBox.information(
                self,
                tr("title_nfo"),
                tr("message_no_duplicates_found")
            )
            return
        files_to_delete, updated_groups = DuplicateService.keep_only_one_file_per_group(duplicate_groups)
        if not files_to_delete:
            QMessageBox.information(self, tr("title_nfo"), tr("message_nothing_to_delete"))
            return
        reply = QMessageBox.question(
            self,
            tr("title_confirm_deletion"),
            tr("text_confirm_deletion").format(count=len(files_to_delete)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.handle_delete_files(files_to_delete)

    def handle_delete_files(self, file_paths):
        tr = self.translator.tr
        if not file_paths:
            return
        total = len(file_paths)
        self.progress_dialog = QProgressDialog(
            tr("text_progress_delete"),
            tr("btn_cancel"),
            0, total, self
        )
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setWindowTitle(tr("title_progress_dialog"))
        self.progress_dialog.show()
        try:
            # Move to trash
            for i, path in enumerate(file_paths):
                FileService.move_to_trash(path)
                self.progress_dialog.setValue(i + 1)
                self.progress_dialog.setLabelText(
                    tr("text_progress_deletion").format(filename=os.path.basename(path))
                )
                QApplication.processEvents()  # Обновляем интерфейс
                if self.progress_dialog.wasCanceled():
                    raise Exception("Operation was cancelled by the user.")
            # Refresh
            self.app.files = DuplicateService.remove_files_from_file_list(self.app.files, file_paths)
            updated_groups = DuplicateService.remove_files_from_groups(self.app.duplicate_groups, file_paths)
            removed_group_count = len(self.app.duplicate_groups) - len(updated_groups)
            # Save groups and update UI
            self.app.duplicate_groups = updated_groups
            self.groups_list.set_groups(updated_groups)
            if removed_group_count == 1:
                QMessageBox.information(
                    self,
                    tr("title_removing_group_from_a_list"),
                    tr("text_removing_group_from_a_list")
                )
            elif removed_group_count > 1:
                QMessageBox.information(
                    self,
                    tr("title_removing_groups_from_a_list"),
                    tr("text_removing_groups_from_a_list").format(group_count=removed_group_count)
                )
            QMessageBox.information(
                self,
                tr("title_success"),
                tr("text_files_moved_to_trash").format(count=total)
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to delete files:\n{e}")
        finally:
            self.progress_dialog.close()
            self.progress_dialog = None

    def show_about_dialog(self):
        about_title = self.translator.tr("title_about")
        about_text = self.translator.tr("about_text")
        QMessageBox.about(self, about_title, about_text)

    def start_deduplication(self):
        root_dir = self.root_dir_input.text().strip()
        if not root_dir:
            QMessageBox.warning(self, "Input Error", self.translator.tr("error_please_select_root"))
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
            QMessageBox.warning(self, "Input Error", f"{self.translator.tr('error_invalid_size_format')}: {e}")
            return
        extensions = [
            ext.strip() for ext in self.extension_filter_input.text().split(",")
            if ext.strip()
        ]
        mode_key = self.dedupe_mode_combo.currentData()
        dedupe_mode = DeduplicationMode[mode_key]
        if self.worker_thread:
            self.worker_thread.stop()
            self.worker_thread.wait()
            self.worker_thread = None
        self.progress_dialog = QProgressDialog(self.translator.tr("text_progress_scanning"), self.translator.tr("btn_cancel"), 0, 100, self)
        self.progress_dialog.setModal(True)
        self.progress_dialog.setWindowTitle(self.translator.tr("title_processing"))
        self.progress_dialog.show()

        def cancel_action():
            if self.worker_thread:
                self.worker_thread.stop()
        self.progress_dialog.canceled.connect(cancel_action)
        self.worker_thread = DeduplicateWorker(
            self.app, min_size, max_size, extensions, self.app.favorite_dirs, dedupe_mode
        )
        self.worker_thread.progress.connect(self.update_progress)
        self.worker_thread.finished.connect(self.on_deduplicate_finished)
        self.worker_thread.error.connect(self.on_deduplicate_error)
        self.worker_thread.start()

    def update_progress(self, stage, current, total):
        if self.progress_dialog is None:
            return
        try:
            percent = int((current / total) * 100) if total > 0 else 0
            self.progress_dialog.setValue(percent)
            self.progress_dialog.setLabelText(f"{stage}: {current}/{total}")
            QApplication.processEvents()
        except (TypeError, ZeroDivisionError, RuntimeError, AttributeError):
            # Gracefully handle errors due to invalid values or destroyed widget
            self.progress_dialog = None

    def on_deduplicate_finished(self, duplicate_groups, stats):
        self.progress_dialog.close()
        self.progress_dialog = None
        self.groups_list.set_groups(duplicate_groups)
        stats_text = stats.print_summary()
        self.stats_window = QMessageBox(self)
        self.stats_window.setWindowTitle(self.translator.tr("message_stats_title"))
        self.stats_window.setText(stats_text)
        self.stats_window.setIcon(QMessageBox.Icon.Information)
        self.stats_window.exec()

    def on_deduplicate_error(self, error_message):
        self.progress_dialog.close()
        self.progress_dialog = None
        QMessageBox.critical(self, self.translator.tr("title_error"), f"{self.translator.tr('error_occurred')}:\n{error_message}")

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
        self.settings_manager.save_settings("language", self.translator.lang_code)

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
        self.favorite_list_widget.clear()
        for path in self.app.favorite_dirs:
            self.favorite_list_widget.addItem(path)
        saved_lang = self.settings.value("language", "en")
        if not isinstance(saved_lang, str) or saved_lang not in self.supported_languages:
            saved_lang = "en"
        self.translator = DictTranslator(saved_lang)
        self.update_ui_texts()
        lang_index = self.supported_languages.index(saved_lang) if saved_lang in self.supported_languages else 0
        self.lang_combo.setCurrentIndex(lang_index)

    def update_ui_texts(self):
        tr = self.translator.tr

        # --- Заголовок окна ---
        self.setWindowTitle(tr("window_title"))

        # --- Кнопки и поля ---
        self.select_dir_button.setText(tr("btn_select_root"))
        self.root_dir_input.setPlaceholderText(tr("select_root_dir"))
        self.find_duplicates_button.setText(tr("btn_start_deduplication"))
        self.keep_one_button.setText(tr("btn_keep_one"))
        self.about_button.setText(tr("btn_about"))
        self.favorite_dirs_button.setText(tr("btn_manage_favorites"))

        # Обновляем заголовки групп
        self.filters_group.setTitle(tr("group_box_filters"))
        self.favorite_group.setTitle(tr("group_box_favorites"))

        # Обновляем подписи к фильтрам
        self.label_root_folder.setText(self.translator.tr("label_root_folder"))
        self.label_min_size.setText(self.translator.tr("label_min_size"))
        self.label_max_size.setText(self.translator.tr("label_max_size"))
        self.label_extensions.setText(self.translator.tr("label_extensions"))

        # --- Тултипы ---
        self.extension_filter_input.setToolTip(tr("tooltip_extensions"))
        self.favorite_dirs_button.setToolTip(tr("tooltip_favorite_dirs"))
        self.find_duplicates_button.setToolTip(tr("tooltip_find_duplicates"))
        self.keep_one_button.setToolTip(tr("tooltip_delete_duplicates"))
        self.about_button.setToolTip(tr("tooltip_about"))
        self.dedupe_mode_combo.setToolTip(tr("tooltip_dedupe_mode"))

        # --- Режимы дедупликации ---
        dedupe_mode_items = [tr("mode_fast"), tr("mode_normal"), tr("mode_full")]
        current_index = self.dedupe_mode_combo.currentIndex()
        self.dedupe_mode_combo.clear()
        for i, text in enumerate(dedupe_mode_items):
            mode_key = ["FAST", "NORMAL", "FULL"][i]
            self.dedupe_mode_combo.addItem(text, userData=mode_key)
        self.dedupe_mode_combo.setCurrentIndex(current_index)

        # --- Placeholder ---
        self.extension_filter_input.setPlaceholderText(tr("placeholder_extensions"))


# Import after class definition to avoid circular import
from translator import DictTranslator

if __name__ == "__main__":
    app = QApplication(sys.argv)
    translator = DictTranslator("ru")  # или "en"
    window = MainWindow(ui_translator=translator)
    window.show()
    sys.exit(app.exec())