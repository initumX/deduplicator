"""
Tests for duplicate service logic — validates correct file preservation behavior.
These tests verify that DuplicateService correctly identifies files to delete,
preserving ONLY the first file in pre-sorted groups (sorting is handled upstream).
"""
import pytest
from highlander.core.models import File, DuplicateGroup
from highlander.services.duplicate_service import DuplicateService


class TestKeepOnlyOneFilePerGroup:
    """Test that service correctly identifies files to delete from pre-sorted groups."""

    def test_identifies_correct_files_to_delete_in_group(self):
        """
        Service MUST mark ONLY files after the first one for deletion.
        First file is always preserved (upstream sorting determines which file is first).
        """
        # Group is ALREADY sorted by upstream component (e.g., DeduplicationCommand)
        # First file = preserved, all others = marked for deletion
        files = [
            File(path="/preserve/me.jpg", size=100, is_from_fav_dir=True),  # ← Preserved (first)
            File(path="/delete/this1.jpg", size=100, is_from_fav_dir=False),  # ← Deleted
            File(path="/delete/this2.jpg", size=100, is_from_fav_dir=False),  # ← Deleted
        ]
        group = DuplicateGroup(size=100, files=files)

        files_to_delete, _ = DuplicateService.keep_only_one_file_per_group([group])

        # Verify ONLY files after first are marked for deletion
        assert "/preserve/me.jpg" not in files_to_delete
        assert "/delete/this1.jpg" in files_to_delete
        assert "/delete/this2.jpg" in files_to_delete

    def test_handles_multiple_groups_independently(self):
        """Each group is processed independently — files after first marked for deletion in each."""
        group1 = DuplicateGroup(size=100, files=[
            File(path="/g1/preserve.jpg", size=100, is_from_fav_dir=True),  # ← Preserve
            File(path="/g1/delete.jpg", size=100, is_from_fav_dir=False),    # ← Delete
        ])
        group2 = DuplicateGroup(size=200, files=[
            File(path="/g2/preserve.jpg", size=200, is_from_fav_dir=False),  # ← Preserve
            File(path="/g2/delete1.jpg", size=200, is_from_fav_dir=False),   # ← Delete
            File(path="/g2/delete2.jpg", size=200, is_from_fav_dir=False),   # ← Delete
        ])

        files_to_delete, _ = DuplicateService.keep_only_one_file_per_group([group1, group2])

        # Group 1: only second file marked for deletion
        assert "/g1/preserve.jpg" not in files_to_delete
        assert "/g1/delete.jpg" in files_to_delete

        # Group 2: second and third files marked for deletion
        assert "/g2/preserve.jpg" not in files_to_delete
        assert "/g2/delete1.jpg" in files_to_delete
        assert "/g2/delete2.jpg" in files_to_delete

    def test_skips_deletion_for_single_file_groups(self):
        """Groups with only one file have nothing to delete."""
        single_file = File(path="/single.jpg", size=100, is_from_fav_dir=False)
        group = DuplicateGroup(size=100, files=[single_file])

        files_to_delete, _ = DuplicateService.keep_only_one_file_per_group([group])

        assert len(files_to_delete) == 0  # Nothing to delete

    def test_handles_empty_groups_safely(self):
        """Empty groups produce no deletions."""
        group = DuplicateGroup(size=100, files=[])

        files_to_delete, _ = DuplicateService.keep_only_one_file_per_group([group])

        assert len(files_to_delete) == 0

    def test_marks_all_but_first_favourite_for_deletion(self):
        """
        When multiple favourite files exist in a pre-sorted group,
        ONLY the first is preserved — all others (even favourites) are marked for deletion.
        """
        # Group pre-sorted: favourites first (newest favourite first)
        files = [
            File(path="/fav/newest.jpg", size=100, is_from_fav_dir=True),   # ← Preserve (first)
            File(path="/fav/oldest.jpg", size=100, is_from_fav_dir=True),   # ← Delete (second favourite)
            File(path="/normal/middle.jpg", size=100, is_from_fav_dir=False), # ← Delete
        ]
        group = DuplicateGroup(size=100, files=files)

        files_to_delete, _ = DuplicateService.keep_only_one_file_per_group([group])

        # ONLY first file preserved — other favourite IS marked for deletion
        assert "/fav/newest.jpg" not in files_to_delete
        assert "/fav/oldest.jpg" in files_to_delete  # Other favourite correctly marked for deletion
        assert "/normal/middle.jpg" in files_to_delete


