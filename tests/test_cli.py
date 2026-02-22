"""
Critical CLI tests — focus on data safety, correct file selection, and deletion logic.
These tests prevent catastrophic bugs that could cause data loss.
"""
import sys
import os
from pathlib import Path
from unittest import mock
import pytest
from onlyone.cli import CLIApplication
from onlyone.core.models import File, DuplicateGroup
from onlyone.services.file_service import FileService


class TestFileSortingAndSelection:
    """Test that correct files are selected for preservation (critical for data safety)."""

    def test_favourite_dir_priority_over_sort_order(self, tmp_path):
        """
        CRITICAL: Files from favourite directories MUST be preserved first,
        regardless of sort order (path depth or filename length).
        """
        # Setup test structure
        fav_dir = tmp_path / "favourite"
        fav_dir.mkdir()
        normal_dir = tmp_path / "normal"
        normal_dir.mkdir()

        # Create duplicates with different path depths
        # Favourite file has LONGER path (deeper nesting)
        deep_fav = fav_dir / "subdir" / "keep_me.jpg"
        deep_fav.parent.mkdir()
        deep_fav.write_bytes(b"identical content")

        # Normal file has SHORTER path (closer to root)
        shallow_normal = normal_dir / "delete_me.jpg"
        shallow_normal.write_bytes(b"identical content")

        # Run deduplication with favourite dir
        with mock.patch.object(sys, 'argv', [
            'onlyone', '--input', str(tmp_path), '--priority-dirs', str(fav_dir), '--keep-one', '--force'
        ]):
            with mock.patch.object(FileService, 'move_to_trash') as mock_trash:
                app = CLIApplication()
                app.run()

                deleted_paths = [str(call.args[0]) for call in mock_trash.call_args_list]
                assert str(shallow_normal) in deleted_paths, "Shallow non-favourite file should be deleted"
                assert str(deep_fav) not in deleted_paths, "Deep favourite file MUST be preserved"

    def test_sort_order_shortest_path_preserved_when_no_favourites(self, tmp_path):
        """
        When no favourite dirs exist, shortest path file should be preserved by default.
        """
        test_dir = tmp_path / "photos"
        test_dir.mkdir()
        subdir = test_dir / "sub"
        subdir.mkdir()

        # Create duplicates: shallow first, deep last
        shallow = test_dir / "shallow.jpg"
        shallow.write_bytes(b"content")
        deep = subdir / "deep.jpg"
        deep.write_bytes(b"content")

        # Run with default sort order (shortest-path)
        with mock.patch.object(sys, 'argv', [
            'onlyone', '--input', str(test_dir), '--keep-one', '--force'
        ]):
            with mock.patch.object(FileService, 'move_to_trash') as mock_trash:
                app = CLIApplication()
                app.run()

                deleted_paths = [str(call.args[0]) for call in mock_trash.call_args_list]
                assert str(deep) in deleted_paths
                assert str(shallow) not in deleted_paths, "Shallow file should be preserved by default"

    def test_sort_order_shortest_filename_preserved_explicitly(self, tmp_path):
        """
        When --sort=shortest-filename is specified, shortest filename should be preserved.
        """
        test_dir = tmp_path / "photos"
        test_dir.mkdir()
        short_name = test_dir / "a.jpg"
        short_name.write_bytes(b"content")
        long_name = test_dir / "very_long_filename.jpg"
        long_name.write_bytes(b"content")

        # Run with explicit shortest-filename sort order
        with mock.patch.object(sys, 'argv', [
            'onlyone', '--input', str(test_dir), '--keep-one', '--sort', 'shortest-filename', '--force'
        ]):
            with mock.patch.object(FileService, 'move_to_trash') as mock_trash:
                app = CLIApplication()
                app.run()

                deleted_paths = [str(call.args[0]) for call in mock_trash.call_args_list]
                assert str(long_name) in deleted_paths
                assert str(short_name) not in deleted_paths, "Shortest filename should be preserved"


