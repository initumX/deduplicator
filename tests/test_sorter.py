"""
Unit tests for core/sorter.py
Verifies file sorting logic inside duplicate groups with favourite file priority.
"""
from onlyone.core.sorter import Sorter
from onlyone.core.models import DuplicateGroup, File, SortOrder


# =============================================================================
# 1. BASIC SORTING FUNCTIONALITY
# =============================================================================
class TestSorterBasicFunctionality:
    """Test basic sorting behavior of Sorter class."""

    def test_sort_files_inside_groups_empty_list(self):
        """Empty groups list should not cause errors."""
        groups = []
        # Should not raise any exception
        Sorter.sort_files_inside_groups(groups)
        assert groups == []

    def test_sort_files_inside_groups_none_input(self):
        """None input should be handled gracefully (type: ignore for intentional test)."""
        # Testing defensive programming - Sorter should handle None without crashing
        Sorter.sort_files_inside_groups(None)  # type: ignore[arg-type]

    def test_sort_files_inside_groups_single_group(self):
        """Single group should be sorted correctly."""
        files = [
            File(path="/deep/nested/file.txt", size=100, name="file.txt", path_depth=3),
            File(path="/shallow/file.txt", size=100, name="file.txt", path_depth=1),
        ]
        group = DuplicateGroup(size=100, files=files)

        Sorter.sort_files_inside_groups([group])

        # Shallow path should be first (default SHORTEST_PATH)
        assert group.files[0].path == "/shallow/file.txt"
        assert group.files[1].path == "/deep/nested/file.txt"

    def test_sort_files_inside_groups_multiple_groups(self):
        """Multiple groups should all be sorted independently."""
        group1 = DuplicateGroup(size=100, files=[
            File(path="/deep/a.txt", size=100, path_depth=2),
            File(path="/shallow/a.txt", size=100, path_depth=1),
        ])
        group2 = DuplicateGroup(size=200, files=[
            File(path="/deep/b.txt", size=200, path_depth=2),
            File(path="/shallow/b.txt", size=200, path_depth=1),
        ])

        Sorter.sort_files_inside_groups([group1, group2])

        # Both groups should have shallow file first
        assert group1.files[0].path_depth == 1
        assert group2.files[0].path_depth == 1

    def test_sort_modifies_groups_in_place(self):
        """Sorting should modify groups in-place, not create new lists."""
        files = [
            File(path="/deep/file.txt", size=100, path_depth=2),
            File(path="/shallow/file.txt", size=100, path_depth=1),
        ]
        group = DuplicateGroup(size=100, files=files)
        original_list_id = id(group.files)

        Sorter.sort_files_inside_groups([group])

        # List object should be the same (modified in-place)
        assert id(group.files) == original_list_id


