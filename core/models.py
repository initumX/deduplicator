"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License

models.py
Data models and domain logic for file scanning and deduplication.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Union, Any, Callable
import os
from enum import Enum


# =============================
# Enums
# =============================

class DeduplicationMode(str, Enum):
    FAST = "fast"
    NORMAL = "normal"
    FULL = "full"

class Stage(str, Enum):
    SIZE = "size"
    FRONT = "front"
    MIDDLE = "middle"
    END = "end"
    FULL = "full"

    @classmethod
    def get_all(cls):
        return [cls.SIZE, cls.FRONT, cls.MIDDLE, cls.END, cls.FULL]


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

    def to_dict(self) -> Dict[str, str]:
        result = {}
        fields = getattr(self, '__dataclass_fields__', {})
        for key in fields:
            value = getattr(self, key)
            if value is not None:
                result[key] = value.hex()
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'FileHashes':
        return cls(**{
            key: bytes.fromhex(val) if val else None
            for key, val in data.items()
        })

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

    def set_favorite_status(self, favorite_dirs: List[str]) -> None:
        """
        Sets the is_from_fav_dir flag if the file is located in one of the favorite directories.
        The path is checked strictly: a file is considered to be from a favorite directory
        if its path starts with one of the paths from favorite_dirs.
        """
        normalized_path = os.path.normpath(self.path)

        for fav_dir in favorite_dirs:
            normalized_fav_dir = os.path.normpath(fav_dir)

            # Check if the file's path is a subpath of the favorite directory
            if normalized_path.startswith(normalized_fav_dir + os.sep) or \
                    normalized_path == normalized_fav_dir:
                self.is_from_fav_dir = True
                return
        self.is_from_fav_dir = False

    def to_dict(self) -> Dict[str, Any]:
        data = {
            'path': self.path,
            'size': self.size,
            'name': self.name,
            'extension': self.extension,
            'is_from_fav_dir': self.is_from_fav_dir,
            'is_confirmed_duplicate': self.is_confirmed_duplicate,
            'chunk_size': self.chunk_size,
            'hashes': self.hashes.to_dict(),
        }
        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'File':
        """Reconstruct File from dict (after loading from JSON)"""
        hash_data = data.get('hashes', {})
        hashes = FileHashes.from_dict(hash_data)

        return cls(
            path=data['path'],
            size=int(data['size']),
            name=data.get('name'),
            extension=data.get('extension'),
            is_from_fav_dir=data.get('is_from_fav_dir', False),
            is_confirmed_duplicate=data.get('is_confirmed_duplicate', False),
            hashes=hashes,
            chunk_size=data.get('chunk_size')
        )

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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "size": self.size,
            "files": [file.to_dict() for file in self.files],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DuplicateGroup':
        files = [File.from_dict(file_data) for file_data in data.get("files", [])]
        return cls(
            size=int(data["size"]),
            files=files
        )

    def __repr__(self):
        return f"<DuplicateGroup size={self.size}, count={len(self.files)}>"

@dataclass
class DeduplicationStats:
    """
    Statistics collected during the deduplication process.
    """
    def __init__(self):
        self.total_time: float = 0.0
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
                print(f"Error in stats event handler: {e}")

    def notify_stage_start(self, stage_name: str):
        """Optional: notifies listeners that a new stage has started."""
        for listener in self._listeners:
            try:
                listener(stage_name, {"status": "started"})
            except Exception as e:
                print(f"⚠️ Error in stats event handler: {e}")


    def print_summary(self) -> None:
        labels = {
            "size": "📁 Size Groups",
            "front": "📄 Front Hash Groups",
            "end": "🔚 End Hash Groups",
            "middle": "🧠 Middle Hash Groups",
            "full": "🔍 Full Content Hash Groups",
        }

        print("\n📊 Deduplication Statistics:")
        for stage, data in self.stage_stats.items():
            label = labels.get(stage, stage)
            if data["groups"] > 0 or data["time"] > 0:
                print(f"{label}: {data['groups']} groups, {data['files']} files / Time: {data['time']:.3f}s")

        print(f"\n⏱️ Total Execution Time: {self.total_time:.3f}s")


# =============================
# Utility Classes
# =============================

class FileCollection:
    """
    A utility class for working with collections of files.
    Provides filtering, sorting, and transformation operations.
    """

    def __init__(self, files: List[File]):
        self.files = files

    def filter_by_size(self, min_size: Optional[int] = None, max_size: Optional[int] = None) -> 'FileCollection':
        filtered = [
            f for f in self.files
            if (min_size is None or f.size >= min_size) and
               (max_size is None or f.size <= max_size)
        ]
        return FileCollection(filtered)

    def filter_by_extension(self, extensions: List[str]) -> 'FileCollection':
        def matches_extension(path: str) -> bool:
            base_name = os.path.basename(path)
            if base_name.startswith("."):
                return False
            parts = base_name.split('.')
            for i in range(1, len(parts)):
                candidate = "." + ".".join(parts[i:])
                if any(candidate.lower() == ext.lower() for ext in extensions):
                    return True
            return False

        filtered = [f for f in self.files if matches_extension(f.path)]
        return FileCollection(filtered)

    def sort_by_size_desc(self) -> 'FileCollection':
        sorted_files = sorted(self.files, key=lambda f: -f.size)
        return FileCollection(sorted_files)

    def get_paths(self) -> List[str]:
        return [f.path for f in self.files]

    def __len__(self):
        return len(self.files)

    def __bool__(self):
        return bool(self.files)

    def __iter__(self):
        return iter(self.files)

    def __repr__(self):
        return f"<FileCollection({len(self.files)} files)>"
