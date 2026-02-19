"""
Tests for CLI argument parsing and validation.
"""
import sys
from unittest import mock
import pytest
from onlyone.cli import CLIApplication
from onlyone.core.models import DeduplicationMode, SortOrder


class TestArgumentParsing:
    """Test CLI argument parsing with argparse."""

    def test_input_flag_variants(self):
        """Test both long (--input) and short (-i) forms."""
        app = CLIApplication()

        # Long form
        with mock.patch.object(sys, 'argv', ['onlyone', '--input', '/tmp/test']):
            args = app.parse_args()
        assert args.input == "/tmp/test"

        # Short form
        with mock.patch.object(sys, 'argv', ['onlyone', '-i', '/tmp/test']):
            args = app.parse_args()
        assert args.input == "/tmp/test"

    def test_extensions_flag_variants(self):
        """Test both long (--extensions) and short (-x) forms with space-separated values."""
        app = CLIApplication()

        # Long form with space-separated values
        with mock.patch.object(sys, 'argv', ['onlyone', '-i', '/tmp', '--extensions', '.jpg', '.png']):
            args = app.parse_args()
        assert args.extensions == [".jpg", ".png"]

        # Short form with space-separated values
        with mock.patch.object(sys, 'argv', ['onlyone', '-i', '/tmp', '-x', '.jpg', '.png', '.gif']):
            args = app.parse_args()
        assert args.extensions == [".jpg", ".png", ".gif"]

        # Test with extensions without dots (should be normalized in create_params)
        with mock.patch.object(sys, 'argv', ['onlyone', '-i', '/tmp', '-x', 'jpg', 'png']):
            args = app.parse_args()
        assert args.extensions == ["jpg", "png"]

        # Test empty extensions (default)
        with mock.patch.object(sys, 'argv', ['onlyone', '-i', '/tmp']):
            args = app.parse_args()
        assert args.extensions == []

    def test_priority_dirs_flag_variants(self):
        """Test both short (-p) and alternative (--priority-dirs) forms."""
        app = CLIApplication()

        # Using -p (short form)
        with mock.patch.object(sys, 'argv', [
            'onlyone', '-i', '/tmp', '-p', '/tmp/dir1', '/tmp/dir2'
        ]):
            args = app.parse_args()
        assert args.priority_dirs == ["/tmp/dir1", "/tmp/dir2"]

        # Using --priority-dirs (alternative form)
        with mock.patch.object(sys, 'argv', [
            'onlyone', '-i', '/tmp', '--priority-dirs', '/tmp/dir1', '/tmp/dir2'
        ]):
            args = app.parse_args()
        assert args.priority_dirs == ["/tmp/dir1", "/tmp/dir2"]

    def test_mode_flag(self):
        """Test --mode flag with valid values."""
        app = CLIApplication()

        for mode in ["fast", "normal", "full"]:
            with mock.patch.object(sys, 'argv', ['onlyone', '-i', '/tmp', '--mode', mode]):
                args = app.parse_args()
            assert args.mode == mode

    def test_invalid_mode_flag(self):
        """Test that invalid mode values are rejected by argparse."""
        app = CLIApplication()

        with mock.patch.object(sys, 'argv', ['onlyone', '-i', '/tmp', '--mode', 'invalid']):
            with pytest.raises(SystemExit):
                app.parse_args()

    def test_sort_flag(self):
        """Test --sort flag with valid values matching SortOrder enum."""
        app = CLIApplication()

        # Test shortest-path (default)
        with mock.patch.object(sys, 'argv', ['onlyone', '-i', '/tmp', '--sort', 'shortest-path']):
            args = app.parse_args()
        assert args.sort == "shortest-path"

        # Test shortest-filename
        with mock.patch.object(sys, 'argv', ['onlyone', '-i', '/tmp', '--sort', 'shortest-filename']):
            args = app.parse_args()
        assert args.sort == "shortest-filename"

    def test_invalid_sort_flag(self):
        """Test that invalid sort values are rejected by argparse."""
        app = CLIApplication()

        with mock.patch.object(sys, 'argv', ['onlyone', '-i', '/tmp', '--sort', 'invalid']):
            with pytest.raises(SystemExit):
                app.parse_args()


