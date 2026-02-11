"""
File Deduplicator — fast duplicate file finder with optional GUI.

Core features:
- Three deduplication modes: FAST (size + front hash), NORMAL (size + 3 partial hashes), FULL (size + full content hash)
- Safe deletion to system trash (via send2trash)
- Optional GUI with PySide6 (install with [gui] extra)
- CLI interface for headless/server usage
"""

__version__ = "0.1.0"

# Public API — only what users should import directly
from deduplicator.commands import DeduplicationCommand
#from .cli import main as cli_main
from deduplicator.core import DeduplicationParams, DeduplicationMode, SortOrder, File, DuplicateGroup
from deduplicator.utils.convert_utils import ConvertUtils
from deduplicator.services import DuplicateService
from deduplicator.services.file_service import FileService

__all__ = [
    "DeduplicationCommand",
    "DeduplicationParams",
    "DeduplicationMode",
    "SortOrder",
    "File",
    "DuplicateGroup",
    "ConvertUtils",
    "DuplicateService",
    "FileService"
]