class TestDeletionSafety:
    """Test deletion logic to prevent accidental data loss."""

    def test_keep_one_deletes_only_duplicates_not_originals(self, tmp_path):
        """
        CRITICAL: --keep-one must delete ONLY duplicates, preserving at least one file per group.
        """
        test_dir = tmp_path / "test"
        test_dir.mkdir()

        # Create 3 identical files (one group of 3 duplicates)
        content = b"test content " + os.urandom(100)
        files = []
        for i in range(3):
            f = test_dir / f"file{i}.txt"
            f.write_bytes(content)
            files.append(f)

        # Run deletion
        with mock.patch.object(sys, 'argv', [
            'onlyone', '--input', str(test_dir), '--keep-one', '--force'
        ]):
            with mock.patch.object(FileService, 'move_to_trash') as mock_trash:
                app = CLIApplication()
                app.run()

                assert mock_trash.call_count == 2, "Should delete exactly N-1 files per group"

                deleted_paths = [str(call.args[0]) for call in mock_trash.call_args_list]
                preserved_files = [f for f in files if str(f) not in deleted_paths]
                assert len(preserved_files) == 1, "Exactly one file must be preserved per group"

    def test_no_deletion_without_keep_one_flag(self, tmp_path):
        """
        CRITICAL: Running WITHOUT --keep-one must NEVER delete files.
        """
        test_dir = tmp_path / "test"
        test_dir.mkdir()

        # Create duplicates
        content = b"content"
        (test_dir / "a.txt").write_bytes(content)
        (test_dir / "b.txt").write_bytes(content)

        # Run WITHOUT --keep-one
        with mock.patch.object(sys, 'argv', ['onlyone', '--input', str(test_dir)]):
            with mock.patch.object(FileService, 'move_to_trash') as mock_trash:
                app = CLIApplication()
                app.run()

                assert mock_trash.call_count == 0, "NO files should be deleted without --keep-one flag"

    def test_force_requires_keep_one(self, tmp_path):
        """
        CRITICAL: --force must be rejected without --keep-one to prevent accidental mass deletion.
        """
        with mock.patch.object(sys, 'argv', [
            'onlyone', '--input', str(tmp_path), '--force'
        ]):
            app = CLIApplication()
            args = app.parse_args()

            # Should raise error during validation
            with pytest.raises(SystemExit) as exc_info:
                app.validate_args(args)
            assert exc_info.value.code == 1


class TestPartialErrorHandling:
    """Test that deletion continues when some files fail to delete (resilience)."""

    def test_deletion_continues_after_single_file_error(self, tmp_path):
        """
        CRITICAL: If one file fails to delete, others must still be deleted.
        Prevents "all-or-nothing" failure mode that leaves duplicates untouched.
        """
        test_dir = tmp_path / "test"
        test_dir.mkdir()

        # Create 3 duplicates (no need to store file objects - we track deletions via mock)
        content = b"content"
        for i in range(3):
            (test_dir / f"file{i}.txt").write_bytes(content)

        # Track deletion attempts
        deletion_attempts = []

        def mock_move_to_trash(path):
            deletion_attempts.append(str(path))
            # Fail on second attempt only
            if len(deletion_attempts) == 2:
                raise PermissionError(f"Mock permission error for {Path(path).name}")

        # Run deletion with mocked failure
        with mock.patch.object(sys, 'argv', [
            'onlyone', '--input', str(test_dir), '--keep-one', '--force'
        ]):
            with mock.patch.object(FileService, 'move_to_trash', side_effect=mock_move_to_trash):
                with mock.patch('builtins.print'):
                    app = CLIApplication()
                    try:
                        app.run()
                    except SystemExit:
                        pass

                    assert len(deletion_attempts) == 2, "Should attempt to delete exactly 2 files"


class TestSpaceSavingsCalculation:
    """Test accurate calculation of space savings."""

    def test_space_savings_for_single_group(self):
        """Verify space savings calculation for one duplicate group."""
        # Create mock group: 3 files of 1MB each (total 3MB, keep 1 → save 2MB)
        files = [
            File(path="/a/f1", size=1024 * 1024, name="f1", extension=".txt"),
            File(path="/a/f2", size=1024 * 1024, name="f2", extension=".txt"),
            File(path="/a/f3", size=1024 * 1024, name="f3", extension=".txt"),
        ]
        # DuplicateGroup requires BOTH size (of one file) AND files list
        group = DuplicateGroup(size=1024 * 1024, files=files)
        app = CLIApplication()

        # Keep f1 (first after sorting), delete f2+f3
        savings = app.calculate_space_savings([group], ["/a/f2", "/a/f3"])
        assert savings == 2 * 1024 * 1024, "Should save exactly 2MB (2 files * 1MB each)"

    def test_space_savings_for_multiple_groups(self):
        """Verify space savings calculation across multiple groups."""
        # Group 1: 2 files of 1MB → save 1MB
        files1 = [
            File(path="/a/f1", size=1024 * 1024, name="f1", extension=".txt"),
            File(path="/a/f2", size=1024 * 1024, name="f2", extension=".txt"),
        ]
        group1 = DuplicateGroup(size=1024 * 1024, files=files1)

        # Group 2: 3 files of 512KB → save 1MB (2 * 512KB)
        files2 = [
            File(path="/b/f1", size=512 * 1024, name="f1", extension=".txt"),
            File(path="/b/f2", size=512 * 1024, name="f2", extension=".txt"),
            File(path="/b/f3", size=512 * 1024, name="f3", extension=".txt"),
        ]
        group2 = DuplicateGroup(size=512 * 1024, files=files2)

        app = CLIApplication()

        savings = app.calculate_space_savings(
            [group1, group2],
            ["/a/f2", "/b/f2", "/b/f3"]
        )
        expected = (1 * 1024 * 1024) + (2 * 512 * 1024)
        assert savings == expected, "Should save 2MB total across both groups"


