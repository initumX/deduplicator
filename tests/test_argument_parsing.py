"""
Tests for CLI argument parsing and validation.
"""
import sys
from unittest import mock
import pytest
from pathlib import Path
from highlander.cli import CLIApplication
from highlander.core.models import DeduplicationMode, SortOrder


class TestArgumentParsing:
    """Test CLI argument parsing with argparse."""

    def test_input_flag_variants(self):
        """Test both long (--input) and short (-i) forms."""
        app = CLIApplication()

        # Long form
        with mock.patch.object(sys, 'argv', ['dedup', '--input', '/tmp/test']):
            args = app.parse_args()
        assert args.input == "/tmp/test"

        # Short form
        with mock.patch.object(sys, 'argv', ['dedup', '-i', '/tmp/test']):
            args = app.parse_args()
        assert args.input == "/tmp/test"

    def test_extensions_flag_variants(self):
        """Test both long (--extensions) and short (-x) forms."""
        app = CLIApplication()

        # Long form with comma-separated values
        with mock.patch.object(sys, 'argv', ['dedup', '-i', '/tmp', '--extensions', '.jpg,.png']):
            args = app.parse_args()
        assert args.extensions == ".jpg,.png"

        # Short form
        with mock.patch.object(sys, 'argv', ['dedup', '-i', '/tmp', '-x', '.jpg,.png,.gif']):
            args = app.parse_args()
        assert args.extensions == ".jpg,.png,.gif"

    def test_favourite_dirs_space_separated(self):
        """Test favourite dirs with space-separated values."""
        app = CLIApplication()

        with mock.patch.object(sys, 'argv', [
            'dedup', '-i', '/tmp', '-f', '/tmp/dir1', '/tmp/dir2', '/tmp/dir3'
        ]):
            args = app.parse_args()
        assert args.favourite_dirs == ["/tmp/dir1", "/tmp/dir2", "/tmp/dir3"]

    def test_favourite_dirs_comma_separated(self):
        """Test favourite dirs with comma-separated values in single argument."""
        app = CLIApplication()

        with mock.patch.object(sys, 'argv', [
            'dedup', '-i', '/tmp', '-f', '/tmp/dir1,/tmp/dir2,/tmp/dir3'
        ]):
            args = app.parse_args()
        # argparse sees this as ONE argument with commas
        assert args.favourite_dirs == ["/tmp/dir1,/tmp/dir2,/tmp/dir3"]

    def test_favourite_dirs_mixed_syntax(self):
        """Test mixed syntax: spaces + commas."""
        app = CLIApplication()

        with mock.patch.object(sys, 'argv', [
            'dedup', '-i', '/tmp', '-f', '/tmp/dir1', '/tmp/dir2,/tmp/dir3'
        ]):
            args = app.parse_args()
        assert args.favourite_dirs == ["/tmp/dir1", "/tmp/dir2,/tmp/dir3"]

    def test_mode_flag(self):
        """Test --mode flag with valid values."""
        app = CLIApplication()

        for mode in ["fast", "normal", "full"]:
            with mock.patch.object(sys, 'argv', ['dedup', '-i', '/tmp', '--mode', mode]):
                args = app.parse_args()
            assert args.mode == mode

    def test_invalid_mode_flag(self):
        """Test that invalid mode values are rejected by argparse."""
        app = CLIApplication()

        with mock.patch.object(sys, 'argv', ['dedup', '-i', '/tmp', '--mode', 'invalid']):
            with pytest.raises(SystemExit):
                app.parse_args()

    def test_sort_order_flag(self):
        """Test --sort-order flag."""
        app = CLIApplication()

        with mock.patch.object(sys, 'argv', ['dedup', '-i', '/tmp', '--sort-order', 'oldest']):
            args = app.parse_args()
        assert args.sort_order == "oldest"

        with mock.patch.object(sys, 'argv', ['dedup', '-i', '/tmp', '--sort-order', 'newest']):
            args = app.parse_args()
        assert args.sort_order == "newest"


