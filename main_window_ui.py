from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QSpinBox,
    QListWidget, QGroupBox, QSizePolicy, QSplitter, QAbstractItemView
)
from PySide6.QtCore import Qt
from custom_widgets.duplicate_groups_list import DuplicateGroupsList
from custom_widgets.image_preview_label import ImagePreviewLabel
from core.models import DeduplicationMode
from core.interfaces import TranslatorProtocol
from translator import DictTranslator


class Ui_MainWindow(object):
    def setupUi(self, MainWindow, ui_translator: TranslatorProtocol = None):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(900, 600)
        self.translator = ui_translator or DictTranslator("en")  # Use injected translator or default
        self.root_layout = QHBoxLayout()
        self.label_root_folder = QLabel("label_root_folder")
        self.root_layout.addWidget(self.label_root_folder)
        self.root_dir_input = QLineEdit()
        self.select_dir_button = QPushButton("Select Root Folder")

        self.extension_filter_input = QLineEdit()
        self.lang_combo = QComboBox()

        self.filters_group = QGroupBox("group_box_filters")

        self.min_size_layout = QHBoxLayout()
        self.label_min_size = QLabel("label_min_size")
        self.min_size_layout.addWidget(self.label_min_size)
        self.min_size_spin, self.min_unit_combo = self.create_size_input(100)


        self.max_size_layout = QHBoxLayout()
        self.label_max_size = QLabel("label_max_size")
        self.max_size_layout.addWidget(self.label_max_size)
        self.max_size_spin, self.max_unit_combo = self.create_size_input(100)

        self.extension_layout_inside = QHBoxLayout()
        self.label_extensions = QLabel("label_extensions")
        self.extension_layout_inside.addWidget(self.label_extensions)

        self.mode_label = QLabel("label_dedupe_mode")


        self.favorite_group = QGroupBox("group_box_favorites")
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

    def init_ui(self):
        tr = self.translator.tr
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        # --- Root Directory Layout ---
        self.root_dir_input.setPlaceholderText(tr("select_root_dir"))
        self.root_layout.addWidget(self.root_dir_input)
        self.select_dir_button.setText(tr("btn_select_root"))

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
        self.extension_filter_input.setPlaceholderText("placeholder_extensions")
        self.extension_filter_input.setToolTip(tr("tooltip_extensions"))
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
        self.favorite_dirs_button.setToolTip(tr("tooltip_favorite_dirs"))
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
        self.find_duplicates_button.setText(tr("btn_start_deduplication"))
        self.find_duplicates_button.setToolTip(tr("tooltip_find_duplicates"))

        control_layout.addWidget(self.find_duplicates_button)

        control_layout.addWidget(self.mode_label)
        self.dedupe_mode_combo.addItems([mode.value.upper() for mode in DeduplicationMode])
        self.dedupe_mode_combo.setToolTip(tr("tooltip_dedupe_mode"))
        control_layout.addWidget(self.dedupe_mode_combo)

        self.keep_one_button.setText(tr("btn_keep_one"))
        self.keep_one_button.setToolTip(tr("tooltip_delete_duplicates"))
        control_layout.addWidget(self.keep_one_button)

        self.about_button.setText(tr("btn_about"))
        self.about_button.setToolTip(tr("tooltip_about"))
        control_layout.addWidget(self.about_button)

        self.lang_combo.addItems(["English", "Русский"])
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


    @staticmethod
    def create_size_input(default_value=100):
        spin = QSpinBox()
        spin.setRange(0, 1024 * 1024)
        spin.setValue(default_value)
        unit_combo = QComboBox()
        unit_combo.addItems(["KB", "MB", "GB"])
        return spin, unit_combo

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
        self.label_root_folder.setText(tr("label_root_folder"))
        self.label_min_size.setText(tr("label_min_size"))
        self.label_max_size.setText(tr("label_max_size"))
        self.label_extensions.setText(tr("label_extensions"))

        # --- Тултипы ---
        self.extension_filter_input.setToolTip(tr("tooltip_extensions"))
        self.favorite_dirs_button.setToolTip(tr("tooltip_favorite_dirs"))
        self.find_duplicates_button.setToolTip(tr("tooltip_find_duplicates"))
        self.keep_one_button.setToolTip(tr("tooltip_delete_duplicates"))
        self.about_button.setToolTip(tr("tooltip_about"))
        self.dedupe_mode_combo.setToolTip(tr("tooltip_dedupe_mode"))

        # --- Режимы дедупликации ---
        self.mode_label.setText(tr("label_dedupe_mode"))
        dedupe_mode_items = [tr("mode_fast"), tr("mode_normal"), tr("mode_full")]
        current_index = self.dedupe_mode_combo.currentIndex()
        self.dedupe_mode_combo.clear()
        for i, text in enumerate(dedupe_mode_items):
            mode_key = ["FAST", "NORMAL", "FULL"][i]
            self.dedupe_mode_combo.addItem(text, userData=mode_key)
        self.dedupe_mode_combo.setCurrentIndex(current_index)

        # --- Placeholder ---
        self.extension_filter_input.setPlaceholderText(tr("placeholder_extensions"))