"""
Unit tests for CLI --excluded-dirs argument parsing and validation.
"""
import pytest
from pathlib import Path
from onlyone.cli import CLIApplication



class TestCLIExcludedDirs:
    """Test CLI excluded-dirs argument handling."""

    def test_excluded_dirs_single_path(self, temp_dir):
        """CLI must accept single excluded directory."""
        excluded_dir = temp_dir / "exclude"
        excluded_dir.mkdir()

        app = CLIApplication()
        args = app.parse_args([
            "-i", str(temp_dir),
            "-e", str(excluded_dir)
        ])

        assert args.excluded_dirs == [str(excluded_dir)]

    def test_excluded_dirs_multiple_paths(self, temp_dir):
        """CLI must accept multiple excluded directories via space separation."""
        dir1 = temp_dir / "exclude1"
        dir1.mkdir()
        dir2 = temp_dir / "exclude2"
        dir2.mkdir()

        app = CLIApplication()
        args = app.parse_args([
            "-i", str(temp_dir),
            "-e", str(dir1), str(dir2)
        ])

        assert len(args.excluded_dirs) == 2
        assert str(dir1) in args.excluded_dirs
        assert str(dir2) in args.excluded_dirs

    def test_excluded_dirs_comma_separated(self, temp_dir):
        """CLI must support comma-separated excluded directories."""
        dir1 = temp_dir / "exclude1"
        dir1.mkdir()
        dir2 = temp_dir / "exclude2"
        dir2.mkdir()

        app = CLIApplication()
        args = app.parse_args([
            "-i", str(temp_dir),
            "-e", f"{dir1},{dir2}"
        ])

        # Should be parsed as single item, split later in create_params
        assert len(args.excluded_dirs) == 1
        assert f"{dir1},{dir2}" in args.excluded_dirs

    def test_excluded_dirs_warning_nonexistent(self, temp_dir, capsys):
        """CLI must warn when excluded directory does not exist."""
        nonexistent = temp_dir / "does_not_exist"

        app = CLIApplication()
        args = app.parse_args([
            "-i", str(temp_dir),
            "-e", str(nonexistent)
        ])

        app.validate_args(args)

        captured = capsys.readouterr()
        assert "Excluded directory not found" in captured.err

    def test_excluded_dirs_warning_not_a_directory(self, temp_dir, capsys):
        """CLI must warn when excluded path is a file, not directory."""
        file_path = temp_dir / "not_a_dir.txt"
        file_path.write_bytes(b"content")

        app = CLIApplication()
        args = app.parse_args([
            "-i", str(temp_dir),
            "-e", str(file_path)
        ])

        app.validate_args(args)

        captured = capsys.readouterr()
        assert "Excluded path is not a directory" in captured.err

    def test_create_params_normalizes_excluded_dirs(self, temp_dir):
        """create_params must normalize excluded_dirs to absolute paths."""
        excluded_dir = temp_dir / "exclude"
        excluded_dir.mkdir()

        app = CLIApplication()
        args = app.parse_args([
            "-i", str(temp_dir),
            "-e", str(excluded_dir)
        ])

        params = app.create_params(args)

        assert len(params.excluded_dirs) == 1
        assert Path(params.excluded_dirs[0]).is_absolute()
        assert params.excluded_dirs[0] == str(excluded_dir.resolve())

    def test_excluded_dirs_in_deduplication_params(self, temp_dir):
        """excluded_dirs must be passed to DeduplicationParams correctly."""
        excluded_dir = temp_dir / "exclude"
        excluded_dir.mkdir()

        app = CLIApplication()
        args = app.parse_args([
            "-i", str(temp_dir),
            "-e", str(excluded_dir),
            "-m", "0",
            "-M", "1GB"
        ])

        params = app.create_params(args)

        assert params.excluded_dirs == [str(excluded_dir.resolve())]

    def test_excluded_dirs_default_empty_list(self, temp_dir):
        """excluded_dirs must default to empty list when not specified."""
        app = CLIApplication()
        args = app.parse_args([
            "-i", str(temp_dir)
        ])

        assert args.excluded_dirs == []

        params = app.create_params(args)
        assert params.excluded_dirs == []