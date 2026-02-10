from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QSpinBox,
    QListWidget, QGroupBox, QSizePolicy, QSplitter, QAbstractItemView
)
from PySide6.QtCore import Qt
from custom_widgets.duplicate_groups_list import DuplicateGroupsList
from custom_widgets.image_preview_label import ImagePreviewLabel
from core.models import DeduplicationMode
from texts import TEXTS


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName("MainWindow")
        MainWindow.resize(900, 600)

        # Root directory selection layout
        self.root_layout = QHBoxLayout()
        self.label_root_folder = QLabel()
        self.root_layout.addWidget(self.label_root_folder)
        self.root_dir_input = QLineEdit()
        self.select_dir_button = QPushButton()

        # Filter controls
        self.extension_filter_input = QLineEdit()
        self.filters_group = QGroupBox()

        # Size filter controls
        self.min_size_layout = QHBoxLayout()
        self.label_min_size = QLabel()
        self.min_size_layout.addWidget(self.label_min_size)
        self.min_size_spin, self.min_unit_combo = self.create_size_input(100)

        self.max_size_layout = QHBoxLayout()
        self.label_max_size = QLabel()
        self.max_size_layout.addWidget(self.label_max_size)
        self.max_size_spin, self.max_unit_combo = self.create_size_input(100)

        # Extension filter controls
        self.extension_layout_inside = QHBoxLayout()
        self.label_extensions = QLabel()
        self.extension_layout_inside.addWidget(self.label_extensions)

        # Deduplication mode controls
        self.mode_label = QLabel()
        self.dedupe_mode_combo = QComboBox()
        self.find_duplicates_button = QPushButton()

        # File ordering controls
        self.ordering_label = QLabel()
        self.ordering_combo = QComboBox()

        # Runtime state
        self.progress_dialog = None
        self.stats_window = None

        # Action buttons
        self.keep_one_button = QPushButton()
        self.about_button = QPushButton()

        # Main content area
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.favorite_list_widget = QListWidget()
        self.favorite_list_widget.setContentsMargins(0, 0, 0, 0)
        self.favorite_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)

        # Output widgets
        self.groups_list = DuplicateGroupsList(self)
        self.image_preview = ImagePreviewLabel()

        # Favorite folders section
        self.favorite_group = QGroupBox()
        self.favorite_dirs_button = QPushButton()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        # Root directory input setup
        self.root_dir_input.setPlaceholderText(TEXTS["select_root_dir"])
        self.root_layout.addWidget(self.root_dir_input)
        self.root_layout.addWidget(self.select_dir_button)

        # Filters group configuration
        self.filters_group.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # Min size input setup
        self.min_size_spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.min_unit_combo.setCurrentText("KB")
        self.min_size_layout.addWidget(self.min_size_spin)
        self.min_size_layout.addWidget(self.min_unit_combo)

        # Max size input setup
        self.max_size_spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.max_unit_combo.setCurrentText("MB")
        self.max_size_layout.addWidget(self.max_size_spin)
        self.max_size_layout.addWidget(self.max_unit_combo)

        # Extension filter setup
        self.extension_filter_input.setPlaceholderText(TEXTS["placeholder_extensions"])
        self.extension_filter_input.setToolTip(TEXTS["tooltip_extensions"])
        self.extension_layout_inside.addWidget(self.extension_filter_input)

        # Assemble filters group layout
        filters_group_layout = QVBoxLayout()
        filters_group_layout.addLayout(self.min_size_layout)
        filters_group_layout.addLayout(self.max_size_layout)
        filters_group_layout.addLayout(self.extension_layout_inside)
        self.filters_group.setLayout(filters_group_layout)

        # Favorite folders section setup
        self.favorite_group.setMaximumHeight(self.filters_group.sizeHint().height() + 20)
        self.favorite_group.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        favorite_layout = QVBoxLayout()
        self.favorite_dirs_button.setToolTip(TEXTS["tooltip_favorite_dirs"])
        favorite_layout.addWidget(self.favorite_dirs_button)
        self.favorite_list_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.favorite_list_widget.setContentsMargins(0, 0, 0, 0)
        self.favorite_list_widget.setStyleSheet("padding: 0px; margin: 0px;")
        favorite_layout.addWidget(self.favorite_list_widget)
        self.favorite_group.setLayout(favorite_layout)

        # Top-level layout: filters + favorites side by side
        level_layout = QHBoxLayout()
        level_layout.addWidget(self.filters_group)
        level_layout.addWidget(self.favorite_group)
        level_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Control buttons and mode selection
        control_layout = QHBoxLayout()
        self.find_duplicates_button.setToolTip(TEXTS["tooltip_find_duplicates"])
        control_layout.addWidget(self.find_duplicates_button)

        control_layout.addWidget(self.mode_label)
        self.dedupe_mode_combo.addItems([mode.value.upper() for mode in DeduplicationMode])
        self.dedupe_mode_combo.setToolTip(TEXTS["tooltip_dedupe_mode"])
        control_layout.addWidget(self.dedupe_mode_combo)

        control_layout.addWidget(self.ordering_label)
        control_layout.addWidget(self.ordering_combo)

        self.keep_one_button.setToolTip(TEXTS["tooltip_delete_duplicates"])
        control_layout.addWidget(self.keep_one_button)

        self.about_button.setToolTip(TEXTS["tooltip_about"])
        control_layout.addWidget(self.about_button)

        control_layout.addStretch()
        control_layout.setContentsMargins(0, 20, 0, 0)

        # Main content splitter (groups list + image preview)
        self.splitter.addWidget(self.groups_list)
        self.splitter.addWidget(self.image_preview)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        self.splitter.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.groups_list.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        # Assemble main window layout
        main_layout = QVBoxLayout()
        main_layout.addLayout(self.root_layout)
        main_layout.addLayout(level_layout)
        main_layout.addLayout(control_layout)
        main_layout.addWidget(self.splitter, stretch=1)
        main_widget.setLayout(main_layout)

        # Apply all UI texts from TEXTS dictionary
        self.update_ui_texts()

    @staticmethod
    def create_size_input(default_value=100):
        spin = QSpinBox()
        spin.setRange(0, 1024 * 1024)
        spin.setValue(default_value)
        unit_combo = QComboBox()
        unit_combo.addItems(["KB", "MB", "GB"])
        return spin, unit_combo

    def update_ui_texts(self):
        """Apply all UI texts from TEXTS dictionary - single source of truth for strings."""
        # Window title
        self.setWindowTitle(TEXTS["window_title"])

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

        # Tooltips
        self.extension_filter_input.setToolTip(TEXTS["tooltip_extensions"])
        self.favorite_dirs_button.setToolTip(TEXTS["tooltip_favorite_dirs"])
        self.find_duplicates_button.setToolTip(TEXTS["tooltip_find_duplicates"])
        self.keep_one_button.setToolTip(TEXTS["tooltip_delete_duplicates"])
        self.about_button.setToolTip(TEXTS["tooltip_about"])
        self.dedupe_mode_combo.setToolTip(TEXTS["tooltip_dedupe_mode"])

        # Deduplication mode combo box items
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

        # Extension input placeholder
        self.extension_filter_input.setPlaceholderText(TEXTS["placeholder_extensions"])

        # Ordering combo box items
        ordering_items = [
            (TEXTS["Oldest_first"], "OLDEST_FIRST"),
            (TEXTS["Newest_first"], "NEWEST_FIRST")
        ]
        current_ordering_index = self.ordering_combo.currentIndex()
        self.ordering_combo.clear()
        for text, mode_key in ordering_items:
            self.ordering_combo.addItem(text, userData=mode_key)
        if 0 <= current_ordering_index < self.ordering_combo.count():
            self.ordering_combo.setCurrentIndex(current_ordering_index)