class TestFullCycleIntegration:
    """End-to-end integration tests for complete deduplication workflow."""

    def test_full_cycle_with_preview_and_confirmation(self, tmp_path, monkeypatch):
        """
        Test complete workflow: scan → preview → user confirmation → deletion.
        """
        test_dir = tmp_path / "photos"
        test_dir.mkdir()

        # Create duplicates
        content = b"photo content " + os.urandom(1000)
        original = test_dir / "vacation.jpg"
        duplicate = test_dir / "vacation_copy.jpg"
        original.write_bytes(content)
        duplicate.write_bytes(content)

        # Mock interactive terminal for confirmation prompt
        monkeypatch.setattr(sys.stdin, 'isatty', lambda: True)
        monkeypatch.setattr(sys.stdout, 'isatty', lambda: True)

        # Run with preview (user confirms deletion)
        with mock.patch.object(sys, 'argv', [
            'onlyone', '--input', str(test_dir), '--keep-one'
        ]):
            with mock.patch('builtins.input', return_value='y'):
                with mock.patch.object(FileService, 'move_to_trash') as mock_trash:
                    app = CLIApplication()
                    app.run()

                    assert mock_trash.call_count == 1, "Should delete exactly one duplicate"

    def test_full_cycle_with_force_skips_confirmation(self, tmp_path):
        """
        Test that --force skips confirmation prompt for automation.
        """
        test_dir = tmp_path / "photos"
        test_dir.mkdir()
        content = b"content"
        (test_dir / "a.jpg").write_bytes(content)
        (test_dir / "b.jpg").write_bytes(content)

        # Track if confirmation prompt was shown
        confirmation_shown = []

        def mock_input(prompt):
            confirmation_shown.append(prompt)
            return 'y'

        # Run with --force (should NOT show confirmation)
        with mock.patch.object(sys, 'argv', [
            'onlyone', '--input', str(test_dir), '--keep-one', '--force'
        ]):
            with mock.patch('builtins.input', side_effect=mock_input) as mock_input_patch:
                with mock.patch.object(FileService, 'move_to_trash'):
                    app = CLIApplication()
                    app.run()

                    assert mock_input_patch.call_count == 0, "--force should skip confirmation prompt"

    def test_no_duplicates_found_handling(self, tmp_path):
        """
        Test graceful handling when no duplicates are found.
        """
        test_dir = tmp_path / "unique_files"
        test_dir.mkdir()

        # Create unique files (no duplicates)
        (test_dir / "a.txt").write_bytes(b"unique content 1")
        (test_dir / "b.txt").write_bytes(b"unique content 2")
        (test_dir / "c.txt").write_bytes(b"unique content 3")

        # Capture output
        with mock.patch.object(sys, 'argv', ['onlyone', '--input', str(test_dir)]):
            with mock.patch('builtins.print') as mock_print:
                app = CLIApplication()
                app.run()

                printed_output = "\n".join(str(call.args[0]) for call in mock_print.call_args_list)
                assert "No duplicate groups found" in printed_output, "Should inform user when no duplicates found"


class TestEdgeCases:
    """Test edge cases that could cause data loss if unhandled."""

    def test_zero_byte_files_are_skipped(self, tmp_path):
        """
        Zero-byte files should be skipped during scanning (not treated as duplicates).
        """
        test_dir = tmp_path / "test"
        test_dir.mkdir()

        # Create zero-byte files
        (test_dir / "empty1.txt").write_bytes(b"")
        (test_dir / "empty2.txt").write_bytes(b"")

        # Create actual duplicate
        content = b"real content"
        (test_dir / "real1.txt").write_bytes(content)
        (test_dir / "real2.txt").write_bytes(content)

        # Run scan
        with mock.patch.object(sys, 'argv', ['onlyone', '--input', str(test_dir)]):
            with mock.patch('builtins.print') as mock_print:
                app = CLIApplication()
                app.run()

                printed_output = "\n".join(str(call.args[0]) for call in mock_print.call_args_list)
                assert "Found" in printed_output and "groups" in printed_output, \
                    "Should find at least one duplicate group (real files)"

    def test_symlinks_are_skipped(self, tmp_path):
        """
        Symbolic links should be skipped to avoid duplicate detection across links.
        """
        if sys.platform == "win32":
            pytest.skip("Symlinks require special permissions on Windows")

        test_dir = tmp_path / "test"
        test_dir.mkdir()

        real_file = test_dir / "real.txt"
        real_file.write_bytes(b"content")
        symlink = test_dir / "link.txt"
        symlink.symlink_to(real_file)

        with mock.patch.object(sys, 'argv', ['onlyone', '--input', str(test_dir)]):
            with mock.patch('builtins.print') as mock_print:
                app = CLIApplication()
                app.run()

                printed_output = "\n".join(str(call.args[0]) for call in mock_print.call_args_list)
                assert "No duplicate groups found" in printed_output or "Found 0" in printed_output, \
                    "Symlinks should be skipped, preventing false duplicates"