# =============================================================================
# 2. FAVOURITE FILES PRIORITY (ABSOLUTE)
# =============================================================================
class TestSorterFavouriteFilesPriority:
    """Test that favourite files always have absolute priority."""

    def test_favourite_file_always_first_regardless_of_path_depth(self):
        """
        CRITICAL: Favourite files MUST be first even if they have deeper paths.
        This is an absolute priority rule for data safety.
        """
        files = [
            File(path="/normal/shallow/file.txt", size=100, path_depth=2, is_from_fav_dir=False),
            File(path="/favourite/deep/nested/file.txt", size=100, path_depth=4, is_from_fav_dir=True),
        ]
        group = DuplicateGroup(size=100, files=files)

        Sorter.sort_files_inside_groups([group])

        # Favourite file MUST be first despite deeper path
        assert group.files[0].is_from_fav_dir is True
        assert group.files[0].path == "/favourite/deep/nested/file.txt"
        assert group.files[1].is_from_fav_dir is False

    def test_favourite_file_always_first_regardless_of_filename_length(self):
        """
        CRITICAL: Favourite files MUST be first even with longer filenames.
        """
        files = [
            File(path="/normal/short.txt", size=100, name="short.txt", is_from_fav_dir=False),
            File(path="/favourite/very_long_filename.txt", size=100, name="very_long_filename.txt", is_from_fav_dir=True),
        ]
        group = DuplicateGroup(size=100, files=files)

        Sorter.sort_files_inside_groups([group], SortOrder.SHORTEST_FILENAME)

        # Favourite file MUST be first despite longer filename
        assert group.files[0].is_from_fav_dir is True
        assert group.files[0].name == "very_long_filename.txt"

    def test_multiple_favourites_sorted_among_themselves(self):
        """
        When multiple favourite files exist, they should be sorted by secondary criterion.
        """
        files = [
            File(path="/fav/deep/file.txt", size=100, path_depth=3, is_from_fav_dir=True),
            File(path="/fav/shallow/file.txt", size=100, path_depth=1, is_from_fav_dir=True),
            File(path="/normal/file.txt", size=100, path_depth=2, is_from_fav_dir=False),
        ]
        group = DuplicateGroup(size=100, files=files)

        Sorter.sort_files_inside_groups([group])

        # All favourites first, then non-favourites
        assert group.files[0].is_from_fav_dir is True
        assert group.files[1].is_from_fav_dir is True
        assert group.files[2].is_from_fav_dir is False
        # Among favourites, shallow path should be first
        assert group.files[0].path_depth == 1
        assert group.files[1].path_depth == 3

    def test_all_favourites_in_group(self):
        """Group with all favourite files should still be sorted by secondary criterion."""
        files = [
            File(path="/fav/deep/file.txt", size=100, path_depth=3, is_from_fav_dir=True),
            File(path="/fav/shallow/file.txt", size=100, path_depth=1, is_from_fav_dir=True),
            File(path="/fav/medium/file.txt", size=100, path_depth=2, is_from_fav_dir=True),
        ]
        group = DuplicateGroup(size=100, files=files)

        Sorter.sort_files_inside_groups([group])

        # All are favourites, so sort by path depth
        assert group.files[0].path_depth == 1
        assert group.files[1].path_depth == 2
        assert group.files[2].path_depth == 3

    def test_no_favourites_in_group(self):
        """Group with no favourite files should sort normally by secondary criterion."""
        files = [
            File(path="/deep/file.txt", size=100, path_depth=3, is_from_fav_dir=False),
            File(path="/shallow/file.txt", size=100, path_depth=1, is_from_fav_dir=False),
        ]
        group = DuplicateGroup(size=100, files=files)

        Sorter.sort_files_inside_groups([group])

        # Sort by path depth (no favourites to prioritize)
        assert group.files[0].path_depth == 1
        assert group.files[1].path_depth == 3


# =============================================================================
# 3. SHORTEST_PATH SORT ORDER
# =============================================================================
class TestSorterShortestPathOrder:
    """Test SHORTEST_PATH sort order behavior."""

    def test_shortest_path_first_explicit(self):
        """Explicit SHORTEST_PATH should sort by path_depth ascending."""
        files = [
            File(path="/a/b/c/d/file.txt", size=100, path_depth=4),
            File(path="/a/file.txt", size=100, path_depth=1),
            File(path="/a/b/c/file.txt", size=100, path_depth=3),
            File(path="/a/b/file.txt", size=100, path_depth=2),
        ]
        group = DuplicateGroup(size=100, files=files)

        Sorter.sort_files_inside_groups([group], SortOrder.SHORTEST_PATH)

        # Should be sorted by path_depth ascending
        depths = [f.path_depth for f in group.files]
        assert depths == [1, 2, 3, 4]

    def test_same_path_depth_sorted_by_filename_length(self):
        """Files with same path_depth should be sorted by filename length."""
        files = [
            File(path="/dir/longfilename.txt", size=100, name="longfilename.txt", path_depth=1),
            File(path="/dir/short.txt", size=100, name="short.txt", path_depth=1),
            File(path="/dir/medium.txt", size=100, name="medium.txt", path_depth=1),
        ]
        group = DuplicateGroup(size=100, files=files)

        Sorter.sort_files_inside_groups([group], SortOrder.SHORTEST_PATH)

        # Same depth, so sort by filename length
        names = [f.name for f in group.files]
        assert names == ["short.txt", "medium.txt", "longfilename.txt"]

    def test_path_depth_tiebreaker_with_favourites(self):
        """Path depth should be tiebreaker after favourite priority."""
        files = [
            File(path="/fav/deep/file.txt", size=100, path_depth=3, is_from_fav_dir=True),
            File(path="/normal/shallow/file.txt", size=100, path_depth=1, is_from_fav_dir=False),
            File(path="/fav/shallow/file.txt", size=100, path_depth=1, is_from_fav_dir=True),
        ]
        group = DuplicateGroup(size=100, files=files)

        Sorter.sort_files_inside_groups([group], SortOrder.SHORTEST_PATH)

        # Favourites first (regardless of depth), then by depth
        assert group.files[0].is_from_fav_dir is True
        assert group.files[0].path_depth == 1  # Shallow favourite first
        assert group.files[1].is_from_fav_dir is True
        assert group.files[1].path_depth == 3  # Deep favourite second
        assert group.files[2].is_from_fav_dir is False


