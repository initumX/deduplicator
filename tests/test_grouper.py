"""
Unit tests for FileGrouperImpl.
Verifies grouping logic for size and hash-based grouping with proper filtering.
"""
from core.grouper import FileGrouperImpl
from core.hasher import HasherImpl, XXHashAlgorithmImpl
from core.models import File, FileHashes


class TestFileGrouperImpl:
    """Test file grouping by size and hash."""

    def test_groups_by_size_filters_single_files(self):
        """
        group_by_size returns ONLY groups with 2+ files of same size.
        Single files are filtered out (not considered duplicates).
        """
        files = [
            File(path="/a.txt", size=1024, creation_time=0.0),
            File(path="/b.txt", size=1024, creation_time=0.0),  # Same size → group
            File(path="/c.txt", size=2048, creation_time=0.0),  # Single file → filtered
        ]

        grouper = FileGrouperImpl()
        size_groups = grouper.group_by_size(files)

        # Only 1 group (1024B with 2 files), 2048B group filtered out (single file)
        assert len(size_groups) == 1
        assert 1024 in size_groups
        assert len(size_groups[1024]) == 2

    def test_groups_by_hash_filters_small_groups(self):
        """Hash-based grouping should exclude groups with <2 files."""
        files = [
            File(path="/dup1.txt", size=100, creation_time=0.0),
            File(path="/dup2.txt", size=100, creation_time=0.0),
            File(path="/unique.txt", size=100, creation_time=0.0),
        ]

        # Manually set identical front hashes for dup1/dup2
        identical_hash = b"hash1234"  # 8 bytes
        files[0].hashes = FileHashes(front=identical_hash)
        files[1].hashes = FileHashes(front=identical_hash)
        files[2].hashes = FileHashes(front=b"unique___")  # Different hash

        hasher = HasherImpl(XXHashAlgorithmImpl())
        grouper = FileGrouperImpl(hasher)

        hash_groups = grouper.group_by_front_hash(files)

        # Should have ONLY 1 group (dup1 + dup2), unique.txt excluded (<2 files)
        assert len(hash_groups) == 1
        group_files = list(hash_groups.values())[0]
        assert len(group_files) == 2
        assert {f.path for f in group_files} == {"/dup1.txt", "/dup2.txt"}

    def test_preserves_favorite_status_in_groups(self):
        """Grouped files should retain favorite directory status."""
        files = [
            File(path="/fav/file.txt", size=100, creation_time=0.0),
            File(path="/nonfav/file.txt", size=100, creation_time=0.0),
        ]
        files[0].is_from_fav_dir = True
        files[1].is_from_fav_dir = False

        # Set identical hashes
        hash_val = b"same_hash8"
        files[0].hashes = FileHashes(front=hash_val)
        files[1].hashes = FileHashes(front=hash_val)

        hasher = HasherImpl(XXHashAlgorithmImpl())
        grouper = FileGrouperImpl(hasher)

        hash_groups = grouper.group_by_front_hash(files)

        assert len(hash_groups) == 1
        group_files = list(hash_groups.values())[0]

        # Verify metadata preserved and sorting applied (favorites first)
        assert group_files[0].is_from_fav_dir is True   # First = favorite
        assert group_files[1].is_from_fav_dir is False  # Second = non-favorite
        assert group_files[0].path == "/fav/file.txt"
        assert group_files[1].path == "/nonfav/file.txt"