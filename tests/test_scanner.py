"""
Unit tests for FileScannerImpl.
Verifies file discovery with size/extension filters, error handling, and edge cases.
"""
from pathlib import Path
import sys
import pytest
from highlander.core import FileScannerImpl
from highlander.core.models import File


class TestFileScannerImpl:
    """Test file scanning with filters and error handling."""

    def test_scans_all_files_without_filters(self, test_files):
        """Scanner should find all .txt files when no size filters applied."""
        scanner = FileScannerImpl(
            root_dir=str(Path(test_files["dup1_a"]).parent),
            min_size=None,
            max_size=None,
            extensions=[".txt"],
            favourite_dirs=[]
        )
        collection = scanner.scan(stopped_flag=lambda: False)
        files = collection.files
        assert len(files) == 7
        assert all(f.path.endswith(".txt") for f in files)
        assert all(f.size > 0 for f in files)

    def test_filters_by_min_size(self, test_files):
        """Files smaller than min_size should be excluded."""
        scanner = FileScannerImpl(
            root_dir=str(Path(test_files["dup1_a"]).parent),
            min_size=1025,
            max_size=None,
            extensions=[".txt"],
            favourite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files
        assert len(files) == 4
        assert all(f.size >= 1025 for f in files)

    def test_filters_by_max_size(self, test_files):
        """Files larger than max_size should be excluded."""
        scanner = FileScannerImpl(
            root_dir=str(Path(test_files["dup1_a"]).parent),
            min_size=None,
            max_size=2000,
            extensions=[".txt"],
            favourite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files
        assert len(files) == 4
        assert all(f.size <= 2000 for f in files)

    def test_filters_by_extension(self, test_files):
        """Only files with specified extensions should be included."""
        scanner = FileScannerImpl(
            root_dir=str(Path(test_files["dup1_a"]).parent),
            min_size=None,
            max_size=None,
            extensions=[".tmp"],
            favourite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files
        assert len(files) == 1
        assert files[0].path.endswith("ignore.tmp")

    def test_scans_subdirectories_recursively(self, test_files):
        """Scanner should traverse into subdirectories by default."""
        scanner = FileScannerImpl(
            root_dir=str(Path(test_files["dup1_a"]).parent),
            min_size=None,
            max_size=None,
            extensions=[".txt"],
            favourite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files
        subdir_files = [f for f in files if "subdir" in f.path]
        assert len(subdir_files) == 1
        assert "dup_in_subdir.txt" in subdir_files[0].path

    def test_skips_empty_files(self, test_files):
        """Scanner should skip zero-byte files."""
        scanner = FileScannerImpl(
            root_dir=str(Path(test_files["dup1_a"]).parent),
            min_size=None,
            max_size=None,
            extensions=[".txt"],
            favourite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files
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
        scanner = FileScannerImpl(
            root_dir=str(temp_dir),
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files
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
        def mocked_stat(self, *args, **kwargs):
            if str(self) == str(denied_file):
                raise PermissionError(f"Permission denied: {self}")
            return original_stat(self, *args, **kwargs)
        monkeypatch.setattr(Path, 'stat', mocked_stat)
        scanner = FileScannerImpl(
            root_dir=str(temp_dir),
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files
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
        scanner = FileScannerImpl(
            root_dir=str(temp_dir),
            min_size=1024,
            max_size=2048,
            extensions=[".txt"],
            favourite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files
        assert len(files) == 4
        sizes = sorted([f.size for f in files])
        assert sizes == [1024, 1025, 2047, 2048]

    def test_skips_system_trash_directories_windows(self, temp_dir, monkeypatch):
        """Scanner must skip Windows $Recycle.Bin directories."""
        monkeypatch.setattr(sys, 'platform', 'win32')
        recycle_bin = temp_dir / "$Recycle.Bin" / "S-1-5-18"
        recycle_bin.mkdir(parents=True)
        (recycle_bin / "deleted.txt").write_bytes(b"trashed")
        (temp_dir / "normal.txt").write_bytes(b"keep me")
        scanner = FileScannerImpl(
            root_dir=str(temp_dir),
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files
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
        scanner = FileScannerImpl(
            root_dir=str(temp_dir),
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".jpg"],
            favourite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files
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
        scanner = FileScannerImpl(
            root_dir=str(temp_dir),
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".pdf"],
            favourite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files
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
        scanner = FileScannerImpl(
            root_dir=str(temp_dir),
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files
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
        scanner = FileScannerImpl(
            root_dir=str(temp_dir),
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[str(fav_dir)]
        )
        files = scanner.scan(stopped_flag=lambda: False).files
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
        scanner = FileScannerImpl(
            root_dir=str(temp_dir),
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[]
        )
        files = scanner.scan(stopped_flag=stopped_flag).files
        assert call_count <= 5
        assert len(files) < 10

    def test_scanner_rejects_nonexistent_root(self, temp_dir):
        """Scanner must raise RuntimeError for non-existent root directory."""
        nonexistent = temp_dir / "does_not_exist"
        scanner = FileScannerImpl(
            root_dir=str(nonexistent),
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[]
        )
        with pytest.raises(RuntimeError, match="does not exist"):
            scanner.scan(stopped_flag=lambda: False)

    def test_scanner_rejects_file_as_root(self, temp_dir):
        """Scanner must raise RuntimeError when root is a file, not directory."""
        file_as_root = temp_dir / "not_a_dir.txt"
        file_as_root.write_bytes(b"content")
        scanner = FileScannerImpl(
            root_dir=str(file_as_root),
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[]
        )
        with pytest.raises(RuntimeError, match="Not a directory"):
            scanner.scan(stopped_flag=lambda: False)