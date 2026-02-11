"""
GUI components built on PySide6 (optional dependency).
"""

from .main_window import MainWindow
from .main_window_ui import Ui_MainWindow
from .worker import DeduplicateWorker
from .texts import TEXTS

__all__ = ["MainWindow", "Ui_MainWindow", "DeduplicateWorker", "TEXTS"]