class TestRemoveFilesFromGroups:
    """Test removal of specific files from duplicate groups."""

    def test_removes_specified_files_and_preserves_others(self):
        """Specified files are removed; remaining files stay in group."""
        group = DuplicateGroup(size=100, files=[
            File(path="/keep/a.jpg", size=100, is_from_fav_dir=False),
            File(path="/remove/b.jpg", size=100, is_from_fav_dir=False),
            File(path="/keep/c.jpg", size=100, is_from_fav_dir=False),
        ])

        updated_groups = DuplicateService.remove_files_from_groups(
            [group],
            ["/remove/b.jpg"]  # Only remove b.jpg
        )

        # Verify b.jpg is gone, a.jpg and c.jpg remain
        assert len(updated_groups) == 1
        assert len(updated_groups[0].files) == 2
        paths = {f.path for f in updated_groups[0].files}
        assert "/keep/a.jpg" in paths
        assert "/keep/c.jpg" in paths
        assert "/remove/b.jpg" not in paths

    def test_discards_groups_that_become_empty(self):
        """Groups with all files removed are discarded."""
        group = DuplicateGroup(size=100, files=[
            File(path="/a.jpg", size=100, is_from_fav_dir=False),
            File(path="/b.jpg", size=100, is_from_fav_dir=False),
        ])

        updated_groups = DuplicateService.remove_files_from_groups(
            [group],
            ["/a.jpg", "/b.jpg"]  # Remove ALL files
        )

        assert len(updated_groups) == 0  # Group discarded

    def test_ignores_nonexistent_files(self):
        """Removing non-existent files has no effect on groups."""
        group = DuplicateGroup(size=100, files=[
            File(path="/a.jpg", size=100, is_from_fav_dir=False),
            File(path="/b.jpg", size=100, is_from_fav_dir=False),
        ])

        updated_groups = DuplicateService.remove_files_from_groups(
            [group],
            ["/nonexistent.jpg"]  # Not in group
        )

        # Group unchanged
        assert len(updated_groups) == 1
        assert len(updated_groups[0].files) == 2
        paths = {f.path for f in updated_groups[0].files}
        assert paths == {"/a.jpg", "/b.jpg"}


class TestRemoveFilesFromFileList:
    """Test removal of files from flat file list."""

    def test_removes_specified_files(self):
        files = [
            File(path="/keep/a.jpg", size=100, is_from_fav_dir=False),
            File(path="/remove/b.jpg", size=100, is_from_fav_dir=False),
            File(path="/keep/c.jpg", size=100, is_from_fav_dir=False),
        ]

        remaining = DuplicateService.remove_files_from_file_list(
            files,
            ["/remove/b.jpg"]
        )

        assert len(remaining) == 2
        paths = {f.path for f in remaining}
        assert "/keep/a.jpg" in paths
        assert "/keep/c.jpg" in paths
        assert "/remove/b.jpg" not in paths

    def test_handles_empty_removal_list(self):
        files = [File(path="/a.jpg", size=100, is_from_fav_dir=False)]
        remaining = DuplicateService.remove_files_from_file_list(files, [])
        assert len(remaining) == 1
        assert remaining[0].path == "/a.jpg"


class TestUpdateFavouriteStatus:
    """Test updating favourite status for files based on directories."""

    def test_marks_files_in_favourite_dirs(self, tmp_path):
        # Create test directories
        fav1 = tmp_path / "favourite1"
        fav2 = tmp_path / "favourite2"
        normal = tmp_path / "normal"
        fav1.mkdir()
        fav2.mkdir()
        normal.mkdir()

        # Create test files
        files = [
            File(path=str(fav1 / "a.jpg"), size=100, is_from_fav_dir=False),
            File(path=str(fav2 / "b.jpg"), size=100, is_from_fav_dir=False),
            File(path=str(normal / "c.jpg"), size=100, is_from_fav_dir=False),
            File(path=str(fav1 / "sub" / "d.jpg"), size=100, is_from_fav_dir=False),
        ]

        # Update status
        DuplicateService.update_favourite_status(files, [str(fav1), str(fav2)])

        # Verify favourites marked correctly
        assert files[0].is_from_fav_dir is True  # fav1/a.jpg
        assert files[1].is_from_fav_dir is True  # fav2/b.jpg
        assert files[2].is_from_fav_dir is False  # normal/c.jpg
        assert files[3].is_from_fav_dir is True  # fav1/sub/d.jpg (subdirectory of favourite)

    def test_handles_empty_favourite_list(self):
        files = [File(path="/a.jpg", size=100, is_from_fav_dir=True)]
        DuplicateService.update_favourite_status(files, [])
        assert files[0].is_from_fav_dir is False  # Reset to False when no favourites specified