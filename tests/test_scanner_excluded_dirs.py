"""
Unit tests for FileScannerImpl excluded_dirs functionality.
Verifies that excluded directories are properly skipped during scanning.
"""
from onlyone.core import FileScannerImpl


class TestFileScannerImplExcludedDirs:
    """Test file scanning with excluded directories."""

    def test_excludes_specified_directories(self, temp_dir):
        """Files in excluded directories must be skipped."""
        included_dir = temp_dir / "included"
        included_dir.mkdir()
        excluded_dir = temp_dir / "excluded"
        excluded_dir.mkdir()

        (included_dir / "keep.txt").write_bytes(b"content")
        (excluded_dir / "skip.txt").write_bytes(b"content")

        scanner = FileScannerImpl(
            root_dir=str(temp_dir),
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=[str(excluded_dir)]
        )
        files = scanner.scan(stopped_flag=lambda: False)

        assert len(files) == 1
        assert "keep.txt" in files[0].path
        assert "skip.txt" not in files[0].path

    def test_excludes_nested_subdirectories(self, temp_dir):
        """Excluding a parent directory must exclude all nested subdirectories."""
        excluded_dir = temp_dir / "excluded"
        excluded_dir.mkdir()
        nested_dir = excluded_dir / "nested" / "deep"
        nested_dir.mkdir(parents=True)

        (excluded_dir / "level0.txt").write_bytes(b"content")
        (nested_dir / "level2.txt").write_bytes(b"content")
        (temp_dir / "outside.txt").write_bytes(b"content")

        scanner = FileScannerImpl(
            root_dir=str(temp_dir),
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=[str(excluded_dir)]
        )
        files = scanner.scan(stopped_flag=lambda: False)

        assert len(files) == 1
        assert "outside.txt" in files[0].path
        assert "level0.txt" not in files[0].path
        assert "level2.txt" not in files[0].path

    def test_multiple_excluded_directories(self, temp_dir):
        """Multiple excluded directories must all be skipped."""
        dir1 = temp_dir / "exclude1"
        dir1.mkdir()
        dir2 = temp_dir / "exclude2"
        dir2.mkdir()
        keep_dir = temp_dir / "keep"
        keep_dir.mkdir()

        (dir1 / "skip1.txt").write_bytes(b"content")
        (dir2 / "skip2.txt").write_bytes(b"content")
        (keep_dir / "keep.txt").write_bytes(b"content")

        scanner = FileScannerImpl(
            root_dir=str(temp_dir),
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=[str(dir1), str(dir2)]
        )
        files = scanner.scan(stopped_flag=lambda: False)

        assert len(files) == 1
        assert "keep.txt" in files[0].path

    def test_excluded_dirs_with_normalization(self, temp_dir):
        """Excluded dirs must work with different path formats (slashes, trailing slashes)."""
        excluded_dir = temp_dir / "excluded"
        excluded_dir.mkdir()
        (excluded_dir / "skip.txt").write_bytes(b"content")
        (temp_dir / "keep.txt").write_bytes(b"content")

        # Test with trailing slash
        scanner = FileScannerImpl(
            root_dir=str(temp_dir),
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=[str(excluded_dir) + "/"]  # Trailing slash
        )
        files = scanner.scan(stopped_flag=lambda: False)

        assert len(files) == 1
        assert "keep.txt" in files[0].path
        assert "skip.txt" not in files[0].path

    def test_empty_excluded_dirs_list(self, temp_dir):
        """Empty excluded_dirs list must not exclude any directories."""
        dir1 = temp_dir / "dir1"
        dir1.mkdir()
        dir2 = temp_dir / "dir2"
        dir2.mkdir()

        (dir1 / "file1.txt").write_bytes(b"content")
        (dir2 / "file2.txt").write_bytes(b"content")

        scanner = FileScannerImpl(
            root_dir=str(temp_dir),
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=[]  # Empty list
        )
        files = scanner.scan(stopped_flag=lambda: False)

        assert len(files) == 2

    def test_none_excluded_dirs(self, temp_dir):
        """None excluded_dirs must not exclude any directories."""
        dir1 = temp_dir / "dir1"
        dir1.mkdir()
        (dir1 / "file1.txt").write_bytes(b"content")

        scanner = FileScannerImpl(
            root_dir=str(temp_dir),
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=None  # None
        )
        files = scanner.scan(stopped_flag=lambda: False)

        assert len(files) == 1

    def test_excluded_dirs_takes_precedence_over_favourite_dirs(self, temp_dir):
        """If a directory is both excluded and favourite, excluded must win."""
        special_dir = temp_dir / "special"
        special_dir.mkdir()
        (special_dir / "file.txt").write_bytes(b"content")

        scanner = FileScannerImpl(
            root_dir=str(temp_dir),
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[str(special_dir)],
            excluded_dirs=[str(special_dir)]  # Same dir excluded
        )
        files = scanner.scan(stopped_flag=lambda: False)

        # File should be excluded, not scanned at all
        assert len(files) == 0

    def test_excluded_dirs_exact_path_match(self, temp_dir):
        """Excluded dir must match exact path, not substring."""
        excluded_dir = temp_dir / "data"
        excluded_dir.mkdir()
        similar_dir = temp_dir / "data_backup"
        similar_dir.mkdir()

        (excluded_dir / "skip.txt").write_bytes(b"content")
        (similar_dir / "keep.txt").write_bytes(b"content")

        scanner = FileScannerImpl(
            root_dir=str(temp_dir),
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=[str(excluded_dir)]
        )
        files = scanner.scan(stopped_flag=lambda: False)

        assert len(files) == 1
        assert "keep.txt" in files[0].path
        assert "skip.txt" not in files[0].path

    def test_excluded_dirs_with_relative_paths(self, temp_dir, monkeypatch):
        """Excluded dirs must work with relative paths (normalized to absolute)."""
        monkeypatch.chdir(temp_dir)

        excluded_dir = temp_dir / "excluded"
        excluded_dir.mkdir()
        (excluded_dir / "skip.txt").write_bytes(b"content")
        (temp_dir / "keep.txt").write_bytes(b"content")

        # Use relative path
        scanner = FileScannerImpl(
            root_dir=".",
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=["excluded"]  # Relative path
        )
        files = scanner.scan(stopped_flag=lambda: False)

        assert len(files) == 1
        assert "keep.txt" in files[0].path
        assert "skip.txt" not in files[0].path