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
from typing import Protocol, BinaryIO, Optional

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

    @staticmethod
    def hash_stream(file_obj: BinaryIO, chunk_size: int = 1 * 1024 * 1024) -> bytes:
        """Computes hash by reading from a file-like object in chunks."""
        ...


class XXHashAlgorithmImpl(HashAlgorithm):
    @staticmethod
    def hash(data: bytes) -> bytes:
        return xxhash.xxh64(data).digest()

    @staticmethod
    def hash_stream(file_obj: BinaryIO, chunk_size: int = 1 * 1024 * 1024) -> bytes:
        """Stream hash a file-like object using xxhash."""
        hasher = xxhash.xxh64()
        while chunk := file_obj.read(chunk_size):
            hasher.update(chunk)
        return hasher.digest()


class HasherImpl(Hasher):
    """
    A hasher implementation that supports any algorithm via the HashAlgorithm interface.
    Computes and caches hashes for different parts of a file.
    Returns None on errors to allow graceful degradation.
    """

    def __init__(self, algorithm: HashAlgorithm):
        self.algorithm = algorithm

    FULL_HASH_CHUNK_SIZE = 256 * 1024

    def compute_full_hash(self, file: File) -> Optional[bytes]:
        if file.hashes.full is not None:
            return file.hashes.full
        try:
            with open(file.path, 'rb') as f:
                if hasattr(self.algorithm, 'hash_stream'):
                    result = self.algorithm.hash_stream(f, chunk_size=self.FULL_HASH_CHUNK_SIZE)
                else:
                    data = f.read()
                    result = self.algorithm.hash(data)

            file.hashes.full = result
            return result

        except FileNotFoundError:
            logger.warning(f"File not found (skipping): {file.path}")
            return None
        except PermissionError:
            logger.warning(f"Permission denied (skipping): {file.path}")
            return None
        except OSError as e:
            logger.warning(f"Error reading {file.path}: {e}")
            return None

    def compute_front_hash(self, file: File) -> Optional[bytes]:
        """Computes and caches hash of the first N bytes of a file."""
        if file.hashes.front is not None:
            return file.hashes.front
        try:
            data = self._read_chunk(file, offset=0)
            if data is None:
                return None
            result = self.algorithm.hash(data)
            file.hashes.front = result
            return result
        except Exception as e:
            logger.warning(f"Unexpected error computing front-chunk hash for {file.path}: {e}")
            return None

    def compute_middle_hash(self, file: File) -> Optional[bytes]:
        """Computes and caches hash of the central N bytes of a file."""
        if file.hashes.middle is not None:
            return file.hashes.middle
        try:
            offset = max(0, file.size // 2)
            data = self._read_chunk(file, offset)
            if data is None:
                return None
            result = self.algorithm.hash(data)
            file.hashes.middle = result
            return result
        except Exception as e:
            logger.warning(f"Unexpected error computing middle-chunk hash for {file.path}: {e}")
            return None

    def compute_end_hash(self, file: File) -> Optional[bytes]:
        """Computes and caches hash of the last N bytes of a file."""
        if file.hashes.end is not None:
            return file.hashes.end
        try:
            offset = max(0, file.size - file.chunk_size)
            data = self._read_chunk(file, offset)
            if data is None:
                return None
            result = self.algorithm.hash(data)
            file.hashes.end = result
            return result
        except Exception as e:
            logger.warning(f"Unexpected error computing end-chunk hash for {file.path}: {e}")
            return None

    @staticmethod
    def _read_chunk(file: File, offset: int = 0) -> Optional[bytes]:
        """Reads and returns a chunk of data from the specified offset in the file.

        Returns:
            bytes if successful, None if any error occurs.
        """
        try:
            with open(file.path, 'rb') as f:
                f.seek(offset)
                return f.read(file.chunk_size)
        except FileNotFoundError:
            logger.warning(f"File not found while reading chunk: {file.path}")
            return None
        except PermissionError:
            logger.warning(f"Permission denied while reading chunk: {file.path}")
            return None
        except OSError as e:
            logger.warning(f"Error reading {file.path} at offset {offset}: {e}")
            return None