"""
Unit tests for HasherImpl with XXHashAlgorithmImpl.
Verifies partial/full hashing returns 8-byte xxHash64 values.
"""
import pytest
from pathlib import Path
from tempfile import NamedTemporaryFile
from core.hasher import HasherImpl, XXHashAlgorithmImpl
from core.models import File, FileHashes


class TestHasherImpl:
    """Test xxHash64 computation with chunk-based reading."""

    def test_same_content_produces_same_full_hash(self):
        """Identical files must produce identical 8-byte full hashes."""
        content = b"test content " * 1000

        with NamedTemporaryFile(delete=False) as f1, NamedTemporaryFile(delete=False) as f2:
            try:
                f1.write(content)
                f1.flush()
                f2.write(content)
                f2.flush()

                file1 = File(path=f1.name, size=len(content), creation_time=0.0)
                file2 = File(path=f2.name, size=len(content), creation_time=0.0)

                hasher = HasherImpl(XXHashAlgorithmImpl())
                hash1 = hasher.compute_full_hash(file1)
                hash2 = hasher.compute_full_hash(file2)

                assert hash1 == hash2
                assert isinstance(hash1, bytes)
                assert len(hash1) == 8  # xxHash64 = 8 bytes
            finally:
                Path(f1.name).unlink()
                Path(f2.name).unlink()

    def test_different_content_produces_different_hashes(self):
        """Different files must produce different 8-byte hashes."""
        with NamedTemporaryFile(delete=False) as f1, NamedTemporaryFile(delete=False) as f2:
            try:
                f1.write(b"A" * 1024)
                f1.flush()
                f2.write(b"B" * 1024)
                f2.flush()

                file1 = File(path=f1.name, size=1024, creation_time=0.0)
                file2 = File(path=f2.name, size=1024, creation_time=0.0)

                hasher = HasherImpl(XXHashAlgorithmImpl())
                hash1 = hasher.compute_full_hash(file1)
                hash2 = hasher.compute_full_hash(file2)

                assert hash1 != hash2
                assert len(hash1) == 8
                assert len(hash2) == 8
            finally:
                Path(f1.name).unlink()
                Path(f2.name).unlink()

    def test_partial_hashes_with_non_uniform_content(self):
        """
        Front/middle/end hashes should differ for non-uniform content.
        Using uniform content (all 'X') causes identical hashes → false negative.
        """
        # Non-uniform content: different bytes at start/middle/end
        front_part = b"START_" + (b"A" * 64*1024)
        middle_part = b"MIDDLE_" + (b"B" * 64*1024)
        end_part = b"END_" + (b"C" * 64*1024)
        large_content = front_part + middle_part + end_part  # ~384KB

        with NamedTemporaryFile(delete=False) as f:
            try:
                f.write(large_content)
                f.flush()

                file = File(path=f.name, size=len(large_content), creation_time=0.0)
                file.chunk_size = 64 * 1024  # Required for partial hashes

                hasher = HasherImpl(XXHashAlgorithmImpl())

                # Compute all partial hashes
                front_hash = hasher.compute_front_hash(file)
                middle_hash = hasher.compute_middle_hash(file)
                end_hash = hasher.compute_end_hash(file)

                # All should be valid 8-byte hashes
                assert len(front_hash) == 8
                assert len(middle_hash) == 8
                assert len(end_hash) == 8

                # With non-uniform content, hashes should differ
                assert front_hash != middle_hash
                assert middle_hash != end_hash
                assert front_hash != end_hash
            finally:
                Path(f.name).unlink()

    def test_hash_caching(self):
        """Hasher should cache computed hashes in File.hashes."""
        content = b"test" * 100

        with NamedTemporaryFile(delete=False) as f:
            try:
                f.write(content)
                f.flush()

                file = File(path=f.name, size=len(content), creation_time=0.0)
                file.chunk_size = len(content)  # Full content in one chunk

                hasher = HasherImpl(XXHashAlgorithmImpl())

                # First call computes hash
                hash1 = hasher.compute_front_hash(file)
                assert file.hashes.front is not None
                assert file.hashes.front == hash1

                # Second call returns cached value (no I/O)
                hash2 = hasher.compute_front_hash(file)
                assert hash1 == hash2
            finally:
                Path(f.name).unlink()

    def test_hasher_handles_deleted_file(self, tmp_path):
        """
        Hasher must NOT crash when attempting to hash a deleted file.
        The exact return value is implementation-specific (may be b'' or hash of empty content),
        but the critical requirement is graceful error handling without exceptions.
        """
        # Create and immediately delete a file
        temp_file = tmp_path / "deleted.txt"
        temp_file.write_bytes(b"content")
        file = File(path=str(temp_file), size=7, creation_time=0.0)
        file.chunk_size = 1024
        temp_file.unlink()  # Delete BEFORE hashing

        hasher = HasherImpl(XXHashAlgorithmImpl())

        # CRITICAL: None of these should raise exceptions
        full_hash = hasher.compute_full_hash(file)
        front_hash = hasher.compute_front_hash(file)
        middle_hash = hasher.compute_middle_hash(file)
        end_hash = hasher.compute_end_hash(file)

        # All methods must return bytes (any bytes - empty or valid hash)
        assert isinstance(full_hash, bytes), "compute_full_hash must return bytes"
        assert isinstance(front_hash, bytes), "compute_front_hash must return bytes"
        assert isinstance(middle_hash, bytes), "compute_middle_hash must return bytes"
        assert isinstance(end_hash, bytes), "compute_end_hash must return bytes"

        # Verify error messages were printed (optional but useful for debugging)
        # Note: We don't check exact message content to avoid fragile tests
        # The key is that the application didn't crash