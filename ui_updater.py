
# ui_updater.py

from PySide6.QtWidgets import QGroupBox, QLabel

def update_ui_texts(main_window):
    """
    Обновляет все текстовые элементы интерфейса согласно текущему языку.
    """
    tr = main_window.translator.tr

    # --- Заголовок окна ---
    main_window.setWindowTitle(tr("window_title"))

    # --- Кнопки и поля ---
    main_window.select_dir_button.setText(tr("btn_select_root"))
    main_window.root_dir_input.setPlaceholderText(tr("select_root_dir"))
    main_window.find_duplicates_button.setText(tr("btn_start_deduplication"))
    main_window.keep_one_button.setText(tr("btn_keep_one"))
    main_window.about_button.setText(tr("btn_about"))
    main_window.favorite_dirs_button.setText(tr("btn_manage_favorites"))

    # --- Группы ---
    for group in main_window.findChildren(QGroupBox):
        title = group.title()
        if title == "Filters":
            group.setTitle(tr("group_box_filters"))
        elif title == "Favorite Folders":
            group.setTitle(tr("group_box_favorites"))

    # --- Подписи к фильтрам ---
    for label in main_window.findChildren(QLabel):
        text = label.text()
        if text == "Root Folder:":
            label.setText(tr("label_root_folder"))
        elif text == "Min Size:":
            label.setText(tr("label_min_size"))
        elif text == "Max Size:":
            label.setText(tr("label_max_size"))
        elif text == "Extensions:":
            label.setText(tr("label_extensions"))

    # --- Тултипы ---
    main_window.extension_filter_input.setToolTip(tr("tooltip_extensions"))
    main_window.favorite_dirs_button.setToolTip(tr("tooltip_favorite_dirs"))
    main_window.find_duplicates_button.setToolTip(tr("tooltip_find_duplicates"))
    main_window.keep_one_button.setToolTip(tr("tooltip_delete_duplicates"))
    main_window.about_button.setToolTip(tr("tooltip_about"))
    main_window.dedupe_mode_combo.setToolTip(tr("tooltip_dedupe_mode"))

    # --- Режимы дедупликации ---
    dedupe_mode_items = [tr("mode_fast"), tr("mode_normal"), tr("mode_full")]
    current_index = main_window.dedupe_mode_combo.currentIndex()
    main_window.dedupe_mode_combo.clear()
    for i, text in enumerate(dedupe_mode_items):
        mode_key = ["FAST", "NORMAL", "FULL"][i]  # соответствующий ключ
        main_window.dedupe_mode_combo.addItem(text, userData=mode_key)
    main_window.dedupe_mode_combo.setCurrentIndex(current_index)

    # --- Placeholder ---
    main_window.extension_filter_input.setPlaceholderText(tr("placeholder_extensions"))

