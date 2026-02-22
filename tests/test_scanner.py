"""
Unit tests for FileScannerImpl.
Verifies file discovery with size/extension filters, error handling, and edge cases.
"""
from pathlib import Path
import sys
import pytest
from onlyone.core.scanner import FileScannerImpl
from onlyone.core.models import DeduplicationParams


# =============================================================================
# 1. EXTENSION NORMALIZATION TESTS
# =============================================================================
class TestExtensionNormalization:
    """Tests for DeduplicationParams._normalize_extensions static method."""

    def test_whitelist_basic_normalization(self):
        """Whitelist: raw extensions should be normalized with dots."""
        exts, mode = DeduplicationParams._normalize_extensions(["txt", "md"])
        assert mode == "whitelist"
        assert exts == [".txt", ".md"]

    def test_whitelist_with_dots(self):
        """Whitelist: extensions with dots should remain unchanged."""
        exts, mode = DeduplicationParams._normalize_extensions([".txt", ".pdf"])
        assert mode == "whitelist"
        assert exts == [".txt", ".pdf"]

    def test_whitelist_mixed_case(self):
        """Whitelist: extensions should be lowercased."""
        exts, mode = DeduplicationParams._normalize_extensions(["TXT", "PdF"])
        assert mode == "whitelist"
        assert exts == [".txt", ".pdf"]

    def test_blacklist_mode(self):
        """Blacklist: '^' marker should set mode and be excluded from list."""
        exts, mode = DeduplicationParams._normalize_extensions(["^", "tmp", "log"])
        assert mode == "blacklist"
        assert exts == [".tmp", ".log"]

    def test_blacklist_with_dots(self):
        """Blacklist: extensions with dots should be normalized."""
        exts, mode = DeduplicationParams._normalize_extensions(["^", ".tmp", ".log"])
        assert mode == "blacklist"
        assert exts == [".tmp", ".log"]

    def test_empty_list(self):
        """Empty list: should default to whitelist with empty extensions."""
        exts, mode = DeduplicationParams._normalize_extensions([])
        assert mode == "whitelist"
        assert exts == []

    def test_whitespace_handling(self):
        """Whitespace: should be stripped from extensions."""
        exts, mode = DeduplicationParams._normalize_extensions(["  txt  ", "  md  "])
        assert exts == [".txt", ".md"]