# =============================================================================
# 4. SHORTEST_FILENAME SORT ORDER
# =============================================================================
class TestSorterShortestFilenameOrder:
    """Test SHORTEST_FILENAME sort order behavior."""

    def test_shortest_filename_first_explicit(self):
        """Explicit SHORTEST_FILENAME should sort by filename length ascending."""
        files = [
            File(path="/dir/verylongname.txt", size=100, name="verylongname.txt"),
            File(path="/dir/a.txt", size=100, name="a.txt"),
            File(path="/dir/mediumname.txt", size=100, name="mediumname.txt"),
        ]
        group = DuplicateGroup(size=100, files=files)

        Sorter.sort_files_inside_groups([group], SortOrder.SHORTEST_FILENAME)

        # Should be sorted by filename length ascending
        names = [f.name for f in group.files]
        assert names == ["a.txt", "mediumname.txt", "verylongname.txt"]

    def test_same_filename_length_sorted_by_path_depth(self):
        """Files with same filename length should be sorted by path_depth."""
        files = [
            File(path="/deep/file.txt", size=100, name="file.txt", path_depth=3),
            File(path="/shallow/file.txt", size=100, name="file.txt", path_depth=1),
            File(path="/medium/file.txt", size=100, name="file.txt", path_depth=2),
        ]
        group = DuplicateGroup(size=100, files=files)

        Sorter.sort_files_inside_groups([group], SortOrder.SHORTEST_FILENAME)

        # Same name length, so sort by path depth
        depths = [f.path_depth for f in group.files]
        assert depths == [1, 2, 3]

    def test_filename_sort_with_favourites(self):
        """Favourite priority should override filename sort order."""
        files = [
            File(path="/normal/short.txt", size=100, name="short.txt", is_from_fav_dir=False),
            File(path="/fav/verylong.txt", size=100, name="verylong.txt", is_from_fav_dir=True),
        ]
        group = DuplicateGroup(size=100, files=files)

        Sorter.sort_files_inside_groups([group], SortOrder.SHORTEST_FILENAME)

        # Favourite first despite longer filename
        assert group.files[0].is_from_fav_dir is True
        assert group.files[0].name == "verylong.txt"
        assert group.files[1].is_from_fav_dir is False


# =============================================================================
# 5. DEFAULT SORT ORDER BEHAVIOR
# =============================================================================
class TestSorterDefaultSortOrder:
    """Test default sort order behavior when None is passed."""

    def test_none_sort_order_defaults_to_shortest_path(self):
        """None sort_order should default to SHORTEST_PATH."""
        files = [
            File(path="/deep/file.txt", size=100, path_depth=2),
            File(path="/shallow/file.txt", size=100, path_depth=1),
        ]
        group = DuplicateGroup(size=100, files=files)

        Sorter.sort_files_inside_groups([group], sort_order=None)

        # Should default to SHORTEST_PATH behavior
        assert group.files[0].path_depth == 1
        assert group.files[1].path_depth == 2

    def test_empty_groups_with_none_sort_order(self):
        """Empty groups list with None sort_order should not cause errors."""
        Sorter.sort_files_inside_groups([], sort_order=None)
        # Should not raise any exception

    def test_group_with_single_file_none_sort_order(self):
        """Single file group with None sort_order should not cause errors."""
        files = [File(path="/single/file.txt", size=100, path_depth=1)]
        group = DuplicateGroup(size=100, files=files)

        Sorter.sort_files_inside_groups([group], sort_order=None)

        # Single file should remain unchanged
        assert len(group.files) == 1
        assert group.files[0].path == "/single/file.txt"


