from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QSpinBox,
    QListWidget, QGroupBox, QSizePolicy, QSplitter, QAbstractItemView, QMainWindow
)
from PySide6.QtCore import Qt
from custom_widgets.duplicate_groups_list import DuplicateGroupsList
from custom_widgets.image_preview_label import ImagePreviewLabel
from core.models import DeduplicationMode
from texts import TEXTS


class Ui_MainWindow:
    """Pure UI class following Qt's official pattern (composition, not inheritance)."""

    def setupUi(self, MainWindow: QMainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(900, 600)

        central_widget = QWidget(MainWindow)
        MainWindow.setCentralWidget(central_widget)

        # Root directory layout
        self.root_layout = QHBoxLayout()
        self.label_root_folder = QLabel(central_widget)
        self.root_layout.addWidget(self.label_root_folder)
        self.root_dir_input = QLineEdit(central_widget)
        self.select_dir_button = QPushButton(central_widget)
        self.root_dir_input.setPlaceholderText(TEXTS["select_root_dir"])
        self.root_layout.addWidget(self.root_dir_input)
        self.root_layout.addWidget(self.select_dir_button)

        # Size filters
        self.min_size_layout = QHBoxLayout()
        self.label_min_size = QLabel(central_widget)
        self.min_size_layout.addWidget(self.label_min_size)
        self.min_size_spin, self.min_unit_combo = self.create_size_input(100, central_widget)
        self.min_size_spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.min_unit_combo.setCurrentText("KB")
        self.min_size_layout.addWidget(self.min_size_spin)
        self.min_size_layout.addWidget(self.min_unit_combo)

        self.max_size_layout = QHBoxLayout()
        self.label_max_size = QLabel(central_widget)
        self.max_size_layout.addWidget(self.label_max_size)
        self.max_size_spin, self.max_unit_combo = self.create_size_input(100, central_widget)
        self.max_size_spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.max_unit_combo.setCurrentText("MB")
        self.max_size_layout.addWidget(self.max_size_spin)
        self.max_size_layout.addWidget(self.max_unit_combo)

        # Extension filter
        self.extension_layout_inside = QHBoxLayout()
        self.label_extensions = QLabel(central_widget)
        self.extension_layout_inside.addWidget(self.label_extensions)
        self.extension_filter_input = QLineEdit(central_widget)
        self.extension_filter_input.setPlaceholderText(TEXTS["placeholder_extensions"])
        self.extension_filter_input.setToolTip(TEXTS["tooltip_extensions"])
        self.extension_layout_inside.addWidget(self.extension_filter_input)

        # Filters group
        self.filters_group = QGroupBox(central_widget)
        filters_group_layout = QVBoxLayout()
        filters_group_layout.addLayout(self.min_size_layout)
        filters_group_layout.addLayout(self.max_size_layout)
        filters_group_layout.addLayout(self.extension_layout_inside)
        self.filters_group.setLayout(filters_group_layout)
        self.filters_group.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # Favorite folders
        self.favorite_group = QGroupBox(central_widget)
        self.favorite_dirs_button = QPushButton(central_widget)
        self.favorite_dirs_button.setToolTip(TEXTS["tooltip_favorite_dirs"])
        self.favorite_list_widget = QListWidget(central_widget)
        self.favorite_list_widget.setContentsMargins(0, 0, 0, 0)
        self.favorite_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.favorite_list_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.favorite_list_widget.setStyleSheet("padding: 0px; margin: 0px;")

        favorite_layout = QVBoxLayout()
        favorite_layout.addWidget(self.favorite_dirs_button)
        favorite_layout.addWidget(self.favorite_list_widget)
        self.favorite_group.setLayout(favorite_layout)
        self.favorite_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Sync height with filters group
        MainWindow.updateGeometry()
        self.favorite_group.setMaximumHeight(self.filters_group.sizeHint().height() + 20)

        # Top-level layout: filters + favorites side by side
        level_layout = QHBoxLayout()
        level_layout.addWidget(self.filters_group)
        level_layout.addWidget(self.favorite_group)
        level_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Control buttons and mode selection
        self.mode_label = QLabel(central_widget)
        self.dedupe_mode_combo = QComboBox(central_widget)
        self.dedupe_mode_combo.addItems([mode.value.upper() for mode in DeduplicationMode])
        self.dedupe_mode_combo.setToolTip(TEXTS["tooltip_dedupe_mode"])

        self.ordering_label = QLabel(central_widget)
        self.ordering_combo = QComboBox(central_widget)

        self.find_duplicates_button = QPushButton(central_widget)
        self.find_duplicates_button.setToolTip(TEXTS["tooltip_find_duplicates"])

        self.keep_one_button = QPushButton(central_widget)
        self.keep_one_button.setToolTip(TEXTS["tooltip_delete_duplicates"])

        self.about_button = QPushButton(central_widget)
        self.about_button.setToolTip(TEXTS["tooltip_about"])

        control_layout = QHBoxLayout()
        control_layout.addWidget(self.find_duplicates_button)
        control_layout.addWidget(self.mode_label)
        control_layout.addWidget(self.dedupe_mode_combo)
        control_layout.addWidget(self.ordering_label)
        control_layout.addWidget(self.ordering_combo)
        control_layout.addWidget(self.keep_one_button)
        control_layout.addWidget(self.about_button)
        control_layout.addStretch()
        control_layout.setContentsMargins(0, 20, 0, 0)

        # Main content area: groups list + image preview
        self.splitter = QSplitter(Qt.Orientation.Horizontal, central_widget)
        self.groups_list = DuplicateGroupsList()  # Parent will be set by splitter
        self.image_preview = ImagePreviewLabel()  # Custom widget - no parent argument
        self.splitter.addWidget(self.groups_list)
        self.splitter.addWidget(self.image_preview)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        self.splitter.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.groups_list.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        # Main layout assembly
        main_layout = QVBoxLayout(central_widget)
        main_layout.addLayout(self.root_layout)
        main_layout.addLayout(level_layout)
        main_layout.addLayout(control_layout)
        main_layout.addWidget(self.splitter, stretch=1)

        # Apply all UI texts
        self.retranslateUi(MainWindow)

    @staticmethod
    def create_size_input(default_value: int = 100, parent: QWidget | None = None) -> tuple[QSpinBox, QComboBox]:
        spin = QSpinBox(parent)
        spin.setRange(0, 1024 * 1024)
        spin.setValue(default_value)
        unit_combo = QComboBox(parent)
        unit_combo.addItems(["KB", "MB", "GB"])
        return spin, unit_combo

    def retranslateUi(self, MainWindow: QMainWindow):
        """Apply all UI texts - single source of truth for strings."""
        MainWindow.setWindowTitle(TEXTS["window_title"])

        # Buttons and input fields
        self.select_dir_button.setText(TEXTS["btn_select_root"])
        self.root_dir_input.setPlaceholderText(TEXTS["select_root_dir"])
        self.find_duplicates_button.setText(TEXTS["btn_start_deduplication"])
        self.keep_one_button.setText(TEXTS["btn_keep_one"])
        self.about_button.setText(TEXTS["btn_about"])
        self.favorite_dirs_button.setText(TEXTS["btn_manage_favorites"])

        # Group box titles
        self.filters_group.setTitle(TEXTS["group_box_filters"])
        self.favorite_group.setTitle(TEXTS["group_box_favorites"])

        # Labels
        self.label_root_folder.setText(TEXTS["label_root_folder"])
        self.label_min_size.setText(TEXTS["label_min_size"])
        self.label_max_size.setText(TEXTS["label_max_size"])
        self.label_extensions.setText(TEXTS["label_extensions"])
        self.mode_label.setText(TEXTS["label_dedupe_mode"])
        self.ordering_label.setText(TEXTS["label_ordering"])

        # Deduplication mode combo box
        dedupe_mode_items = [
            TEXTS["mode_fast"],
            TEXTS["mode_normal"],
            TEXTS["mode_full"]
        ]
        current_index = self.dedupe_mode_combo.currentIndex()
        self.dedupe_mode_combo.clear()
        for i, text in enumerate(dedupe_mode_items):
            mode_key = ["FAST", "NORMAL", "FULL"][i]
            self.dedupe_mode_combo.addItem(text, userData=mode_key)
        self.dedupe_mode_combo.setCurrentIndex(current_index)

        # Ordering combo box
        ordering_items = [
            (TEXTS["Oldest_first"], "OLDEST_FIRST"),
            (TEXTS["Newest_first"], "NEWEST_FIRST")
        ]
        current_index = self.ordering_combo.currentIndex()
        self.ordering_combo.clear()
        for text, mode_key in ordering_items:
            self.ordering_combo.addItem(text, userData=mode_key)
        if 0 <= current_index < self.ordering_combo.count():
            self.ordering_combo.setCurrentIndex(current_index)