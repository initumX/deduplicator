"""
OnlyOne — fast duplicate file finder with optional GUI.

Core features:
- Three deduplication modes: FAST (size + front hash), NORMAL (size + 3 partial hashes), FULL (size + full content hash)
- Safe deletion to system trash (via send2trash)
- Optional GUI with PySide6 (install with [gui] extra)
- CLI interface for headless/server usage
"""

# Get version
from importlib.metadata import version as _version
__version__ = _version("onlyone")

# Public API — only what users should import directly
from onlyone.commands import DeduplicationCommand
from onlyone.aliases import (
    BOOST_ALIASES, BOOST_CHOICES, BOOST_HELP_TEXT,
    DEDUP_MODE_ALIASES, DEDUP_MODE_CHOICES, DEDUP_MODE_HELP_TEXT,
    EPILOG_TEXT
)
from onlyone.core import DeduplicationParams, DeduplicationMode, SortOrder, File, DuplicateGroup
from onlyone.utils.convert_utils import bytes_to_human, human_to_bytes
from onlyone.services import DuplicateService
from onlyone.services.file_service import FileService
from onlyone.progress_bar import ProgressBar, ProgressContext
from onlyone.reporter import (
    format_groups_output,
    format_deletion_preview,
    format_deletion_result
)

__all__ = [
    "DeduplicationCommand",
    "DeduplicationParams",
    "DeduplicationMode",
    "SortOrder",
    "File",
    "ProgressBar",
    "ProgressContext",
    "format_groups_output",
    "format_deletion_preview",
    "format_deletion_result",
    "DuplicateGroup",
    "bytes_to_human",
    "human_to_bytes",
    "DuplicateService",
    "FileService",
    "__version__",
    "BOOST_ALIASES",
    "BOOST_CHOICES",
    "BOOST_HELP_TEXT",
    "DEDUP_MODE_ALIASES",
    "DEDUP_MODE_CHOICES",
    "DEDUP_MODE_HELP_TEXT",
    "EPILOG_TEXT",
]