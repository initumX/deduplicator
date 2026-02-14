#!/usr/bin/env python3
"""
GUI launcher — entry point for dedup-gui command.
"""
import sys
from PySide6.QtWidgets import QApplication
from highlander.gui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()