# =============================================================================
# 6. EDGE CASES
# =============================================================================
class TestSorterEdgeCases:
    """Test edge cases and special scenarios."""

    def test_single_file_group_unchanged(self):
        """Single file groups should remain unchanged after sorting."""
        original_file = File(path="/single/file.txt", size=100, path_depth=1)
        files = [original_file]
        group = DuplicateGroup(size=100, files=files)

        Sorter.sort_files_inside_groups([group])

        assert len(group.files) == 1
        assert group.files[0] is original_file

    def test_empty_files_list_in_group(self):
        """Group with empty files list should not cause errors."""
        group = DuplicateGroup(size=100, files=[])

        # Should not raise any exception
        Sorter.sort_files_inside_groups([group])
        assert group.files == []

    def test_large_group_sorting(self):
        """Large groups (100+ files) should sort correctly."""
        files = []
        for i in range(100):
            files.append(File(
                path=f"/dir{i}/file.txt",
                size=100,
                path_depth=i % 10,
                is_from_fav_dir=(i % 3 == 0)
            ))
        group = DuplicateGroup(size=100, files=files)

        Sorter.sort_files_inside_groups([group])

        # All favourites should be first
        favourite_count = sum(1 for f in files if f.is_from_fav_dir)
        for i in range(favourite_count):
            assert group.files[i].is_from_fav_dir is True
        for i in range(favourite_count, len(group.files)):
            assert group.files[i].is_from_fav_dir is False

    def test_files_with_same_all_criteria(self):
        """Files identical in all sorting criteria should maintain stable order."""
        files = [
            File(path="/dir/a.txt", size=100, name="a.txt", path_depth=1, is_from_fav_dir=False),
            File(path="/dir/b.txt", size=100, name="b.txt", path_depth=1, is_from_fav_dir=False),
            File(path="/dir/c.txt", size=100, name="c.txt", path_depth=1, is_from_fav_dir=False),
        ]
        group = DuplicateGroup(size=100, files=files)
        original_order = [f.path for f in files]

        Sorter.sort_files_inside_groups([group])

        # Python's sort is stable, so order should be preserved for equal keys
        sorted_order = [f.path for f in group.files]
        assert sorted_order == original_order, "Stable sort should preserve original order for equal keys"
        assert len(group.files) == 3

    def test_mixed_favourite_and_non_favourite_with_same_depth(self):
        """Mixed favourite/non-favourite with same path depth."""
        files = [
            File(path="/dir/nonfav1.txt", size=100, path_depth=2, is_from_fav_dir=False),
            File(path="/dir/fav1.txt", size=100, path_depth=2, is_from_fav_dir=True),
            File(path="/dir/nonfav2.txt", size=100, path_depth=2, is_from_fav_dir=False),
            File(path="/dir/fav2.txt", size=100, path_depth=2, is_from_fav_dir=True),
        ]
        group = DuplicateGroup(size=100, files=files)

        Sorter.sort_files_inside_groups([group])

        # All favourites first, then non-favourites
        assert group.files[0].is_from_fav_dir is True
        assert group.files[1].is_from_fav_dir is True
        assert group.files[2].is_from_fav_dir is False
        assert group.files[3].is_from_fav_dir is False

    def test_sort_order_enum_values(self):
        """All SortOrder enum values should work correctly."""
        for sort_order in SortOrder:
            files = [
                File(path="/deep/file.txt", size=100, name="file.txt", path_depth=2),
                File(path="/shallow/file.txt", size=100, name="file.txt", path_depth=1),
            ]
            group = DuplicateGroup(size=100, files=files)

            # Should not raise any exception for any valid SortOrder
            Sorter.sort_files_inside_groups([group], sort_order)
            assert len(group.files) == 2