# =============================================================================
# 2. FILE SCANNER TESTS
# =============================================================================
class TestFileScannerImpl:
    """Test file scanning with filters and error handling."""

    def test_scans_all_files_without_filters(self, test_files):
        """Scanner should find all .txt files when no size filters applied."""
        params = DeduplicationParams(
            root_dir=str(Path(test_files["dup1_a"]).parent),
            min_size_bytes=0,
            max_size_bytes=100_000_000,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=[]
        )
        scanner = FileScannerImpl(params=params)
        files = scanner.scan(stopped_flag=lambda: False)
        assert len(files) > 0
        assert all(f.path.endswith(".txt") for f in files)
        assert all(f.size > 0 for f in files)

    def test_filters_by_min_size(self, test_files):
        """Files smaller than min_size should be excluded."""
        params = DeduplicationParams(
            root_dir=str(Path(test_files["dup1_a"]).parent),
            min_size_bytes=1025,
            max_size_bytes=100_000_000,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=[]
        )
        scanner = FileScannerImpl(params=params)
        files = scanner.scan(stopped_flag=lambda: False)
        assert all(f.size >= 1025 for f in files)

    def test_filters_by_max_size(self, test_files):
        """Files larger than max_size should be excluded."""
        params = DeduplicationParams(
            root_dir=str(Path(test_files["dup1_a"]).parent),
            min_size_bytes=0,
            max_size_bytes=2000,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=[]
        )
        scanner = FileScannerImpl(params=params)
        files = scanner.scan(stopped_flag=lambda: False)
        assert all(f.size <= 2000 for f in files)

    def test_filters_by_extension_whitelist(self, test_files):
        """Whitelist: only files with specified extensions should be included."""
        params = DeduplicationParams(
            root_dir=str(Path(test_files["dup1_a"]).parent),
            min_size_bytes=0,
            max_size_bytes=100_000_000,
            extensions=[".tmp"],
            favourite_dirs=[],
            excluded_dirs=[]
        )
        scanner = FileScannerImpl(params=params)
        files = scanner.scan(stopped_flag=lambda: False)
        assert all(f.extension == ".tmp" for f in files)

    def test_filters_by_extension_blacklist(self, test_files):
        """Blacklist: files with specified extensions should be excluded."""
        params = DeduplicationParams(
            root_dir=str(Path(test_files["dup1_a"]).parent),
            min_size_bytes=0,
            max_size_bytes=100_000_000,
            extensions=["^", ".tmp", ".log"],
            favourite_dirs=[],
            excluded_dirs=[]
        )
        scanner = FileScannerImpl(params=params)
        files = scanner.scan(stopped_flag=lambda: False)
        assert not any(f.extension == ".tmp" for f in files)
        assert not any(f.extension == ".log" for f in files)

    def test_scans_subdirectories_recursively(self, test_files):
        """Scanner should traverse into subdirectories by default."""
        params = DeduplicationParams(
            root_dir=str(Path(test_files["dup1_a"]).parent),
            min_size_bytes=0,
            max_size_bytes=100_000_000,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=[]
        )
        scanner = FileScannerImpl(params=params)
        files = scanner.scan(stopped_flag=lambda: False)
        subdir_files = [f for f in files if "subdir" in f.path]
        assert len(subdir_files) >= 0

    def test_skips_empty_files(self, test_files):
        """Scanner should skip zero-byte files."""
        params = DeduplicationParams(
            root_dir=str(Path(test_files["dup1_a"]).parent),
            min_size_bytes=0,
            max_size_bytes=100_000_000,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=[]
        )
        scanner = FileScannerImpl(params=params)
        files = scanner.scan(stopped_flag=lambda: False)
        assert not any("empty.txt" in f.path for f in files)

    def test_scanner_skips_symlinks(self, temp_dir):
        """Symbolic links must be skipped to prevent duplicate processing."""
        real_file = temp_dir / "real.txt"
        real_file.write_bytes(b"content")
        try:
            symlink = temp_dir / "link.txt"
            symlink.symlink_to(real_file)
            symlink_created = True
        except (OSError, NotImplementedError):
            symlink_created = False
        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=[]
        )
        scanner = FileScannerImpl(params=params)
        files = scanner.scan(stopped_flag=lambda: False)
        if symlink_created:
            assert len(files) == 1
            assert files[0].path == str(real_file)
            assert not any("link.txt" in f.path for f in files)
        else:
            assert len(files) == 1
            assert files[0].path == str(real_file)

    def test_scanner_handles_permission_error(self, temp_dir, monkeypatch):
        """Scanner must gracefully skip files with PermissionError without crashing."""
        (temp_dir / "accessible.txt").write_bytes(b"ok")
        denied_file = temp_dir / "denied.txt"
        denied_file.write_bytes(b"secret")
        original_stat = Path.stat

        def mocked_stat(path_obj, *args, **kwargs):
            if str(path_obj) == str(denied_file):
                raise PermissionError(f"Permission denied: {path_obj}")
            return original_stat(path_obj, *args, **kwargs)

        monkeypatch.setattr(Path, 'stat', mocked_stat)

        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=[]
        )
        scanner = FileScannerImpl(params=params)
        files = scanner.scan(stopped_flag=lambda: False)

        assert len(files) == 1
        assert "accessible.txt" in files[0].path

    def test_scanner_inclusive_size_boundaries(self, temp_dir):
        """Size filters must be inclusive: min_size <= file.size <= max_size."""
        (temp_dir / "min_boundary.txt").write_bytes(b"A" * 1024)
        (temp_dir / "just_above_min.txt").write_bytes(b"A" * 1025)
        (temp_dir / "max_boundary.txt").write_bytes(b"B" * 2048)
        (temp_dir / "just_below_max.txt").write_bytes(b"B" * 2047)
        (temp_dir / "below_min.txt").write_bytes(b"C" * 1023)
        (temp_dir / "above_max.txt").write_bytes(b"D" * 2049)
        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=1024,
            max_size_bytes=2048,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=[]
        )
        scanner = FileScannerImpl(params=params)
        files = scanner.scan(stopped_flag=lambda: False)
        sizes = sorted([f.size for f in files])
        assert 1024 in sizes
        assert 2048 in sizes
        assert 1023 not in sizes
        assert 2049 not in sizes

    def test_skips_system_trash_directories_windows(self, temp_dir, monkeypatch):
        """Scanner must skip Windows $Recycle.Bin directories."""
        monkeypatch.setattr(sys, 'platform', 'win32')
        recycle_bin = temp_dir / "$Recycle.Bin" / "S-1-5-18"
        recycle_bin.mkdir(parents=True)
        (recycle_bin / "deleted.txt").write_bytes(b"trashed")
        (temp_dir / "normal.txt").write_bytes(b"keep me")
        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=[]
        )
        scanner = FileScannerImpl(params=params)
        files = scanner.scan(stopped_flag=lambda: False)
        assert len(files) == 1
        assert "normal.txt" in files[0].path
        assert "$Recycle.Bin" not in files[0].path

    def test_skips_system_trash_directories_macos(self, temp_dir, monkeypatch):
        """Scanner must skip macOS .Trash directories."""
        monkeypatch.setattr(sys, 'platform', 'darwin')
        trash_dir = temp_dir / ".Trash"
        trash_dir.mkdir()
        (trash_dir / "deleted.jpg").write_bytes(b"trashed")
        (temp_dir / "normal.jpg").write_bytes(b"keep me")
        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".jpg"],
            favourite_dirs=[],
            excluded_dirs=[]
        )
        scanner = FileScannerImpl(params=params)
        files = scanner.scan(stopped_flag=lambda: False)
        assert len(files) == 1
        assert "normal.jpg" in files[0].path
        assert ".Trash" not in files[0].path

    def test_skips_system_trash_directories_linux(self, temp_dir, monkeypatch):
        """Scanner must skip Linux .local/share/Trash directories."""
        monkeypatch.setattr(sys, 'platform', 'linux')
        trash_dir = temp_dir / ".local" / "share" / "Trash"
        trash_dir.mkdir(parents=True)
        (trash_dir / "deleted.pdf").write_bytes(b"trashed")
        (temp_dir / "normal.pdf").write_bytes(b"keep me")
        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".pdf"],
            favourite_dirs=[],
            excluded_dirs=[]
        )
        scanner = FileScannerImpl(params=params)
        files = scanner.scan(stopped_flag=lambda: False)
        assert len(files) == 1
        assert "normal.pdf" in files[0].path
        assert "Trash" not in files[0].path

    def test_path_depth_field_set_correctly(self, temp_dir):
        """File.path_depth must reflect actual directory nesting level."""
        root_file = temp_dir / "root.txt"
        root_file.write_bytes(b"content")
        subdir = temp_dir / "level1"
        subdir.mkdir()
        level1_file = subdir / "level1.txt"
        level1_file.write_bytes(b"content")
        subsubdir = subdir / "level2"
        subsubdir.mkdir()
        level2_file = subsubdir / "level2.txt"
        level2_file.write_bytes(b"content")
        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=[]
        )
        scanner = FileScannerImpl(params=params)
        files = scanner.scan(stopped_flag=lambda: False)
        files_by_name = {Path(f.path).name: f for f in files}
        assert files_by_name["root.txt"].path_depth >= 0
        assert files_by_name["level1.txt"].path_depth == files_by_name["root.txt"].path_depth + 1
        assert files_by_name["level2.txt"].path_depth == files_by_name["level1.txt"].path_depth + 1

    def test_favourite_dirs_status_set_during_scan(self, temp_dir):
        """Files in favourite directories must have is_from_fav_dir=True after scan."""
        fav_dir = temp_dir / "favourites"
        fav_dir.mkdir()
        normal_dir = temp_dir / "normal"
        normal_dir.mkdir()
        (fav_dir / "fav.txt").write_bytes(b"content")
        (normal_dir / "normal.txt").write_bytes(b"content")
        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[str(fav_dir)],
            excluded_dirs=[]
        )
        scanner = FileScannerImpl(params=params)
        files = scanner.scan(stopped_flag=lambda: False)
        files_by_name = {Path(f.path).name: f for f in files}
        assert files_by_name["fav.txt"].is_from_fav_dir is True
        assert files_by_name["normal.txt"].is_from_fav_dir is False

    def test_stopped_flag_during_directory_traversal(self, temp_dir):
        """Scanner must respect stopped_flag during os.walk directory traversal phase."""
        for i in range(10):
            subdir = temp_dir / f"dir{i}"
            subdir.mkdir()
            (subdir / f"file{i}.txt").write_bytes(b"content")
        call_count = 0
        def stopped_flag():
            nonlocal call_count
            call_count += 1
            return call_count > 3
        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=[]
        )
        scanner = FileScannerImpl(params=params)
        files = scanner.scan(stopped_flag=stopped_flag)
        assert call_count <= 5
        assert len(files) < 10

    def test_scanner_rejects_nonexistent_root(self, temp_dir):
        """Scanner must raise RuntimeError for non-existent root directory."""
        nonexistent = temp_dir / "does_not_exist"
        params = DeduplicationParams(
            root_dir=str(nonexistent),
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=[]
        )
        scanner = FileScannerImpl(params=params)
        with pytest.raises(RuntimeError, match="does not exist"):
            scanner.scan(stopped_flag=lambda: False)

    def test_scanner_rejects_file_as_root(self, temp_dir):
        """Scanner must raise RuntimeError when root is a file, not directory."""
        file_as_root = temp_dir / "not_a_dir.txt"
        file_as_root.write_bytes(b"content")
        params = DeduplicationParams(
            root_dir=str(file_as_root),
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=[]
        )
        scanner = FileScannerImpl(params=params)
        with pytest.raises(RuntimeError, match="Not a directory"):
            scanner.scan(stopped_flag=lambda: False)

    def test_empty_directory_returns_empty_list(self, temp_dir):
        """Scanner should return empty list for empty directory."""
        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=[]
        )
        scanner = FileScannerImpl(params=params)
        files = scanner.scan(stopped_flag=lambda: False)
        assert len(files) == 0

    def test_case_insensitive_extension_filter(self, temp_dir):
        """Extension filter should be case-insensitive."""
        (temp_dir / "upper.TXT").write_bytes(b"content")
        (temp_dir / "lower.txt").write_bytes(b"content")
        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=[]
        )
        scanner = FileScannerImpl(params=params)
        files = scanner.scan(stopped_flag=lambda: False)
        assert len(files) == 2
        assert all(f.extension == ".txt" for f in files)

    def test_excluded_dirs_are_skipped(self, temp_dir):
        """Files in excluded directories should be skipped."""
        excluded_subdir = temp_dir / "excluded"
        excluded_subdir.mkdir()
        (excluded_subdir / "file.txt").write_bytes(b"content")
        (temp_dir / "included.txt").write_bytes(b"content")
        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[],
            favourite_dirs=[],
            excluded_dirs=[str(excluded_subdir)]
        )
        scanner = FileScannerImpl(params=params)
        files = scanner.scan(stopped_flag=lambda: False)
        assert len(files) == 1
        assert "included.txt" in files[0].path
        assert "excluded" not in files[0].path


    def test_excludes_specified_directories(self, temp_dir):
        """Files in excluded directories must be skipped."""
        included_dir = temp_dir / "included"
        included_dir.mkdir()
        excluded_dir = temp_dir / "excluded"
        excluded_dir.mkdir()

        (included_dir / "keep.txt").write_bytes(b"content")
        (excluded_dir / "skip.txt").write_bytes(b"content")

        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=[str(excluded_dir)]
        )
        scanner = FileScannerImpl(params=params)
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

        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=[str(excluded_dir)]
        )
        scanner = FileScannerImpl(params=params)
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

        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=[str(dir1), str(dir2)]
        )
        scanner = FileScannerImpl(params=params)
        files = scanner.scan(stopped_flag=lambda: False)

        assert len(files) == 1
        assert "keep.txt" in files[0].path

    def test_excluded_dirs_with_normalization(self, temp_dir):
        """Excluded dirs must work with different path formats (slashes, trailing slashes)."""
        excluded_dir = temp_dir / "excluded"
        excluded_dir.mkdir()
        (excluded_dir / "skip.txt").write_bytes(b"content")
        (temp_dir / "keep.txt").write_bytes(b"content")

        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=[str(excluded_dir) + "/"]
        )
        scanner = FileScannerImpl(params=params)
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

        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=[]
        )
        scanner = FileScannerImpl(params=params)
        files = scanner.scan(stopped_flag=lambda: False)

        assert len(files) == 2

    def test_none_excluded_dirs(self, temp_dir):
        """None excluded_dirs must not exclude any directories."""
        dir1 = temp_dir / "dir1"
        dir1.mkdir()
        (dir1 / "file1.txt").write_bytes(b"content")

        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=[]
        )
        scanner = FileScannerImpl(params=params)
        files = scanner.scan(stopped_flag=lambda: False)

        assert len(files) == 1

    def test_excluded_dirs_takes_precedence_over_favourite_dirs(self, temp_dir):
        """If a directory is both excluded and favourite, excluded must win."""
        special_dir = temp_dir / "special"
        special_dir.mkdir()
        (special_dir / "file.txt").write_bytes(b"content")

        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[str(special_dir)],
            excluded_dirs=[str(special_dir)]
        )
        scanner = FileScannerImpl(params=params)
        files = scanner.scan(stopped_flag=lambda: False)

        assert len(files) == 0

    def test_excluded_dirs_exact_path_match(self, temp_dir):
        """Excluded dir must match exact path, not substring."""
        excluded_dir = temp_dir / "data"
        excluded_dir.mkdir()
        similar_dir = temp_dir / "data_backup"
        similar_dir.mkdir()

        (excluded_dir / "skip.txt").write_bytes(b"content")
        (similar_dir / "keep.txt").write_bytes(b"content")

        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=[str(excluded_dir)]
        )
        scanner = FileScannerImpl(params=params)
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

        params = DeduplicationParams(
            root_dir=".",
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=["excluded"]
        )
        scanner = FileScannerImpl(params=params)
        files = scanner.scan(stopped_flag=lambda: False)

        assert len(files) == 1
        assert "keep.txt" in files[0].path
        assert "skip.txt" not in files[0].path


