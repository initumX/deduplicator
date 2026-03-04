#!/usr/bin/env python3
"""
GUI launcher — entry point for dedup-gui command.
"""
import logging
from pathlib import Path
import sys
from PySide6.QtWidgets import QApplication
from onlyone.gui.main_window import MainWindow
from onlyone.logging_config import setup_logging, cleanup_logging

def main():
    # === UNIFIED LOGGING SETUP ===
    setup_logging(
        mode="gui",
        level=logging.INFO,
        verbose=False
    )
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    exit_code = app.exec()
    cleanup_logging()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()