# =============================================================================
# 7. INTEGRATION WITH DUPLICATE GROUPS
# =============================================================================
class TestSorterDuplicateGroupIntegration:
    """Test Sorter integration with DuplicateGroup properties."""

    def test_sort_preserves_group_size(self):
        """Sorting should not change the group's size property."""
        files = [
            File(path="/a/file.txt", size=100),
            File(path="/b/file.txt", size=100),
        ]
        group = DuplicateGroup(size=100, files=files)
        original_size = group.size

        Sorter.sort_files_inside_groups([group])

        assert group.size == original_size

    def test_sort_preserves_duplicate_count(self):
        """Sorting should not change the group's duplicate_count property."""
        files = [
            File(path="/a/file.txt", size=100),
            File(path="/b/file.txt", size=100),
            File(path="/c/file.txt", size=100),
        ]
        group = DuplicateGroup(size=100, files=files)
        original_count = group.duplicate_count

        Sorter.sort_files_inside_groups([group])

        assert group.duplicate_count == original_count
        assert group.duplicate_count == 3

    def test_sort_preserves_is_duplicate_status(self):
        """Sorting should not change the group's is_duplicate() status."""
        files = [
            File(path="/a/file.txt", size=100),
            File(path="/b/file.txt", size=100),
        ]
        group = DuplicateGroup(size=100, files=files)
        original_is_duplicate = group.is_duplicate()

        Sorter.sort_files_inside_groups([group])

        assert group.is_duplicate() == original_is_duplicate
        assert group.is_duplicate() is True

    def test_sort_with_group_add_file_method(self):
        """Sorting should work correctly after using group.add_file()."""
        group = DuplicateGroup(size=100, files=[])
        group.add_file(File(path="/deep/file.txt", size=100, path_depth=2))
        group.add_file(File(path="/shallow/file.txt", size=100, path_depth=1))

        Sorter.sort_files_inside_groups([group])

        assert group.files[0].path_depth == 1
        assert group.files[1].path_depth == 2


# =============================================================================
# 8. PERFORMANCE AND STABILITY
# =============================================================================
class TestSorterPerformance:
    """Test sorting performance and stability."""

    def test_sort_is_stable(self):
        """Sorting should be stable (preserve order of equal elements)."""
        # Create files with IDENTICAL sorting keys (same depth, same name length)
        files = []
        for i in range(10):
            # All files have same path_depth (1) and same name length (9 chars: "fileX.txt")
            files.append(File(
                path=f"/dir/file{i}.txt",
                size=100,
                name=f"file{i}.txt",  # All are 9 characters
                path_depth=1,
                is_from_fav_dir=False
            ))
        group = DuplicateGroup(size=100, files=files)
        original_order = [f.path for f in files]

        Sorter.sort_files_inside_groups([group])

        # Stable sort should preserve original order for equal keys
        sorted_order = [f.path for f in group.files]

        # ASSERT: Original order must be preserved (Python's sort is stable)
        assert sorted_order == original_order, \
            f"Stable sort failed: order changed from {original_order} to {sorted_order}"

    def test_sort_deterministic(self):
        """Sorting should be deterministic (same input = same output)."""
        results = []

        for _ in range(5):
            # Create fresh File objects each iteration to verify determinism
            group = DuplicateGroup(size=100, files=[
                File(path="/c/file.txt", size=100, path_depth=3),
                File(path="/a/file.txt", size=100, path_depth=1),
                File(path="/b/file.txt", size=100, path_depth=2),
            ])
            Sorter.sort_files_inside_groups([group])
            results.append([f.path for f in group.files])

        # All runs should produce identical results
        assert all(r == results[0] for r in results), \
            f"Sort is non-deterministic: got {results}"