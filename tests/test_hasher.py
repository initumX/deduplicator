"""
Unit tests for HasherImpl with XXHashAlgorithmImpl.
Verifies partial/full hashing returns 8-byte xxHash64 values.
"""
from pathlib import Path
from tempfile import NamedTemporaryFile
from onlyone.core import HasherImpl, XXHashAlgorithmImpl
from onlyone.core import File



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

                file1 = File(path=f1.name, size=len(content))
                file2 = File(path=f2.name, size=len(content))

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

                file1 = File(path=f1.name, size=1024)
                file2 = File(path=f2.name, size=1024)

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

                file = File(path=f.name, size=len(large_content))
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

                file = File(path=f.name, size=len(content))
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





    class TestHasherErrorHandling:
        """Tests for hasher graceful error handling with Optional[bytes] return type."""

        def test_hasher_returns_none_on_deleted_file(self, tmp_path):
            """
            If file is deleted after stat but before hash computation,
            hasher must return None without raising exceptions.
            This allows the grouper to skip the file safely.
            """
            # Create file and immediately delete it before hashing
            temp_file = tmp_path / "volatile.txt"
            temp_file.write_bytes(b"content that will disappear")
            file_obj = File(path=str(temp_file), size=30)
            file_obj.chunk_size = 32

            # Delete BEFORE hashing (simulate race condition)
            temp_file.unlink()

            hasher = HasherImpl(XXHashAlgorithmImpl())

            # CRITICAL: None of these should raise exceptions
            # Application must degrade gracefully, not crash
            full_hash = hasher.compute_full_hash(file_obj)
            front_hash = hasher.compute_front_hash(file_obj)
            middle_hash = hasher.compute_middle_hash(file_obj)
            end_hash = hasher.compute_end_hash(file_obj)

            # UPDATED: All methods must return None on error (not b'')
            assert full_hash is None, "compute_full_hash must return None for missing files"
            assert front_hash is None, "compute_front_hash must return None for missing files"
            assert middle_hash is None, "compute_middle_hash must return None for missing files"
            assert end_hash is None, "compute_end_hash must return None for missing files"

        def test_hasher_returns_none_on_permission_error(self, tmp_path):
            """
            Hasher must return None when file cannot be read due to permissions.
            """
            temp_file = tmp_path / "protected.txt"
            temp_file.write_bytes(b"secret content")
            file_obj = File(path=str(temp_file), size=14)
            file_obj.chunk_size = 32

            # Remove read permissions (Unix-like systems)
            temp_file.chmod(0o000)

            hasher = HasherImpl(XXHashAlgorithmImpl())

            # Should not raise, should return None
            result = hasher.compute_full_hash(file_obj)
            assert result is None, "compute_full_hash must return None on permission error"

            # Cleanup
            temp_file.chmod(0o644)
            temp_file.unlink()

        def test_grouper_skips_none_hashes(self, tmp_path):
            """
            Integration test: verify that FileGrouper correctly skips files
            when hasher returns None.
            """
            from onlyone.core.grouper import FileGrouper

            # Create TWO valid files with identical content (to form a duplicate group)
            valid_file1 = tmp_path / "valid1.txt"
            valid_file1.write_bytes(b"identical content")
            valid_file_obj1 = File(path=str(valid_file1), size=17)
            valid_file_obj1.chunk_size = 32

            valid_file2 = tmp_path / "valid2.txt"
            valid_file2.write_bytes(b"identical content")  # Same content → same hash
            valid_file_obj2 = File(path=str(valid_file2), size=17)
            valid_file_obj2.chunk_size = 32

            # Create one "deleted" file (will return None hash)
            deleted_file = tmp_path / "deleted.txt"
            deleted_file.write_bytes(b"deleted content")
            deleted_file_obj = File(path=str(deleted_file), size=15)
            deleted_file_obj.chunk_size = 32
            deleted_file.unlink()  # Delete before hashing

            files = [valid_file_obj1, valid_file_obj2, deleted_file_obj]
            grouper = FileGrouper()

            # Group by front hash - should not crash
            groups = grouper.group_by_front_hash(files)

            # Verify: only the two valid files should be in groups (as a pair)
            # The deleted file (None hash) should be skipped
            total_files_in_groups = sum(len(file_list) for file_list in groups.values())

            assert total_files_in_groups == 2, "Only valid files should be grouped, and they should form a duplicate pair"

            # Verify the group contains both valid files
            assert len(groups) == 1, "Should have exactly one duplicate group"
            group_files = next(iter(groups.values()))
            group_paths = {f.path for f in group_files}
            assert group_paths == {str(valid_file1), str(valid_file2)}, "Group should contain both valid files"