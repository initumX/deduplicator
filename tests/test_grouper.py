"""
Unit tests for FileGrouperImpl.
Verifies grouping logic for size, hash-based grouping, and fuzzy filename matching.
"""
import pytest
from onlyone.core.grouper import FileGrouperImpl
from onlyone.core.hasher import HasherImpl, XXHashAlgorithmImpl
from onlyone.core.models import File, FileHashes


class TestFileGrouperImpl:
    """Test file grouping by size and hash."""

    # ========================================================================
    # BASIC GROUPING TESTS
    # ========================================================================

    def test_groups_by_size_filters_single_files(self):
        """group_by_size returns ONLY groups with 2+ files of same size."""
        files = [
            File(path="/a.txt", size=1024, name="a.txt"),
            File(path="/b.txt", size=1024, name="b.txt"),  # Same size → group
            File(path="/c.txt", size=2048, name="c.txt"),  # Single file → filtered
        ]

        grouper = FileGrouperImpl()
        size_groups = grouper.group_by_size(files)

        assert len(size_groups) == 1
        assert 1024 in size_groups
        assert len(size_groups[1024]) == 2
        assert {f.path for f in size_groups[1024]} == {"/a.txt", "/b.txt"}

    def test_group_by_size_empty_input(self):
        """Empty file list should return empty dict."""
        grouper = FileGrouperImpl()
        result = grouper.group_by_size([])
        assert result == {}

    def test_group_by_size_all_unique(self):
        """All files with different sizes should return empty result."""
        files = [
            File(path="/f1.txt", size=100, name="f1.txt"),
            File(path="/f2.txt", size=200, name="f2.txt"),
            File(path="/f3.txt", size=300, name="f3.txt"),
        ]
        grouper = FileGrouperImpl()
        result = grouper.group_by_size(files)
        assert result == {}

    # ========================================================================
    # SIZE + EXTENSION GROUPING
    # ========================================================================

    def test_group_by_size_and_extension(self):
        """Files grouped by (size, extension) tuple."""
        files = [
            File(path="/a.jpg", size=1024, name="a.jpg", extension=".jpg"),
            File(path="/b.jpg", size=1024, name="b.jpg", extension=".jpg"),  # Same group
            File(path="/c.png", size=1024, name="c.png", extension=".png"),  # Diff ext → diff group
            File(path="/d.jpg", size=2048, name="d.jpg", extension=".jpg"),  # Diff size → diff group
        ]

        grouper = FileGrouperImpl()
        groups = grouper.group_by_size_and_extension(files)

        # Only (1024, ".jpg") has 2+ files
        assert len(groups) == 1
        assert (1024, ".jpg") in groups
        assert len(groups[(1024, ".jpg")]) == 2

    def test_group_by_size_and_extension_empty_extension(self):
        """Files without extension should group correctly."""
        files = [
            File(path="/README", size=512, name="README", extension=""),
            File(path="/Makefile", size=512, name="Makefile", extension=""),  # Same group
            File(path="/doc.txt", size=512, name="doc.txt", extension=".txt"),  # Diff ext
        ]

        grouper = FileGrouperImpl()
        groups = grouper.group_by_size_and_extension(files)

        assert len(groups) == 1
        assert (512, "") in groups
        assert len(groups[(512, "")]) == 2

    # ========================================================================
    # SIZE + EXACT NAME GROUPING
    # ========================================================================

    def test_group_by_size_and_name(self):
        """Files grouped by (size, exact name) — case-sensitive."""
        files = [
            File(path="/dir1/Report.pdf", size=1024, name="Report.pdf"),
            File(path="/dir2/Report.pdf", size=1024, name="Report.pdf"),  # Exact match → group
            File(path="/dir3/report.pdf", size=1024, name="report.pdf"),  # Lowercase → different
        ]

        grouper = FileGrouperImpl()
        groups = grouper.group_by_size_and_name(files)

        # Only exact "Report.pdf" matches
        assert len(groups) == 1
        assert (1024, "Report.pdf") in groups
        assert len(groups[(1024, "Report.pdf")]) == 2

    # ========================================================================
    # SIZE + NORMALIZED NAME GROUPING (NEW)
    # ========================================================================

    def test_group_by_size_and_normalized_name_basic(self):
        """Fuzzy grouping: names with digits/spaces/underscores should match."""
        files = [
            File(path="/img/Photo (1).jpg", size=2048, name="Photo (1).jpg"),
            File(path="/backup/Photo_2.jpg", size=2048, name="Photo_2.jpg"),  # Normalizes to same
            File(path="/other/Different.jpg", size=2048, name="Different.jpg"),  # Different name
        ]

        grouper = FileGrouperImpl()
        groups = grouper.group_by_size_and_normalized_name(files)

        assert len(groups) == 1
        # Key is (size, normalized_name)
        key = (2048, "photojpg")
        assert key in groups
        assert len(groups[key]) == 2
        assert {f.path for f in groups[key]} == {"/img/Photo (1).jpg", "/backup/Photo_2.jpg"}

    def test_normalize_name_removes_specified_chars(self):
        """Test _normalize_name_for_comparison removes _, spaces, (), digits, dots."""
        grouper = FileGrouperImpl()

        test_cases = [
            ("Report (Final) 2024.pdf", "reportfinalpdf"),
            ("My_File-Name_v2.docx", "myfilenamevdocx"),
            ("IMG_001.JPG", "imgjpg"),
            ("file (copy) (1).txt", "filecopytxt"),
            ("", ""),  # Empty name
            ("NormalName.pdf", "normalnamepdf"),
        ]

        for original, expected in test_cases:
            file = File(path="/dummy", size=100, name=original)
            result = grouper._normalize_name_for_comparison(file)
            assert result == expected, f"Failed for '{original}': got '{result}', expected '{expected}'"

    def test_normalize_name_case_insensitive(self):
        """Normalization should be case-insensitive."""
        grouper = FileGrouperImpl()

        files = [
            File(path="/a/FILE.JPG", size=100, name="FILE.JPG"),
            File(path="/b/file.jpg", size=100, name="file.jpg"),
            File(path="/c/File.Jpg", size=100, name="File.Jpg"),
        ]

        groups = grouper.group_by_size_and_normalized_name(files)

        # All should normalize to "filejpg" and group together
        assert len(groups) == 1
        key = (100, "filejpg")
        assert key in groups
        assert len(groups[key]) == 3

    def test_normalize_name_removes_hyphens_and_other_noise(self):
        """Verify that hyphens, underscores, digits, dots, parentheses are all removed."""
        grouper = FileGrouperImpl()

        file = File(path="/test", size=100, name="My-File_2024 (Copy).pdf")
        normalized = grouper._normalize_name_for_comparison(file)

        assert normalized == "myfilecopypdf"

    def test_group_by_normalized_name_different_sizes_not_grouped(self):
        """Files with same normalized name but different sizes should NOT group."""
        files = [
            File(path="/small/Doc.pdf", size=100, name="Doc (1).pdf"),
            File(path="/large/Doc.pdf", size=200, name="Doc_2.pdf"),  # Same normalized, diff size
        ]

        grouper = FileGrouperImpl()
        groups = grouper.group_by_size_and_normalized_name(files)

        # Different sizes → different keys → no grouping
        assert len(groups) == 0

    # ========================================================================
    # HASH-BASED GROUPING TESTS
    # ========================================================================

    def test_group_by_front_hash(self):
        """Files with identical front hash should group together."""
        files = [
            File(path="/dup1.txt", size=100, name="dup1.txt"),
            File(path="/dup2.txt", size=100, name="dup2.txt"),
            File(path="/unique.txt", size=100, name="unique.txt"),
        ]

        # Mock identical hashes for dup1/dup2
        identical_hash = b"front_hash_123"
        files[0].hashes = FileHashes(front=identical_hash)
        files[1].hashes = FileHashes(front=identical_hash)
        files[2].hashes = FileHashes(front=b"different_hash__")

        hasher = HasherImpl(XXHashAlgorithmImpl())
        grouper = FileGrouperImpl(hasher)

        groups = grouper.group_by_front_hash(files)

        assert len(groups) == 1
        assert identical_hash in groups
        assert len(groups[identical_hash]) == 2

    def test_hash_grouping_methods_consistency(self):
        """All hash methods (front/middle/end/full) should follow same grouping logic."""
        files = [
            File(path="/a.bin", size=500, name="a.bin"),
            File(path="/b.bin", size=500, name="b.bin"),
        ]

        # Set identical hashes for all types
        test_hash = b"test_hash_value_"
        for f in files:
            f.hashes = FileHashes(
                front=test_hash,
                middle=test_hash,
                end=test_hash,
                full=test_hash
            )

        hasher = HasherImpl(XXHashAlgorithmImpl())
        grouper = FileGrouperImpl(hasher)

        # All methods should produce 1 group with 2 files
        methods = [
            grouper.group_by_front_hash,
            grouper.group_by_middle_hash,
            grouper.group_by_end_hash,
            grouper.group_by_full_hash,
        ]

        for method in methods:
            groups = method(files)
            assert len(groups) == 1, f"{method.__name__} failed"
            assert len(list(groups.values())[0]) == 2

    # ========================================================================
    # FAVOURITE DIRECTORY SORTING
    # ========================================================================

    def test_favourite_files_sorted_first_in_groups(self):
        """Files from favourite dirs should appear first in grouped lists."""
        files = [
            File(path="/nonfav/dup.txt", size=100, name="dup.txt"),
            File(path="/fav/dup.txt", size=100, name="dup.txt"),
            File(path="/alsofav/dup.txt", size=100, name="dup.txt"),
        ]
        files[0].is_from_fav_dir = False
        files[1].is_from_fav_dir = True
        files[2].is_from_fav_dir = True

        # Use size-based grouping (simplest for this test)
        grouper = FileGrouperImpl()
        groups = grouper.group_by_size(files)

        assert len(groups) == 1
        group = groups[100]

        # First two should be favourites (order among favourites is stable)
        assert group[0].is_from_fav_dir is True
        assert group[1].is_from_fav_dir is True
        assert group[2].is_from_fav_dir is False

    def test_favourite_status_preserved_after_grouping(self):
        """Grouping should not modify file metadata."""
        files = [
            File(path="/fav/a.txt", size=50, name="a.txt"),
            File(path="/nonfav/b.txt", size=50, name="b.txt"),
        ]
        files[0].is_from_fav_dir = True
        files[1].is_from_fav_dir = False

        grouper = FileGrouperImpl()
        grouper.group_by_size(files)

        # Original objects should be unchanged
        assert files[0].is_from_fav_dir is True
        assert files[1].is_from_fav_dir is False

    # ========================================================================
    # EDGE CASES AND ERROR HANDLING
    # ========================================================================

    def test_group_by_with_none_key_filtered(self):
        """Files that produce None key should be skipped silently."""
        files = [
            File(path="/valid.txt", size=100, name="valid.txt"),
            File(path="/valid2.txt", size=100, name="valid2.txt"),
        ]

        # Custom key_func that returns None for specific file
        def faulty_key_func(f):
            if "valid2" in f.path:
                return None
            return f.size

        grouper = FileGrouperImpl()
        groups = grouper._group_by(files, faulty_key_func)

        # Only valid.txt should be considered; but single file → filtered out
        assert len(groups) == 0

    def test_group_by_exception_handling(self, capsys):
        """Exceptions in key_func should be caught and logged, not crash."""
        files = [
            File(path="/good.txt", size=100, name="good.txt"),
            File(path="/bad.txt", size=200, name="bad.txt"),
            File(path="/good2.txt", size=100, name="good2.txt"),
        ]

        def flaky_key_func(f):
            if "bad" in f.path:
                raise ValueError("Simulated error")
            return f.size

        grouper = FileGrouperImpl()
        groups = grouper._group_by(files, flaky_key_func)

        # Verify output
        captured = capsys.readouterr()
        assert "⚠️ Error processing /bad.txt" in captured.out
        assert "⚠️ Skipped 1 files" in captured.out

        # Good files should still be grouped
        assert len(groups) == 1
        assert 100 in groups
        assert len(groups[100]) == 2

    def test_group_by_with_mixed_valid_invalid_files(self):
        """Valid files should be grouped even if some files cause errors."""
        files = [
            File(path="/a.txt", size=100, name="a.txt"),
            File(path="/b.txt", size=100, name="b.txt"),  # Same size as /a.txt
            File(path="/error.txt", size=100, name="error.txt"),  # Will raise
            File(path="/c.txt", size=100, name="c.txt"),  # Same size as /a.txt
        ]

        def error_on_specific(f):
            if f.path == "/error.txt":
                raise RuntimeError("Test error")
            return f.size

        grouper = FileGrouperImpl()
        groups = grouper._group_by(files, error_on_specific)

        # Three good files of size 100 → one group
        assert len(groups) == 1
        assert len(groups[100]) == 3
        assert {f.path for f in groups[100]} == {"/a.txt", "/b.txt", "/c.txt"}

    def test_normalize_name_with_none_or_empty(self):
        """_normalize_name_for_comparison handles None/empty names gracefully."""
        grouper = FileGrouperImpl()

        # Empty string name
        assert grouper._normalize_name_for_comparison(File(path="/x", size=1, name="")) == ""

        # Name with only special chars (all removed)
        result = grouper._normalize_name_for_comparison(File(path="/x", size=1, name="___(123)."))
        assert result == ""

    def test_group_by_preserves_original_file_objects(self):
        """Grouping returns references to original File objects, not copies."""
        files = [
            File(path="/a.txt", size=100, name="a.txt"),
            File(path="/b.txt", size=100, name="b.txt"),
        ]

        grouper = FileGrouperImpl()
        groups = grouper.group_by_size(files)

        # Objects in groups should be the same instances
        group = groups[100]
        assert files[0] in group
        assert files[1] in group
        assert group[0] is files[0] or group[0] is files[1]  # One of them is first

    # ========================================================================
    # INTEGRATION: MULTI-STAGE GROUPING SCENARIO
    # ========================================================================

    def test_realistic_dedup_workflow(self):
        """Simulate real usage: filter by size → fuzzy name → hash verification."""
        files = [
            # Group 1: Same size, fuzzy-matching names, same content
            File(path="/photos/IMG_001.jpg", size=5000, name="IMG_001.jpg"),
            File(path="/backup/IMG (1).jpg", size=5000, name="IMG (1).jpg"),

            # Group 2: Same size, different names → should NOT fuzzy-match
            File(path="/docs/Report.pdf", size=5000, name="Report.pdf"),
            File(path="/docs/Summary.pdf", size=5000, name="Summary.pdf"),

            # Singleton: unique size
            File(path="/misc/Unique.dat", size=9999, name="Unique.dat"),
        ]

        # Set identical full hashes for Group 1
        group1_hash = b"photo_hash_12345"
        files[0].hashes = FileHashes(full=group1_hash)
        files[1].hashes = FileHashes(full=group1_hash)
        # Group 2 files get different hashes
        files[2].hashes = FileHashes(full=b"report_hash_____")
        files[3].hashes = FileHashes(full=b"summary_hash____")

        grouper = FileGrouperImpl()

        # Stage 1: Fuzzy name grouping (fast pre-filter)
        fuzzy_groups = grouper.group_by_size_and_normalized_name(files)

        # Expect 1 group: IMG_001.jpg + IMG (1).jpg
        assert len(fuzzy_groups) == 1
        assert (5000, "imgjpg") in fuzzy_groups

        # Stage 2: Full hash verification on fuzzy group candidates
        candidates = fuzzy_groups.get((5000, "imgjpg"), [])
        final_groups = grouper.group_by_full_hash(candidates)

        # Hash verification confirms they're true duplicates
        assert len(final_groups) == 1
        assert group1_hash in final_groups
        assert len(final_groups[group1_hash]) == 2