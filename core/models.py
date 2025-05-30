"""
models.py

Data models and domain logic for file scanning and deduplication.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Union, Tuple, Any
from abc import ABC, abstractmethod
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

# =============================
# Core Data Models
# =============================

@dataclass
class File:
    """
    Represents a single file on the filesystem.
    Stores metadata and computed hashes to support deduplication.
    """
    path: str
    size: int  # in bytes
    phash: Optional[bytes] = None
    full_hash: Optional[bytes] = None  # xxHash64 digest of entire file
    front_hash: Optional[bytes] = None  # hash of first N bytes
    end_hash: Optional[bytes] = None  # hash of last N bytes
    middle_hash: Optional[bytes] = None  # hash of central N bytes
    chunk_size: Optional[int] = None # Will be set dynamically


    def __post_init__(self):
        """Validate that hash values are either None or valid bytes."""
        for field_name in ['full_hash', 'front_hash', 'end_hash', 'middle_hash']:
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, bytes):
                raise ValueError(f"{field_name} must be bytes or None")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            key: (value.hex() if isinstance(value, bytes) else value)
            for key, value in self.__dict__.items()
            if value is not None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'File':
        """Reconstruct File from dict (after loading from JSON)"""
        # Convert hex strings back to bytes where applicable
        phash = bytes.fromhex(data["phash"]) if "phash" in data else None
        full_hash = bytes.fromhex(data.get("full_hash")) if "full_hash" in data else None
        front_hash = bytes.fromhex(data.get("front_hash")) if "front_hash" in data else None
        end_hash = bytes.fromhex(data.get("end_hash")) if "end_hash" in data else None
        middle_hash = bytes.fromhex(data.get("middle_hash")) if "middle_hash" in data else None

        return cls(
            path=data["path"],
            size=int(data["size"]),
            phash=phash,
            full_hash=full_hash,
            front_hash=front_hash,
            end_hash=end_hash,
            middle_hash=middle_hash,
            chunk_size=data.get("chunk_size")
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
            "files": [f.to_dict() for f in self.files]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DuplicateGroup':
        files = [File.from_dict(f) for f in data["files"]]
        return cls(size=int(data["size"]), files=files)

    def __repr__(self):
        return f"<DuplicateGroup size={self.size}, count={len(self.files)}>"


@dataclass
class DeduplicationStats:
    """
    Statistics collected during the deduplication process.
    """
    total_time: float = 0.0
    stage_stats: Dict[str, Dict[str, Union[int, float]]] = None

    def __post_init__(self):
        if self.stage_stats is None:
            self.stage_stats = {}

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
# Interfaces & Abstract Classes
# =============================

class Hasher(ABC):
    """
    Interface for hashing strategies.
    Implementations should provide methods for computing specific parts of a file.
    """

    @abstractmethod
    def compute_front_hash(self, file: File) -> bytes:
        pass

    @abstractmethod
    def compute_end_hash(self, file: File) -> bytes:
        pass

    @abstractmethod
    def compute_middle_hash(self, file: File) -> bytes:
        pass

    @abstractmethod
    def compute_full_hash(self, file: File) -> bytes:
        pass


class FileScanner(ABC):
    """
    Interface for scanning directories and returning filtered files.
    """

    @abstractmethod
    def scan(self) -> List[File]:
        pass


class FileGrouper(ABC):
    """
    Interface for grouping files by various keys.
    """

    @abstractmethod
    def group_by_size(self, files: List[File]) -> Dict[int, List[File]]:
        pass

    @abstractmethod
    def group_by_front_hash(self, files: List[File]) -> Dict[bytes, List[File]]:
        pass

    @abstractmethod
    def group_by_end_hash(self, files: List[File]) -> Dict[bytes, List[File]]:
        pass

    @abstractmethod
    def group_by_middle_hash(self, files: List[File]) -> Dict[bytes, List[File]]:
        pass


    @abstractmethod
    def group_by_full_hash(self, files: List[File]) -> Dict[bytes, List[File]]:
        pass


class Deduplicator(ABC):
    """
    Interface for detecting duplicates based on multi-stage hash filtering.
    """

    @abstractmethod
    def find_duplicates(self, files: List[File], mode: DeduplicationMode) -> Tuple[List[DuplicateGroup], DeduplicationStats]:
        pass


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

