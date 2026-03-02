"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License

core/models.py
Data models and domain logic for file scanning and deduplication.
"""
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Union, Callable
import os
from enum import Enum

logger = logging.getLogger(__name__)

# =============================
# Enums
# =============================

class DeduplicationMode(Enum):
    """
    Deduplication mode controlling the depth of duplicate detection.
    """
    NORMAL = "normal"
    FULL = "full"

    @property
    def display_name(self) -> str:
        """Human-readable name for UI display."""
        mapping = {
            DeduplicationMode.NORMAL: "Normal",
            DeduplicationMode.FULL: "Full",
        }
        return mapping.get(self, self.value)

    @property
    def description(self) -> str:
        """Detailed description for help text."""
        mapping = {
            DeduplicationMode.NORMAL:
                "Size → Front → Middle → End Hash (balanced speed/accuracy)",
            DeduplicationMode.FULL:
                "Size → Front → Middle → Full Hash (slowest)",
        }
        return mapping.get(self, self.value)

    def __repr__(self) -> str:
        return self.value

class Stage(str, Enum):
    SIZE = "Size grouping"
    FRONT = "Front-chunk Hash"
    MIDDLE = "Middle-chunk Hash"
    END = "End-chunk Hash"
    FULL = "Full Hash"

    @classmethod
    def get_all(cls):
        return [cls.SIZE, cls.FRONT, cls.MIDDLE, cls.END, cls.FULL]

class SortOrder(Enum):
    SHORTEST_PATH = "shortest-path"
    SHORTEST_FILENAME = "shortest-filename"

    @property
    def display_name(self) -> str:
        """Human-readable name for UI display."""
        mapping = {
            SortOrder.SHORTEST_PATH: "Shortest Path",
            SortOrder.SHORTEST_FILENAME: "Shortest f-name",
        }
        return mapping.get(self, self.value)

class BoostMode(Enum):
    """
    Boost mode for file grouping strategy.
    Controls how files are grouped during the initial size-based stage.
    """
    SAME_SIZE = "same-size"
    SAME_SIZE_PLUS_EXT = "same-size-plus-ext"
    SAME_SIZE_PLUS_FUZZY_FILENAME = "same-size-plus-fuzzy-filename"
    SAME_SIZE_PLUS_FILENAME = "same-size-plus-filename"


    @property
    def display_name(self) -> str:
        """Human-readable name for UI display."""
        mapping = {
            BoostMode.SAME_SIZE: "Size",
            BoostMode.SAME_SIZE_PLUS_EXT: "Size + Extension",
            BoostMode.SAME_SIZE_PLUS_FUZZY_FILENAME: "Size + fuzzy f-name",
            BoostMode.SAME_SIZE_PLUS_FILENAME: "Size + exact f-name",
        }
        return mapping.get(self, self.value)

    def __repr__(self) -> str:
        return self.value


# ======================
#  Core Data Models
# ======================

@dataclass
class FileHashes:
    full: Optional[bytes] = None
    front: Optional[bytes] = None
    middle: Optional[bytes] = None
    end: Optional[bytes] = None
    phash: Optional[bytes] = None

    def __post_init__(self):
        fields = getattr(self, '__dataclass_fields__', {})
        for key in fields:
            value = getattr(self, key)
            if value is not None and not isinstance(value, bytes):
                raise ValueError(f"Field '{key}' must be bytes or None")

@dataclass
class File:
    """
    Represents a single file on the file system.
    Stores metadata and computed hashes to support deduplication.
    """
    path: str
    size: int  # in bytes
    name: Optional[str] = None
    extension: Optional[str] = None
    is_from_fav_dir: bool = False
    path_depth: int = 0
    is_confirmed_duplicate: bool = False  # Mark files that have already been confirmed as duplicate
    hashes: FileHashes = field(default_factory=FileHashes)
    chunk_size: Optional[int] = None  # Will be set dynamically

    def __post_init__(self):
        """Automatically extract basename and extension from path if not provided."""
        if self.name is None:
            self.name = os.path.basename(self.path)

        if self.extension is None:
            _, ext = os.path.splitext(self.name)
            self.extension = ext.lower()  # ".JPG" → ".jpg"

    def set_favourite_status(self, favourite_dirs: List[str]) -> None:
        """
        Sets the is_from_fav_dir flag if the file is located in one of the favourite directories.
        The path is checked strictly: a file is considered to be from a favourite directory
        if its path starts with one of the paths from favourite_dirs.
        """
        normalized_path = os.path.normpath(self.path)

        for fav_dir in favourite_dirs:
            normalized_fav_dir = os.path.normpath(fav_dir)

            # Check if the file's path is a subpath of the favourite directory
            if normalized_path.startswith(normalized_fav_dir + os.sep) or \
                    normalized_path == normalized_fav_dir:
                self.is_from_fav_dir = True
                return
        self.is_from_fav_dir = False

    def __repr__(self):
        return f"<File path={self.path}, size={self.size}>"

@dataclass
class DuplicateGroup:
    """
    A group of files that are potential duplicates.
    All files in the group have the same size and matching hash signatures.
    """
    size: int
    files: List[File]

    @property
    def duplicate_count(self) -> int:
        """How many files are in this group."""
        return len(self.files)

    def add_file(self, file: File) -> None:
        if file.size != self.size:
            raise ValueError("Cannot add file with different size to a group.")
        self.files.append(file)

    def is_duplicate(self) -> bool:
        """True if this group contains at least two files."""
        return self.duplicate_count >= 2

    def __repr__(self):
        return f"<DuplicateGroup size={self.size}, count={len(self.files)}>"

@dataclass
class DeduplicationStats:
    """
    Statistics collected during the deduplication process.
    """
    def __init__(self):
        self.total_time: float = 0.0
        self.scan_time: float = 0.0
        self.grouping_time: float = 0.0
        self.stage_stats: Dict[str, Dict[str, Union[int, float]]] = {}
        self._listeners: List[Callable[[str, Dict], None]] = []

    def add_listener(self, listener: Callable[[str, Dict], None]):
        """Adds a listener to receive updates when stats are updated."""
        self._listeners.append(listener)

    def update_stage(
            self,
            stage_name: str,
            groups_found: int,
            files_processed: int,
            duration: float
    ) -> None:
        if stage_name not in self.stage_stats:
            self.stage_stats[stage_name] = {
                "groups": 0,
                "files": 0,
                "time": 0.0
            }
        self.stage_stats[stage_name]["groups"] += groups_found
        self.stage_stats[stage_name]["files"] += files_processed
        self.stage_stats[stage_name]["time"] += duration

        # Notify listeners about the update
        for listener in self._listeners:
            try:
                listener(stage_name, self.stage_stats[stage_name])
            except Exception as e:
                logger.error(f"Error in stats event handler: {e}", exc_info=True)

    def notify_stage_start(self, stage_name: str):
        """Optional: notifies listeners that a new stage has started."""
        for listener in self._listeners:
            try:
                listener(stage_name, {"status": "started"})
            except Exception as e:
                logger.error(f"Error in stats event handler: {e}", exc_info=True)


    def print_summary(self) -> str:
        labels = {
            "size": "Initial",
            "front": "Front",
            "middle": "Middle",
            "end": "End",
            "full": "Full",
        }

        lines = [
            "Deduplication Statistics:",
            "================",
            f"Scanning Time: {self.scan_time:.3f}s",
            f"Calculations Time: {self.grouping_time:.3f}s",
            f"Total Time: {self.total_time:.3f}s",
            "================",
            "Stage: Groups / Files / Time",
        ]

        for stage, data in self.stage_stats.items():
            label = labels.get(stage.lower(), stage.title())
            if data["groups"] > 0 or data["time"] > 0:
                lines.append(f"{label}: {data['groups']} / {data['files']} / {data['time']:.3f}s")

        return "\n".join(lines)

"""
DTO for deduplication parameters with built-in validation.
Interface-agnostic — used by both GUI and CLI.
"""
from dataclasses import dataclass, field
from onlyone.core.measurer import human_to_bytes
from onlyone.core.validator import (
    validate_deduplication_params
)


@dataclass
class DeduplicationParams:
    """
    Parameters for deduplication operation with validation.

    All path and filter parameters are automatically normalized and validated
    upon instantiation using the centralized validator module.
    """
    root_dirs: List[str]
    min_size_bytes: int
    max_size_bytes: int
    extensions: List[str] = field(default_factory=list)
    favourite_dirs: List[str] = field(default_factory=list)
    excluded_dirs: List[str] = field(default_factory=list)
    mode: DeduplicationMode = DeduplicationMode.NORMAL
    sort_order: SortOrder = SortOrder.SHORTEST_PATH
    boost: BoostMode = field(default=BoostMode.SAME_SIZE)

    # === Read-only computed properties (set in __post_init__) ===
    _extension_filter_mode: str = field(default="whitelist", init=False)
    _normalized_extensions: List[str] = field(default_factory=list, init=False)
    _normalized_root_dirs: List[str] = field(default_factory=list, init=False)
    _normalized_favourite_dirs: List[str] = field(default_factory=list, init=False)
    _normalized_excluded_dirs: List[str] = field(default_factory=list, init=False)

    def __post_init__(self):
        """Validate and normalize parameters using the centralized validator."""
        validated = validate_deduplication_params(
            root_dirs=self.root_dirs,
            min_size_bytes=self.min_size_bytes,
            max_size_bytes=self.max_size_bytes,
            extensions=self.extensions,
            favourite_dirs=self.favourite_dirs,
            excluded_dirs=self.excluded_dirs,
        )

        # Store validated and normalized values in private fields
        self._normalized_root_dirs = validated["root_dirs"]
        self._normalized_extensions = validated["extensions"]
        self._extension_filter_mode = validated["extension_filter_mode"]
        self._normalized_favourite_dirs = validated["favourite_dirs"]
        self._normalized_excluded_dirs = validated["excluded_dirs"]

        # Update public fields with normalized paths for consistency
        self.root_dirs = self._normalized_root_dirs
        self.favourite_dirs = self._normalized_favourite_dirs
        self.excluded_dirs = self._normalized_excluded_dirs
        self.extensions = self._normalized_extensions

    @property
    def normalized_root_dirs(self) -> List[str]:
        """Get normalized root directories (read-only)."""
        return self._normalized_root_dirs

    @property
    def normalized_extensions(self) -> List[str]:
        """Get normalized extensions (read-only)."""
        return self._normalized_extensions

    @property
    def extension_filter_mode(self) -> str:
        """Get filter mode: 'whitelist' or 'blacklist' (read-only)."""
        return self._extension_filter_mode

    @property
    def normalized_favourite_dirs(self) -> List[str]:
        """Get normalized favourite directories (read-only)."""
        return self._normalized_favourite_dirs

    @property
    def normalized_excluded_dirs(self) -> List[str]:
        """Get normalized excluded directories (read-only)."""
        return self._normalized_excluded_dirs

    @staticmethod
    def from_human_readable(
            root_dirs: List[str],
            min_size_str: str,
            max_size_str: str,
            extensions: Optional[List[str]] = None,
            favourite_dirs: Optional[List[str]] = None,
            excluded_dirs: Optional[List[str]] = None,
            sort_order: SortOrder = SortOrder.SHORTEST_PATH,
            mode: DeduplicationMode = DeduplicationMode.NORMAL,
            boost: BoostMode = BoostMode.SAME_SIZE,
    ) -> "DeduplicationParams":
        """
        Factory method to create params from human-readable inputs.
        """
        min_size = human_to_bytes(min_size_str)
        max_size = human_to_bytes(max_size_str)

        return DeduplicationParams(
            root_dirs=root_dirs,
            min_size_bytes=min_size,
            max_size_bytes=max_size,
            extensions=extensions or [],
            favourite_dirs=favourite_dirs or [],
            excluded_dirs=excluded_dirs or [],
            mode=mode,
            sort_order=sort_order,
            boost=boost,
        )

    def __repr__(self) -> str:
        return (
            f"<DeduplicationParams root_dirs={len(self._normalized_root_dirs)} "
            f"size=[{self.min_size_bytes}, {self.max_size_bytes}] "
            f"mode={self.mode.value} boost={self.boost.value}>"
        )