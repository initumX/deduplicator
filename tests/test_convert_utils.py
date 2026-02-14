"""
Unit tests for ConvertUtils - size/timestamp conversion helpers.
"""
import pytest
from onlyone.utils.convert_utils import ConvertUtils


class TestConvertUtils:
    """Test size and timestamp conversion utilities."""

    # === bytes_to_human ===

    def test_bytes_to_human_zero(self):
        """0 bytes should convert to '0.00B'."""
        assert ConvertUtils.bytes_to_human(0) == "0.00B"

    def test_bytes_to_human_small_values(self):
        """Values < 1024 should stay in bytes."""
        assert ConvertUtils.bytes_to_human(1) == "1.00B"
        assert ConvertUtils.bytes_to_human(512) == "512.00B"
        assert ConvertUtils.bytes_to_human(1023) == "1023.00B"

    def test_bytes_to_human_boundary_transitions(self):
        """Exact boundaries should transition to next unit."""
        assert ConvertUtils.bytes_to_human(1024) == "1.00KB"
        assert ConvertUtils.bytes_to_human(1024 * 1024) == "1.00MB"
        assert ConvertUtils.bytes_to_human(1024 * 1024 * 1024) == "1.00GB"

    def test_bytes_to_human_negative(self):
        """Negative sizes should return '0B'."""
        assert ConvertUtils.bytes_to_human(-1) == "0B"
        assert ConvertUtils.bytes_to_human(-1000000) == "0B"

    def test_bytes_to_human_large_values(self):
        """Large values should scale to appropriate units."""
        assert "TB" in ConvertUtils.bytes_to_human(1024 ** 4)
        assert "PB" in ConvertUtils.bytes_to_human(1024 ** 5)

    # === human_to_bytes ===

    def test_human_to_bytes_without_unit(self):
        """Plain numbers should be treated as bytes."""
        assert ConvertUtils.human_to_bytes("1024") == 1024
        assert ConvertUtils.human_to_bytes("0") == 0
        assert ConvertUtils.human_to_bytes("1") == 1

    def test_human_to_bytes_with_full_units(self):
        """Full unit suffixes (KB, MB, GB) should be parsed correctly."""
        assert ConvertUtils.human_to_bytes("1KB") == 1024
        assert ConvertUtils.human_to_bytes("1.5KB") == 1536
        assert ConvertUtils.human_to_bytes("2MB") == 2 * 1024 * 1024
        assert ConvertUtils.human_to_bytes("1.5GB") == int(1.5 * 1024 ** 3)

    def test_human_to_bytes_with_short_units(self):
        """Short unit suffixes (K, M, G) should be parsed correctly."""
        assert ConvertUtils.human_to_bytes("1K") == 1024
        assert ConvertUtils.human_to_bytes("2M") == 2 * 1024 * 1024
        assert ConvertUtils.human_to_bytes("1G") == 1024 ** 3

    def test_human_to_bytes_case_insensitive(self):
        """Unit parsing should be case-insensitive."""
        assert ConvertUtils.human_to_bytes("1kb") == 1024
        assert ConvertUtils.human_to_bytes("1KB") == 1024
        assert ConvertUtils.human_to_bytes("1Kb") == 1024

    def test_human_to_bytes_whitespace_around_value(self):
        """Surrounding whitespace should be ignored."""
        assert ConvertUtils.human_to_bytes(" 1KB ") == 1024
        assert ConvertUtils.human_to_bytes("\t1MB\n") == 1024 * 1024

    def test_human_to_bytes_zero_values(self):
        """Zero values should parse correctly."""
        assert ConvertUtils.human_to_bytes("0") == 0
        assert ConvertUtils.human_to_bytes("0KB") == 0
        assert ConvertUtils.human_to_bytes("0.0MB") == 0

    def test_human_to_bytes_rejects_negative(self):
        """Negative sizes must raise ValueError."""
        with pytest.raises(ValueError, match="Negative size"):
            ConvertUtils.human_to_bytes("-100")
        with pytest.raises(ValueError, match="Negative size"):
            ConvertUtils.human_to_bytes("-1KB")

    def test_human_to_bytes_rejects_invalid_formats(self):
        """Invalid formats must raise ValueError."""
        with pytest.raises(ValueError, match="Invalid size format"):
            ConvertUtils.human_to_bytes("abc")
        with pytest.raises(ValueError, match="Invalid numeric value"):
            ConvertUtils.human_to_bytes("xyzKB")

    def test_human_to_bytes_boundary_values(self):
        """Boundary values should convert precisely."""
        assert ConvertUtils.human_to_bytes("1024B") == 1024
        assert ConvertUtils.human_to_bytes("1KB") == 1024
        assert ConvertUtils.human_to_bytes("1024KB") == 1024 * 1024

    # === is_valid_size_format ===

    def test_is_valid_size_format_accepts_valid(self):
        """Valid size formats should return True."""
        assert ConvertUtils.is_valid_size_format("1024")
        assert ConvertUtils.is_valid_size_format("1KB")
        assert ConvertUtils.is_valid_size_format("1.5GB")
        assert ConvertUtils.is_valid_size_format("0")

    def test_is_valid_size_format_rejects_invalid(self):
        """Invalid size formats should return False."""
        assert not ConvertUtils.is_valid_size_format("abc")
        assert not ConvertUtils.is_valid_size_format("-100")