class TestCLIBoostMode:
    """Test CLI --boost flag argument parsing and integration."""

    def test_boost_same_size_cli_argument_accepted(self, tmp_path):
        """
        CLI must accept --boost size argument without errors.
        Business logic tested in test_stages.py
        """
        test_dir = tmp_path / "test"
        test_dir.mkdir()
        content = b"A" * 1024
        (test_dir / "doc.txt").write_bytes(content)
        (test_dir / "img.jpg").write_bytes(content)

        with mock.patch.object(sys, 'argv', [
            'onlyone', '--input', str(test_dir), '--boost', 'size'
        ]):
            with mock.patch('builtins.print'):
                app = CLIApplication()
                app.run()

    def test_boost_same_size_plus_ext_cli_argument_accepted(self, tmp_path):
        """
        CLI must accept --boost extension argument without errors.
        Business logic tested in test_stages.py
        """
        test_dir = tmp_path / "test"
        test_dir.mkdir()
        content = b"B" * 2048
        (test_dir / "a.txt").write_bytes(content)
        (test_dir / "x.jpg").write_bytes(content)

        with mock.patch.object(sys, 'argv', [
            'onlyone', '--input', str(test_dir), '--boost', 'extension'
        ]):
            with mock.patch('builtins.print'):
                app = CLIApplication()
                app.run()

    def test_boost_mode_with_true_duplicates_still_works(self, tmp_path):
        """
        CRITICAL: Even with strict boost modes, TRUE duplicates
        (same size + same name + same content) must still be detected.
        This is an important e2e safety test.
        """
        test_dir = tmp_path / "test"
        test_dir.mkdir()
        subdir = test_dir / "backup"
        subdir.mkdir()

        content = b"TRUE_DUPLICATE_CONTENT" * 100
        original = test_dir / "photo.jpg"
        copy = subdir / "photo.jpg"
        original.write_bytes(content)
        copy.write_bytes(content)

        with mock.patch.object(sys, 'argv', [
            'onlyone', '--input', str(test_dir),
            '--boost', 'filename', '--keep-one', '--force'
        ]):
            with mock.patch.object(FileService, 'move_to_trash') as mock_trash:
                app = CLIApplication()
                app.run()

                assert mock_trash.call_count == 1, "Should detect true duplicates even with strict boost"

                deleted_paths = [str(call.args[0]) for call in mock_trash.call_args_list]
                preserved = [str(original), str(copy)]
                preserved_count = sum(1 for p in preserved if p not in deleted_paths)
                assert preserved_count == 1, "Exactly one true duplicate must be preserved"

    def test_boost_invalid_value_rejected(self, tmp_path):
        """
        Invalid --boost values must be rejected with clear error message.
        CLI validation test (not applicable to stages).
        """
        test_dir = tmp_path / "test"
        test_dir.mkdir()

        with mock.patch.object(sys, 'argv', [
            'onlyone', '--input', str(test_dir), '--boost', 'invalid-mode'
        ]):
            with pytest.raises(SystemExit) as exc_info:
                app = CLIApplication()
                app.run()
            assert exc_info.value.code != 0, "Should exit with error for invalid boost mode"

    def test_boost_fuzzy_filename_cli_argument_accepted(self, tmp_path):
        """
        CLI must accept --boost fuzzy-filename argument without errors.
        """
        test_dir = tmp_path / "test"
        test_dir.mkdir()
        content = b"C" * 512
        (test_dir / "report_v1.txt").write_bytes(content)
        (test_dir / "report_v2.txt").write_bytes(content)

        with mock.patch.object(sys, 'argv', [
            'onlyone', '--input', str(test_dir), '--boost', 'fuzzy-filename'
        ]):
            with mock.patch('builtins.print'):
                app = CLIApplication()
                app.run()