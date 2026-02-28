"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License

core/hasher.py
Implements file hashing utilities using the File class and pluggable hash algorithms.

The GenericHasher class provides methods to compute partial and full hashes efficiently,
caching results in the File object's Hashes container.
"""

import xxhash
import logging
from onlyone.core.models import File
from typing import Protocol, Optional

logger = logging.getLogger(__name__)

class Hasher(Protocol):
    """Interface for hashing different parts of a file."""
    def compute_front_hash(self, file: File) -> Optional[bytes]: ...
    def compute_middle_hash(self, file: File) -> Optional[bytes]: ...
    def compute_end_hash(self, file: File) -> Optional[bytes]: ...
    def compute_full_hash(self, file: File) -> Optional[bytes]: ...


class HashAlgorithm(Protocol):
    """Interface for generic hash algorithms."""

    @staticmethod
    def hash(data: bytes) -> bytes:
        """Computes the hash of the provided byte data."""
        ...


# Use the same way to implement and use any other hashing algorithm
class XXHashAlgorithmImpl(HashAlgorithm):
    @staticmethod
    def hash(data: bytes) -> bytes:
        return xxhash.xxh64(data).digest()


class HasherImpl(Hasher):
    """
    A hasher implementation that supports any algorithm via the HashAlgorithm interface.
    Computes and caches hashes for different parts of a file.
    """

    def __init__(self, algorithm: HashAlgorithm):
        self.algorithm = algorithm

    def compute_full_hash(self, file: File) -> Optional[bytes]:
        if file.hashes.full is not None:
            return file.hashes.full
        try:
            with open(file.path, 'rb') as f:
                data = f.read()
                result = self.algorithm.hash(data)
                file.hashes.full = result
                return result
        except Exception as e:
            logger.error(f"Error reading full content of {file.path}: {e}", exc_info=True)
            return None

    def compute_front_hash(self, file: File) -> Optional[bytes]:
        """Computes and caches hash of the first N bytes of a file."""
        if file.hashes.front is not None:
            return file.hashes.front
        data = self._read_chunk(file, offset=0)
        if data is None:
            logger.warning(f"Could not read front chunk from {file.path}")
            return None
        result = self.algorithm.hash(data)
        file.hashes.front = result
        return result

    def compute_middle_hash(self, file: File) -> Optional[bytes]:
        """Computes and caches hash of the central N bytes of a file."""
        if file.hashes.middle is not None:
            return file.hashes.middle
        offset = max(0, file.size // 2)
        data = self._read_chunk(file, offset)
        if data is None:
            logger.warning(f"Could not read middle chunk from {file.path}")
            return None
        result = self.algorithm.hash(data)
        file.hashes.middle = result
        return result

    def compute_end_hash(self, file: File) -> Optional[bytes]:
        """Computes and caches hash of the last N bytes of a file."""
        if file.hashes.end is not None:
            return file.hashes.end
        offset = max(0, file.size - file.chunk_size)
        data = self._read_chunk(file, offset)
        if data is None:
            logger.warning(f"Could not read end chunk from {file.path}")
            return None
        result = self.algorithm.hash(data)
        file.hashes.end = result
        return result

    @staticmethod
    def _read_chunk(file: File, offset: int = 0) -> Optional[bytes]:
        """Reads and returns a chunk of data from the specified offset in the file."""
        try:
            with open(file.path, 'rb') as f:
                f.seek(offset)
                data = f.read(file.chunk_size)
                return data if data is not None else b''
        except Exception as e:
            logger.debug(f"Error reading {file.path} at offset {offset}: {e}")
            return None