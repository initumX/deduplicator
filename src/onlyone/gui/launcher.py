#!/usr/bin/env python3
"""
GUI launcher — entry point for dedup-gui command.
"""
import logging
from pathlib import Path
import sys
from PySide6.QtWidgets import QApplication
from onlyone.gui.main_window import MainWindow

def main():
    log_dir = Path.home() / ".onlyone" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / "app.log", encoding='utf-8')]
    )
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()