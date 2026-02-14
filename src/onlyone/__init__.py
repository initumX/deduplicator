"""
OnlyOne — fast duplicate file finder with optional GUI.

Core features:
- Three deduplication modes: FAST (size + front hash), NORMAL (size + 3 partial hashes), FULL (size + full content hash)
- Safe deletion to system trash (via send2trash)
- Optional GUI with PySide6 (install with [gui] extra)
- CLI interface for headless/server usage
"""

# Get version
try:
    from importlib.metadata import version as _version
    __version__ = _version("onlyone")
except Exception:
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        import tomli as tomllib  # Python < 3.11: pip install tomli

    with open("pyproject.toml", "rb") as f:
        __version__ = tomllib.load(f)["project"]["version"]

# Public API — only what users should import directly
from onlyone.commands import DeduplicationCommand
#from .cli import main as cli_main
from onlyone.core import DeduplicationParams, DeduplicationMode, SortOrder, File, DuplicateGroup
from onlyone.utils.convert_utils import ConvertUtils
from onlyone.services import DuplicateService
from onlyone.services.file_service import FileService

__all__ = [
    "DeduplicationCommand",
    "DeduplicationParams",
    "DeduplicationMode",
    "SortOrder",
    "File",
    "DuplicateGroup",
    "ConvertUtils",
    "DuplicateService",
    "FileService",
    "__version__",
]