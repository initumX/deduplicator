from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QSpinBox,
    QListWidget, QGroupBox, QSizePolicy, QSplitter, QAbstractItemView, QMainWindow
)
from PySide6.QtCore import Qt
from highlander.gui.custom_widgets.duplicate_groups_list import DuplicateGroupsList
from highlander.gui.custom_widgets.image_preview_label import ImagePreviewLabel
from highlander.core.models import DeduplicationMode
from highlander.core.models import SortOrder

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
        self.root_dir_input.setPlaceholderText("Select Folder to scan")
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
        self.extension_filter_input.setPlaceholderText(".jpg,.png")
        self.extension_filter_input.setToolTip(
            """Enter comma-separated file extensions to filter (e.g., .jpg, .png, .pdf).
                Leave empty to disable extension filtering."""
        )
        self.extension_layout_inside.addWidget(self.extension_filter_input)

        # Filters group
        self.filters_group = QGroupBox(central_widget)
        filters_group_layout = QVBoxLayout()
        filters_group_layout.addLayout(self.min_size_layout)
        filters_group_layout.addLayout(self.max_size_layout)
        filters_group_layout.addLayout(self.extension_layout_inside)
        self.filters_group.setLayout(filters_group_layout)
        self.filters_group.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # Favourite folders
        self.favourite_group = QGroupBox(central_widget)
        self.favourite_dirs_button = QPushButton(central_widget)
        self.favourite_dirs_button.setToolTip(
            "Files from favourite folders are prioritized (goes first, as 'original') in each group.\n"
        )
        self.favourite_list_widget = QListWidget(central_widget)
        self.favourite_list_widget.setContentsMargins(0, 0, 0, 0)
        self.favourite_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.favourite_list_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.favourite_list_widget.setStyleSheet("padding: 0px; margin: 0px;")

        favourite_layout = QVBoxLayout()
        favourite_layout.addWidget(self.favourite_dirs_button)
        favourite_layout.addWidget(self.favourite_list_widget)
        self.favourite_group.setLayout(favourite_layout)
        self.favourite_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Sync height with filters group
        MainWindow.updateGeometry()
        self.favourite_group.setMaximumHeight(self.filters_group.sizeHint().height() + 20)

        # Top-level layout: filters + favourites side by side
        level_layout = QHBoxLayout()
        level_layout.addWidget(self.filters_group)
        level_layout.addWidget(self.favourite_group)
        level_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Control buttons and mode selection
        self.mode_label = QLabel(central_widget)
        self.dedupe_mode_combo = QComboBox(central_widget)
        self.dedupe_mode_combo.addItems([mode.value.upper() for mode in DeduplicationMode])
        self.dedupe_mode_combo.setToolTip(
            """
            FAST: Size + checksum from the first few KB (fastest, but may produce false positives)
            NORMAL: Size + checksums from 3 parts of the file (generally reliable)
            FULL: Size + checksums from 2 parts of the file + checksum of entire file (very slow for large files)
            
            ** This staged approach minimizes expensive full-hash computations: each filtering step 
            eliminates non-matching files early, ensuring that only highly probable duplicates 
            reach the final FULL comparison stage.
            """
        )

        self.ordering_label = QLabel(central_widget)
        self.ordering_combo = QComboBox(central_widget)
        self.ordering_combo.setToolTip(
            """
            Which file should be kept/considered as "original"?
                • The file closest to the root folder (shortest path)
                • The file with the shortest filename
            """
        )

        self.find_duplicates_button = QPushButton(central_widget)
        self.find_duplicates_button.setToolTip(
            "Start searching for duplicate files.\nFiles from favourite folders are marked with ✅"
        )

        self.keep_one_button = QPushButton(central_widget)
        self.keep_one_button.setToolTip("Keep one file (the first) in the group and delete the rest")

        self.about_button = QPushButton(central_widget)
        self.about_button.setToolTip("Show Help")

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
        MainWindow.setWindowTitle("File Deduplicator")

        # Buttons and input fields
        self.select_dir_button.setText("Select Folder")
        self.root_dir_input.setPlaceholderText("Select Folder to scan")
        self.find_duplicates_button.setText("Find Duplicates")
        self.keep_one_button.setText("Keep One (The first one) File Per Group")
        self.about_button.setText("Help/About")
        self.favourite_dirs_button.setText("Manage Favourite Folders List")

        # Group box titles
        self.filters_group.setTitle("Filters")
        self.favourite_group.setTitle("Favourite Folders")

        # Labels
        self.label_root_folder.setText("Root Folder")
        self.label_min_size.setText("Min size:")
        self.label_max_size.setText("Max size:")
        self.label_extensions.setText("Extensions:")
        self.mode_label.setText("Mode:")
        self.ordering_label.setText("Order:")

        # Deduplication mode combo box
        dedupe_mode_items = [
            "Fast",
            "Normal",
            "Full"
        ]
        current_index = self.dedupe_mode_combo.currentIndex()
        self.dedupe_mode_combo.clear()
        for i, text in enumerate(dedupe_mode_items):
            mode_key = ["FAST", "NORMAL", "FULL"][i]
            self.dedupe_mode_combo.addItem(text, userData=mode_key)
        self.dedupe_mode_combo.setCurrentIndex(current_index)

        # Ordering combo box
        ordering_items = [
            ("Shortest Path First", SortOrder.SHORTEST_PATH),
            ("Shortest Filename First", SortOrder.SHORTEST_FILENAME)
        ]
        current_index = self.ordering_combo.currentIndex()
        self.ordering_combo.clear()
        for text, sort_order in ordering_items:
            self.ordering_combo.addItem(text, userData=sort_order)
        if 0 <= current_index < self.ordering_combo.count():
            self.ordering_combo.setCurrentIndex(current_index)