class TestArgumentValidation:
    """Test validation of parsed arguments."""

    def test_validate_nonexistent_input_directory(self, tmp_path):
        """Test validation fails for non-existent input directory."""
        app = CLIApplication()

        with mock.patch.object(sys, 'argv', ['dedup', '-i', str(tmp_path / "nonexistent")]):
            args = app.parse_args()

        with pytest.raises(SystemExit) as exc_info:
            app.validate_args(args)
        assert exc_info.value.code == 1

    def test_validate_existing_input_directory(self, tmp_path):
        """Test validation succeeds for existing directory."""
        test_dir = tmp_path / "test_input"
        test_dir.mkdir()

        app = CLIApplication()
        with mock.patch.object(sys, 'argv', ['dedup', '-i', str(test_dir)]):
            args = app.parse_args()

        # Should not raise
        app.validate_args(args)

    def test_validate_file_as_input(self, tmp_path):
        """Test validation fails when input is a file, not directory."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        app = CLIApplication()
        with mock.patch.object(sys, 'argv', ['dedup', '-i', str(test_file)]):
            args = app.parse_args()

        with pytest.raises(SystemExit) as exc_info:
            app.validate_args(args)
        assert exc_info.value.code == 1

    def test_validate_invalid_size_format(self, tmp_path):
        """Test validation fails for invalid size format."""
        app = CLIApplication()
        with mock.patch.object(sys, 'argv', ['dedup', '-i', str(tmp_path), '-m', 'invalid']):
            args = app.parse_args()

        with pytest.raises(SystemExit):
            app.validate_args(args)

    def test_validate_size_range(self, tmp_path):
        """Test validation fails when min_size > max_size."""
        app = CLIApplication()
        with mock.patch.object(sys, 'argv', ['dedup', '-i', str(tmp_path), '-m', '100MB', '-M', '50MB']):
            args = app.parse_args()

        with pytest.raises(SystemExit):
            app.validate_args(args)

    def test_validate_force_without_keep_one(self, tmp_path):
        """Test that --force without --keep-one raises error."""
        app = CLIApplication()
        with mock.patch.object(sys, 'argv', ['dedup', '-i', str(tmp_path), '--force']):
            args = app.parse_args()

        with pytest.raises(SystemExit):
            app.validate_args(args)


class TestParamsCreation:
    """Test creation of DeduplicationParams from CLI arguments."""

    def test_create_params_with_extensions(self, tmp_path):
        """Test that extensions are correctly parsed from comma-separated string."""
        app = CLIApplication()
        with mock.patch.object(sys, 'argv', [
            'dedup', '-i', str(tmp_path), '-x', '.jpg,.PNG,.gif'
        ]):
            args = app.parse_args()

        params = app.create_params(args)

        # Extensions should be normalized to lowercase with leading dot
        assert set(params.extensions) == {".jpg", ".png", ".gif"}
        # Check DEFAULT values (not 100KB - we didn't pass -m!)
        assert params.min_size_bytes == 0  # Default: "0"
        assert params.max_size_bytes == 100 * 1024 * 1024 * 1024  # Default: "100GB" = 100 GiB
        assert params.mode == DeduplicationMode.NORMAL
        assert params.sort_order == SortOrder.NEWEST_FIRST  # Default sort order

    def test_create_params_with_favourite_dirs_spaces(self, tmp_path):
        """Test favourite dirs parsing with space-separated values."""
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        app = CLIApplication()
        with mock.patch.object(sys, 'argv', [
            'dedup', '-i', str(tmp_path), '-f', str(dir1), str(dir2)
        ]):
            args = app.parse_args()

        params = app.create_params(args)

        # Should contain absolute paths to both directories
        assert len(params.favourite_dirs) == 2
        assert str(dir1.resolve()) in params.favourite_dirs
        assert str(dir2.resolve()) in params.favourite_dirs

    def test_create_params_with_favourite_dirs_commas(self, tmp_path):
        """Test favourite dirs parsing with comma-separated values in single argument."""
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir3 = tmp_path / "dir3"
        dir1.mkdir()
        dir2.mkdir()
        dir3.mkdir()

        app = CLIApplication()
        # Simulate comma-separated input
        with mock.patch.object(sys, 'argv', [
            'dedup', '-i', str(tmp_path), '-f', f"{dir1},{dir2},{dir3}"
        ]):
            args = app.parse_args()

        params = app.create_params(args)

        # Should split by commas and resolve all three directories
        assert len(params.favourite_dirs) == 3
        assert str(dir1.resolve()) in params.favourite_dirs
        assert str(dir2.resolve()) in params.favourite_dirs
        assert str(dir3.resolve()) in params.favourite_dirs

    def test_create_params_with_favourite_dirs_mixed(self, tmp_path):
        """Test favourite dirs parsing with mixed space+comma syntax."""
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir3 = tmp_path / "dir3"
        dir1.mkdir()
        dir2.mkdir()
        dir3.mkdir()

        app = CLIApplication()
        with mock.patch.object(sys, 'argv', [
            'dedup', '-i', str(tmp_path), '-f', str(dir1), f"{dir2},{dir3}"
        ]):
            args = app.parse_args()

        params = app.create_params(args)

        # Should handle both space-separated and comma-separated parts
        assert len(params.favourite_dirs) == 3
        assert str(dir1.resolve()) in params.favourite_dirs
        assert str(dir2.resolve()) in params.favourite_dirs
        assert str(dir3.resolve()) in params.favourite_dirs

    def test_create_params_with_explicit_sizes(self, tmp_path):
        """Test explicit size parameters."""
        app = CLIApplication()
        with mock.patch.object(sys, 'argv', [
            'dedup', '-i', str(tmp_path), '-m', '100KB', '-M', '10MB'
        ]):
            args = app.parse_args()

        params = app.create_params(args)

        assert params.min_size_bytes == 100 * 1024
        assert params.max_size_bytes == 10 * 1024 * 1024