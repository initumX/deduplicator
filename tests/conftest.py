"""
Shared fixtures for deduplication core tests.
Creates isolated temporary directories with controlled test files.
"""
import pytest
import tempfile
from pathlib import Path
from typing import Dict
import sys

# Add project root to sys.path so 'core' package is importable
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

@pytest.fixture
def temp_dir():
    """Creates isolated temporary directory, auto-cleanup after test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_files(temp_dir) -> Dict[str, Path]:
    """
    Creates controlled test files for deduplication scenarios:
    - 2 identical files (duplicates)
    - 2 unique files (different content)
    - 1 empty file (should be filtered by scanner)
    - 1 file with .tmp extension (should be filtered)
    """
    files = {}

    # Duplicate pair #1 (1KB of 'A')
    content_a = b"A" * 1024
    files["dup1_a"] = temp_dir / "dup1_a.txt"
    files["dup1_b"] = temp_dir / "dup1_b.txt"
    files["dup1_a"].write_bytes(content_a)
    files["dup1_b"].write_bytes(content_a)

    # Duplicate pair #2 (2KB of 'B')
    content_b = b"B" * 2048
    files["dup2_a"] = temp_dir / "dup2_a.txt"
    files["dup2_b"] = temp_dir / "dup2_b.txt"
    files["dup2_a"].write_bytes(content_b)
    files["dup2_b"].write_bytes(content_b)

    # Unique files
    files["unique1"] = temp_dir / "unique1.txt"
    files["unique1"].write_bytes(b"C" * 1500)
    files["unique2"] = temp_dir / "unique2.txt"
    files["unique2"].write_bytes(b"D" * 2500)

    # Empty file (should be filtered by scanner - 0 bytes)
    files["empty"] = temp_dir / "empty.txt"
    files["empty"].write_bytes(b"")

    # Filtered file (wrong extension)
    files["filtered"] = temp_dir / "ignore.tmp"
    files["filtered"].write_bytes(b"E" * 1024)

    # Subdirectory with duplicates
    subdir = temp_dir / "subdir"
    subdir.mkdir()
    files["sub_dup"] = subdir / "dup_in_subdir.txt"
    files["sub_dup"].write_bytes(content_a)  # Same as dup1_a/b

    return files