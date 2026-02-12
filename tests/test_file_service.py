"""
Tests for file service — critical for safe file deletion.
These tests verify files are moved to trash (not permanently deleted).
"""
import os
import sys
import pytest
from pathlib import Path
from deduplicator.services.file_service import FileService


class TestMoveToTrash:
    """Test safe file deletion via system trash."""

    def test_moves_file_to_trash(self, tmp_path):
        """
        CRITICAL: File must disappear from original location after move_to_trash().
        We don't verify trash location (OS-dependent), only that:
        1. Original file is gone
        2. No exception was raised
        """
        test_file = tmp_path / "test.txt"
        test_file.write_text("content to delete")

        # Verify file exists before deletion
        assert test_file.exists(), "Test file must exist before deletion"

        # Perform deletion
        FileService.move_to_trash(str(test_file))

        # Verify file no longer exists in original location
        assert not test_file.exists(), "File must be removed from original location after trash"

    def test_raises_runtime_error_for_nonexistent_file(self, tmp_path):
        """
        send2trash raises FileNotFoundError which is wrapped as RuntimeError by FileService.
        We test the actual behavior of our wrapper, not send2trash internals.
        """
        nonexistent = tmp_path / "does_not_exist.txt"

        with pytest.raises(RuntimeError, match="File not found"):
            FileService.move_to_trash(str(nonexistent))

    def test_handles_files_with_spaces_in_name(self, tmp_path):
        """Files with spaces in path must be trashed correctly."""
        spaced_file = tmp_path / "my photo.jpg"
        spaced_file.write_text("content")

        assert spaced_file.exists()
        FileService.move_to_trash(str(spaced_file))
        assert not spaced_file.exists()

    def test_handles_files_with_unicode_in_name(self, tmp_path):
        """Files with Unicode characters must be trashed correctly."""
        # Skip on Windows if filesystem doesn't support Unicode well
        if sys.platform == "win32":
            pytest.skip("Unicode filename handling may be flaky on Windows")

        unicode_file = tmp_path / "фото.jpg"
        unicode_file.write_text("content")

        assert unicode_file.exists()
        FileService.move_to_trash(str(unicode_file))
        assert not unicode_file.exists()

    def test_handles_nested_directories(self, tmp_path):
        """Files in subdirectories must be trashed correctly."""
        subdir = tmp_path / "photos" / "vacation"
        subdir.mkdir(parents=True)
        nested_file = subdir / "beach.jpg"
        nested_file.write_text("content")

        assert nested_file.exists()
        FileService.move_to_trash(str(nested_file))
        assert not nested_file.exists()

    def test_preserves_other_files_in_directory(self, tmp_path):
        """Trashing one file must not affect siblings in same directory."""
        file1 = tmp_path / "keep_me.txt"
        file2 = tmp_path / "delete_me.txt"

        file1.write_text("preserve this")
        file2.write_text("delete this")

        assert file1.exists() and file2.exists()

        # Trash only file2
        FileService.move_to_trash(str(file2))

        # Verify file1 still exists, file2 is gone
        assert file1.exists(), "Sibling file must not be affected by deletion"
        assert not file2.exists(), "Deleted file must be gone"

    @pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific trash path")
    def test_linux_trash_location_exists(self, tmp_path):
        """
        On Linux, verify trash directory exists after deletion (sanity check).
        Note: We don't verify exact file location — send2trash handles this.
        """
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        FileService.move_to_trash(str(test_file))

        # Verify Linux trash directory exists (at least one of standard locations)
        home_trash = Path.home() / ".local" / "share" / "Trash"
        assert home_trash.exists() or (Path("/") / "root" / ".local" / "share" / "Trash").exists(), \
            "Linux trash directory should exist after deletion"

    @pytest.mark.xfail(
        reason="OS-dependent behavior: read-only files may fail to trash on some systems",
        raises=RuntimeError,
        strict=False
    )
    def test_handles_readonly_files(self, tmp_path):
        """
        Read-only files MAY be trashed on some systems but fail on others.
        This test is marked xfail because behavior depends on OS permissions.
        Critical requirement: file must NOT be permanently deleted if trashing fails.
        """
        readonly_file = tmp_path / "readonly.txt"
        readonly_file.write_text("content")

        # Make file read-only
        readonly_file.chmod(0o444)  # Read-only for all users

        initial_exists = readonly_file.exists()
        try:
            FileService.move_to_trash(str(readonly_file))
            # If successful, file should be gone
            assert not readonly_file.exists(), "Read-only file should be trashed successfully"
        except RuntimeError as e:
            # If failed, file MUST still exist (no permanent deletion!)
            assert readonly_file.exists(), \
                f"CRITICAL: File was permanently deleted after trashing failed! Error: {e}"
            # Expected failure on some systems - not a bug if file still exists
            pytest.xfail(f"Trashing read-only file failed (expected on some OS): {e}")

    def test_handles_large_files(self, tmp_path):
        """Large files (10MB) should be trashed without issues."""
        large_file = tmp_path / "large.bin"
        # Write 10MB of random data
        large_file.write_bytes(os.urandom(10 * 1024 * 1024))

        assert large_file.exists()
        initial_size = large_file.stat().st_size

        FileService.move_to_trash(str(large_file))
        assert not large_file.exists(), f"Large file ({initial_size} bytes) should be trashed"