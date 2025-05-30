"""
hasher.py
Implements file hashing utilities using the File class.
Uses xxHash64 to compute partial and full hashes efficiently.

This implementation ensures predictable behavior:
- Each hash method returns only the requested portion of the file
- No hidden overrides for small files
- Chunk size decisions are made in the deduplicator, not here
"""

import xxhash
from core.models import File, Hasher


def compute_hash_at_offset(file_path: str, offset: int, chunk_size: int) -> bytes:
    """
    Computes a hash from a specific offset in the file.

    Args:
        file_path: Path to the file
        offset: Position in the file to start reading
        chunk_size: Number of bytes to read from offset

    Returns:
        bytes: The xxHash64 digest of the chunk

    Raises:
        RuntimeError: If reading fails or returns empty data
    """
    try:
        with open(file_path, 'rb') as f:
            f.seek(offset)
            chunk = f.read(chunk_size)
            if not chunk:
                raise RuntimeError(f"Empty read from {file_path}")
            return xxhash.xxh64(chunk).digest()
    except Exception as e:
        raise RuntimeError(f"Error reading {file_path} at offset {offset}: {e}")


class XXHasher(Hasher):
    """
    Concrete implementation of Hasher interface using xxHash64.
    Caches computed hashes in File objects to avoid recomputation.
    """

    def compute_full_hash(self, file: File) -> bytes:
        """
        Computes and caches the full xxHash64 digest of the entire file.
        """
        if file.full_hash is not None:
            return file.full_hash
        try:
            with open(file.path, 'rb') as f:
                digest = xxhash.xxh64(f.read()).digest()
            file.full_hash = digest
            return digest
        except Exception as e:
            raise RuntimeError(f"Failed to read {file.path}: {e}")

    def compute_front_hash(self, file: File) -> bytes:
        """
        Computes hash of the first N bytes of a file.
        Result is cached in file.front_hash.
        """
        if file.front_hash is not None:
            return file.front_hash
        result = compute_hash_at_offset(file.path, 0, file.chunk_size)
        file.front_hash = result
        return result

    def compute_middle_hash(self, file: File) -> bytes:
        """
        Computes hash of the central N bytes of a file.
        Result is cached in file.middle_hash.
        """
        if file.middle_hash is not None:
            return file.middle_hash
        offset = max(0, (file.size - file.chunk_size) // 2)
        result = compute_hash_at_offset(file.path, offset, file.chunk_size)
        file.middle_hash = result
        return result

    def compute_end_hash(self, file: File) -> bytes:
        """
        Computes hash of the last N bytes of a file.
        Result is cached in file.end_hash.
        """
        if file.end_hash is not None:
            return file.end_hash
        offset = max(0, file.size - file.chunk_size)
        result = compute_hash_at_offset(file.path, offset, file.chunk_size)
        file.end_hash = result
        return result
