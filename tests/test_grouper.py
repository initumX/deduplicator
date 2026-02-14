"""
Unit tests for FileGrouperImpl.
Verifies grouping logic for size and hash-based grouping with proper filtering.
"""
from highlander.core import FileGrouperImpl
from highlander.core import HasherImpl, XXHashAlgorithmImpl
from highlander.core import File, FileHashes


class TestFileGrouperImpl:
    """Test file grouping by size and hash."""

    def test_groups_by_size_filters_single_files(self):
        """
        group_by_size returns ONLY groups with 2+ files of same size.
        Single files are filtered out (not considered duplicates).
        """
        files = [
            File(path="/a.txt", size=1024),
            File(path="/b.txt", size=1024),  # Same size → group
            File(path="/c.txt", size=2048),  # Single file → filtered
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
            File(path="/dup1.txt", size=100),
            File(path="/dup2.txt", size=100),
            File(path="/unique.txt", size=100),
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

    def test_preserves_favourite_status_in_groups(self):
        """Grouped files should retain favourite directory status."""
        files = [
            File(path="/fav/file.txt", size=100),
            File(path="/nonfav/file.txt", size=100),
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

        # Verify metadata preserved and sorting applied (favourites first)
        assert group_files[0].is_from_fav_dir is True   # First = favourite
        assert group_files[1].is_from_fav_dir is False  # Second = non-favourite
        assert group_files[0].path == "/fav/file.txt"
        assert group_files[1].path == "/nonfav/file.txt"

    def test_grouper_all_unique_files(self):
        """
        When all files are unique (different sizes or hashes), grouper should return empty result.
        """
        # Scenario 1: All files have different sizes
        files_different_sizes = [
            File(path="/file1.txt", size=100),
            File(path="/file2.txt", size=200),
            File(path="/file3.txt", size=300),
            File(path="/file4.txt", size=400),
        ]

        grouper = FileGrouperImpl()
        size_groups = grouper.group_by_size(files_different_sizes)

        # No groups possible — all sizes unique
        assert len(size_groups) == 0

        # Scenario 2: Same size but different hashes (all unique content)
        files_same_size_different_hashes = [
            File(path="/fileA.txt", size=100),
            File(path="/fileB.txt", size=100),
            File(path="/fileC.txt", size=100),
        ]

        # Set unique hashes for each file
        files_same_size_different_hashes[0].hashes = FileHashes(front=b"hash_aaaa")
        files_same_size_different_hashes[1].hashes = FileHashes(front=b"hash_bbbb")
        files_same_size_different_hashes[2].hashes = FileHashes(front=b"hash_cccc")

        hasher = HasherImpl(XXHashAlgorithmImpl())
        grouper_with_hasher = FileGrouperImpl(hasher)
        hash_groups = grouper_with_hasher.group_by_front_hash(files_same_size_different_hashes)

        # No groups possible — all hashes unique
        assert len(hash_groups) == 0