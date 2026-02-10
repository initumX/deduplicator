"""
Unit tests for FileScannerImpl.
Verifies file discovery with size/extension filters, error handling, and edge cases.
"""
import pytest
import os
from pathlib import Path
from core.scanner import FileScannerImpl


class TestFileScannerImpl:
    """Test file scanning with filters and error handling."""

    def test_scans_all_files_without_filters(self, test_files):
        """Scanner should find all .txt files when no size filters applied."""
        scanner = FileScannerImpl(
            root_dir=str(Path(test_files["dup1_a"]).parent),
            min_size=None,
            max_size=None,
            extensions=[".txt"],
            favorite_dirs=[]
        )
        collection = scanner.scan(stopped_flag=lambda: False)
        files = collection.files

        # Should find: dup1_a, dup1_b, dup2_a, dup2_b, unique1, unique2, sub_dup (7 files)
        # Should NOT find: empty.txt (0 bytes filtered), filtered.tmp (wrong extension)
        assert len(files) == 7
        assert all(f.path.endswith(".txt") for f in files)
        assert all(f.size > 0 for f in files)  # Empty file filtered out

    def test_filters_by_min_size(self, test_files):
        """Files smaller than min_size should be excluded."""
        scanner = FileScannerImpl(
            root_dir=str(Path(test_files["dup1_a"]).parent),
            min_size=1025,  # Larger than dup1 files (1024 bytes)
            max_size=None,
            extensions=[".txt"],
            favorite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files

        # Should exclude: dup1_a, dup1_b, sub_dup (all 1024B)
        # Should include: dup2_a/b (2048B), unique1 (1500B), unique2 (2500B)
        assert len(files) == 4
        assert all(f.size >= 1025 for f in files)

    def test_filters_by_max_size(self, test_files):
        """Files larger than max_size should be excluded."""
        scanner = FileScannerImpl(
            root_dir=str(Path(test_files["dup1_a"]).parent),
            min_size=None,
            max_size=2000,  # Smaller than dup2 files (2048 bytes) and unique2 (2500B)
            extensions=[".txt"],
            favorite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files

        # Should exclude: dup2_a, dup2_b (2048B), unique2 (2500B)
        # Should include: dup1_a/b (1024B), unique1 (1500B), sub_dup (1024B) → total 4 files
        assert len(files) == 4
        assert all(f.size <= 2000 for f in files)

    def test_filters_by_extension(self, test_files):
        """Only files with specified extensions should be included."""
        scanner = FileScannerImpl(
            root_dir=str(Path(test_files["dup1_a"]).parent),
            min_size=None,
            max_size=None,
            extensions=[".tmp"],  # Only .tmp files
            favorite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files

        # Should find ONLY filtered.tmp
        assert len(files) == 1
        assert files[0].path.endswith("ignore.tmp")

    def test_scans_subdirectories_recursively(self, test_files):
        """Scanner should traverse into subdirectories by default."""
        scanner = FileScannerImpl(
            root_dir=str(Path(test_files["dup1_a"]).parent),
            min_size=None,
            max_size=None,
            extensions=[".txt"],
            favorite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files

        # Should include file from subdir/
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
            favorite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files

        # empty.txt should NOT be in results
        assert not any("empty.txt" in f.path for f in files)

    def test_scanner_skips_symlinks(self, temp_dir):
        """
        Symbolic links must be skipped to prevent infinite loops and duplicate processing.
        This is a critical security and stability feature.
        """
        # Create a real file
        real_file = temp_dir / "real.txt"
        real_file.write_bytes(b"content")

        # Create a symlink pointing to the real file (only if OS supports symlinks)
        try:
            symlink = temp_dir / "link.txt"
            symlink.symlink_to(real_file)
            symlink_created = True
        except (OSError, NotImplementedError):
            # Symlinks not supported (e.g., Windows without admin rights)
            symlink_created = False

        scanner = FileScannerImpl(
            root_dir=str(temp_dir),
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favorite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files

        if symlink_created:
            # Should find ONLY the real file, NOT symlinks
            assert len(files) == 1
            assert files[0].path == str(real_file)
            assert not any("link.txt" in f.path for f in files)
        else:
            # Without symlink support, just verify real file is found
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

        monkeypatch.setattr(Path, 'stat', mocked_stat)  # ← is_symlink больше не нужно мокировать!

        scanner = FileScannerImpl(
            root_dir=str(temp_dir),
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favorite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files

        assert len(files) == 1
        assert "accessible.txt" in files[0].path

    def test_scanner_inclusive_size_boundaries(self, temp_dir):
        """
        Size filters must be inclusive: min_size <= file.size <= max_size.
        Critical boundary test: files exactly at min/max boundaries must be included.
        """
        # Create files at exact boundaries
        (temp_dir / "min_boundary.txt").write_bytes(b"A" * 1024)      # Exactly 1024 bytes
        (temp_dir / "just_above_min.txt").write_bytes(b"A" * 1025)    # 1025 bytes
        (temp_dir / "max_boundary.txt").write_bytes(b"B" * 2048)      # Exactly 2048 bytes
        (temp_dir / "just_below_max.txt").write_bytes(b"B" * 2047)    # 2047 bytes
        (temp_dir / "below_min.txt").write_bytes(b"C" * 1023)         # 1023 bytes (excluded)
        (temp_dir / "above_max.txt").write_bytes(b"D" * 2049)         # 2049 bytes (excluded)

        scanner = FileScannerImpl(
            root_dir=str(temp_dir),
            min_size=1024,   # Inclusive lower bound
            max_size=2048,   # Inclusive upper bound
            extensions=[".txt"],
            favorite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files

        # Should include: min_boundary, just_above_min, max_boundary, just_below_max (4 files)
        # Should exclude: below_min, above_max (2 files)
        assert len(files) == 4

        sizes = sorted([f.size for f in files])
        assert sizes == [1024, 1025, 2047, 2048]  # Exact boundaries INCLUDED