class TestArgumentValidation:
    """Test validation of parsed arguments."""

    def test_validate_nonexistent_input_directory(self, tmp_path):
        """Test validation fails for non-existent input directory."""
        app = CLIApplication()

        with mock.patch.object(sys, 'argv', ['onlyone', '-i', str(tmp_path / "nonexistent")]):
            args = app.parse_args()

        with pytest.raises(SystemExit) as exc_info:
            app.validate_args(args)
        assert exc_info.value.code == 1

    def test_validate_existing_input_directory(self, tmp_path):
        """Test validation succeeds for existing directory."""
        test_dir = tmp_path / "test_input"
        test_dir.mkdir()

        app = CLIApplication()
        with mock.patch.object(sys, 'argv', ['onlyone', '-i', str(test_dir)]):
            args = app.parse_args()

        # Should not raise
        app.validate_args(args)

    def test_validate_file_as_input(self, tmp_path):
        """Test validation fails when input is a file, not directory."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        app = CLIApplication()
        with mock.patch.object(sys, 'argv', ['onlyone', '-i', str(test_file)]):
            args = app.parse_args()

        with pytest.raises(SystemExit) as exc_info:
            app.validate_args(args)
        assert exc_info.value.code == 1

    def test_validate_invalid_size_format(self, tmp_path):
        """Test validation fails for invalid size format."""
        app = CLIApplication()
        with mock.patch.object(sys, 'argv', ['onlyone', '-i', str(tmp_path), '-m', 'invalid']):
            args = app.parse_args()

        with pytest.raises(SystemExit):
            app.validate_args(args)

    def test_validate_size_range(self, tmp_path):
        """Test validation fails when min_size > max_size."""
        app = CLIApplication()
        with mock.patch.object(sys, 'argv', ['onlyone', '-i', str(tmp_path), '-m', '100MB', '-M', '50MB']):
            args = app.parse_args()

        with pytest.raises(SystemExit):
            app.validate_args(args)

    def test_validate_force_without_keep_one(self, tmp_path):
        """Test that --force without --keep-one raises error."""
        app = CLIApplication()
        with mock.patch.object(sys, 'argv', ['onlyone', '-i', str(tmp_path), '--force']):
            args = app.parse_args()

        with pytest.raises(SystemExit):
            app.validate_args(args)

    def test_validate_keep_one_requires_tty_without_force(self, tmp_path, monkeypatch):
        """Test that --keep-one without --force requires interactive terminal."""
        app = CLIApplication()
        with mock.patch.object(sys, 'argv', ['onlyone', '-i', str(tmp_path), '--keep-one']):
            args = app.parse_args()

        # Mock non-interactive environment (e.g., piping output to file)
        monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)
        monkeypatch.setattr(sys.stdout, 'isatty', lambda: True)

        with pytest.raises(SystemExit) as exc_info:
            app.validate_args(args)
        assert exc_info.value.code == 1


class TestParamsCreation:
    """Test creation of DeduplicationParams from CLI arguments."""

    def test_create_params_with_extensions(self, tmp_path):
        """Test that extensions are correctly parsed from space-separated values."""
        app = CLIApplication()
        with mock.patch.object(sys, 'argv', [
            'onlyone', '-i', str(tmp_path), '-x', '.jpg', '.PNG', '.gif'
        ]):
            args = app.parse_args()

        params = app.create_params(args)

        # Extensions should be normalized to lowercase with leading dot
        assert set(params.extensions) == {".jpg", ".png", ".gif"}
        # Check DEFAULT values
        assert params.min_size_bytes == 0  # Default: "0"
        assert params.max_size_bytes == 100 * 1024 * 1024 * 1024  # Default: "100GB" = 100 GiB
        assert params.mode == DeduplicationMode.NORMAL
        assert params.sort_order == SortOrder.SHORTEST_PATH  # Default sort order

    def test_create_params_with_favourite_dirs(self, tmp_path):
        """Test favourite dirs parsing with space-separated values."""
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        app = CLIApplication()
        with mock.patch.object(sys, 'argv', [
            'onlyone', '-i', str(tmp_path), '-p', str(dir1), str(dir2)
        ]):
            args = app.parse_args()

        params = app.create_params(args)

        # Should contain absolute paths to both directories
        assert len(params.favourite_dirs) == 2
        assert str(dir1.resolve()) in params.favourite_dirs
        assert str(dir2.resolve()) in params.favourite_dirs

    def test_create_params_with_sort_shortest_filename(self, tmp_path):
        """Test explicit sort order shortest-filename."""
        app = CLIApplication()
        with mock.patch.object(sys, 'argv', [
            'onlyone', '-i', str(tmp_path), '--sort', 'shortest-filename'
        ]):
            args = app.parse_args()

        params = app.create_params(args)
        assert params.sort_order == SortOrder.SHORTEST_FILENAME

    def test_create_params_with_explicit_sizes(self, tmp_path):
        """Test explicit size parameters."""
        app = CLIApplication()
        with mock.patch.object(sys, 'argv', [
            'onlyone', '-i', str(tmp_path), '-m', '100KB', '-M', '10MB'
        ]):
            args = app.parse_args()

        params = app.create_params(args)

        assert params.min_size_bytes == 100 * 1024
        assert params.max_size_bytes == 10 * 1024 * 1024