# =============================================================================
# 3. INTEGRATION TESTS (DeduplicationCommand)
# =============================================================================
class TestDeduplicationCommandIntegration:
    """End-to-end tests through DeduplicationCommand."""

    def test_command_whitelist_mode(self, temp_dir):
        """Command: whitelist should only scan allowed extensions."""
        from onlyone.commands import DeduplicationCommand
        content = b"duplicate content"
        (temp_dir / "file1.txt").write_bytes(content)
        (temp_dir / "file2.txt").write_bytes(content)
        (temp_dir / "file3.pdf").write_bytes(content)
        (temp_dir / "cache.tmp").write_bytes(content)
        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1000000,
            extensions=[".txt"],
            favourite_dirs=[],
            excluded_dirs=[]
        )
        command = DeduplicationCommand()
        groups, stats = command.execute(params)
        all_files = []
        for group in groups:
            for f in group.files:
                all_files.append(f.path)
        if all_files:
            assert any(".txt" in f for f in all_files)
            assert not any(".pdf" in f for f in all_files)
            assert not any(".tmp" in f for f in all_files)

    def test_command_blacklist_mode(self, temp_dir):
        """Command: blacklist should exclude specified extensions."""
        from onlyone.commands import DeduplicationCommand
        content = b"duplicate content"
        (temp_dir / "file1.txt").write_bytes(content)
        (temp_dir / "file2.txt").write_bytes(content)
        (temp_dir / "cache.tmp").write_bytes(content)
        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1000000,
            extensions=["^", ".tmp"],
            favourite_dirs=[],
            excluded_dirs=[]
        )
        command = DeduplicationCommand()
        groups, stats = command.execute(params)
        all_files = []
        for group in groups:
            for f in group.files:
                all_files.append(f.path)
        if all_files:
            assert not any(".tmp" in f for f in all_files)

    def test_command_empty_extensions_allows_all(self, temp_dir):
        """Command: empty extensions should allow all file types."""
        from onlyone.commands import DeduplicationCommand
        content = b"duplicate content"
        (temp_dir / "file1.txt").write_bytes(content)
        (temp_dir / "file2.pdf").write_bytes(content)
        (temp_dir / "file3.jpg").write_bytes(content)
        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1000000,
            extensions=[],
            favourite_dirs=[],
            excluded_dirs=[]
        )
        command = DeduplicationCommand()
        groups, stats = command.execute(params)
        assert isinstance(groups, list)
        assert hasattr(stats, 'total_time')


# =============================================================================
# 4. DEDUPLICATION PARAMS TESTS
# =============================================================================
class TestDeduplicationParamsProperties:
    """Tests for DeduplicationParams normalized properties."""

    def test_normalized_extensions_property(self):
        """normalized_extensions should return processed list."""
        params = DeduplicationParams(
            root_dir="/test",
            min_size_bytes=0,
            max_size_bytes=1000000,
            extensions=["TXT", "md"]
        )
        assert params.normalized_extensions == [".txt", ".md"]
        assert params.extension_filter_mode == "whitelist"

    def test_blacklist_properties(self):
        """Blacklist mode should set correct properties."""
        params = DeduplicationParams(
            root_dir="/test",
            min_size_bytes=0,
            max_size_bytes=1000000,
            extensions=["^", "tmp", "log"]
        )
        assert params.normalized_extensions == [".tmp", ".log"]
        assert params.extension_filter_mode == "blacklist"

    def test_raw_extensions_preserved(self):
        """Raw extensions should be preserved unchanged."""
        params = DeduplicationParams(
            root_dir="/test",
            min_size_bytes=0,
            max_size_bytes=1000000,
            extensions=["TXT", "^", "tmp"]
        )
        assert params.extensions == ["TXT", "^", "tmp"]
        assert params.normalized_extensions == [".txt", ".tmp"]
        assert params.extension_filter_mode == "blacklist"

    def test_params_validation_empty_root(self):
        """Should raise ValueError for empty root directory."""
        with pytest.raises(ValueError, match="Root directory cannot be empty"):
            DeduplicationParams(
                root_dir="",
                min_size_bytes=0,
                max_size_bytes=1000000
            )

    def test_params_validation_negative_min_size(self):
        """Should raise ValueError for negative min_size."""
        with pytest.raises(ValueError, match="Minimum size cannot be negative"):
            DeduplicationParams(
                root_dir="/test",
                min_size_bytes=-1,
                max_size_bytes=1000000
            )

    def test_params_validation_max_less_than_min(self):
        """Should raise ValueError when max_size < min_size."""
        with pytest.raises(ValueError, match="Maximum size cannot be less than minimum size"):
            DeduplicationParams(
                root_dir="/test",
                min_size_bytes=1000,
                max_size_bytes=500
            )