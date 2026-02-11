"""
Tests for size conversion utilities — critical for correct file filtering.
"""
import pytest
from deduplicator.utils.convert_utils import ConvertUtils


class TestHumanToBytes:
    """Test conversion from human-readable sizes (e.g., "500KB") to bytes."""

    def test_bytes_without_suffix(self):
        """Plain numbers should be interpreted as bytes."""
        assert ConvertUtils.human_to_bytes("0") == 0
        assert ConvertUtils.human_to_bytes("1") == 1
        assert ConvertUtils.human_to_bytes("1024") == 1024
        assert ConvertUtils.human_to_bytes("500000") == 500000

    def test_bytes_with_b_suffix(self):
        """Explicit 'B' suffix should work."""
        assert ConvertUtils.human_to_bytes("0B") == 0
        assert ConvertUtils.human_to_bytes("1B") == 1
        assert ConvertUtils.human_to_bytes("1024B") == 1024

    def test_kilobytes(self):
        """KB suffix should multiply by 1024 (binary, not decimal)."""
        assert ConvertUtils.human_to_bytes("1KB") == 1024
        assert ConvertUtils.human_to_bytes("1K") == 1024  # Alternative form
        assert ConvertUtils.human_to_bytes("1.5KB") == 1536  # Decimal support
        assert ConvertUtils.human_to_bytes("0.5KB") == 512
        assert ConvertUtils.human_to_bytes("1024KB") == 1024 * 1024  # 1 MB

    def test_megabytes(self):
        """MB suffix should multiply by 1024*1024."""
        assert ConvertUtils.human_to_bytes("1MB") == 1024 * 1024
        assert ConvertUtils.human_to_bytes("1M") == 1024 * 1024
        assert ConvertUtils.human_to_bytes("1.5MB") == int(1.5 * 1024 * 1024)
        assert ConvertUtils.human_to_bytes("100MB") == 100 * 1024 * 1024

    def test_gigabytes(self):
        """GB suffix should multiply by 1024*1024*1024."""
        assert ConvertUtils.human_to_bytes("1GB") == 1024 * 1024 * 1024
        assert ConvertUtils.human_to_bytes("1G") == 1024 * 1024 * 1024
        assert ConvertUtils.human_to_bytes("0.5GB") == 512 * 1024 * 1024
        assert ConvertUtils.human_to_bytes("100GB") == 100 * 1024 * 1024 * 1024

    def test_case_insensitivity(self):
        """Suffixes should be case-insensitive."""
        assert ConvertUtils.human_to_bytes("1kb") == 1024
        assert ConvertUtils.human_to_bytes("1Kb") == 1024
        assert ConvertUtils.human_to_bytes("1KB") == 1024
        assert ConvertUtils.human_to_bytes("1mb") == 1024 * 1024

    def test_whitespace_tolerance(self):
        """Whitespace around values should be ignored."""
        assert ConvertUtils.human_to_bytes(" 1KB ") == 1024
        assert ConvertUtils.human_to_bytes("\t1MB\n") == 1024 * 1024

    def test_rejects_negative_values(self):
        """Negative sizes are invalid for file filtering (security critical)."""
        with pytest.raises(ValueError, match="Negative size not allowed"):
            ConvertUtils.human_to_bytes("-1")
        with pytest.raises(ValueError, match="Negative size not allowed"):
            ConvertUtils.human_to_bytes("-1KB")
        with pytest.raises(ValueError, match="Negative size not allowed"):
            ConvertUtils.human_to_bytes("-1K")  # Short form

    def test_rejects_invalid_formats(self):
        """Garbage input must raise ValueError."""
        with pytest.raises(ValueError):
            ConvertUtils.human_to_bytes("")
        with pytest.raises(ValueError):
            ConvertUtils.human_to_bytes("invalid")
        with pytest.raises(ValueError):
            ConvertUtils.human_to_bytes("1.2.3KB")  # Multiple dots
        with pytest.raises(ValueError):
            ConvertUtils.human_to_bytes("1KB2")  # Suffix in middle
        with pytest.raises(ValueError):
            ConvertUtils.human_to_bytes("1 XB")  # Unknown suffix

    def test_rejects_suffixes_without_number(self):
        """Suffix alone is invalid."""
        with pytest.raises(ValueError):
            ConvertUtils.human_to_bytes("KB")
        with pytest.raises(ValueError):
            ConvertUtils.human_to_bytes("MB")


class TestBytesToHuman:
    """Test conversion from bytes to human-readable format."""

    def test_zero_bytes(self):
        """Zero should format as '0.00B'."""
        assert ConvertUtils.bytes_to_human(0) == "0.00B"

    def test_bytes_range(self):
        """Values under 1KB should show as bytes."""
        assert ConvertUtils.bytes_to_human(1) == "1.00B"
        assert ConvertUtils.bytes_to_human(512) == "512.00B"
        assert ConvertUtils.bytes_to_human(1023) == "1023.00B"

    def test_kilobytes_range(self):
        """Values 1KB–1023KB should show as KB."""
        assert ConvertUtils.bytes_to_human(1024) == "1.00KB"
        assert ConvertUtils.bytes_to_human(1536) == "1.50KB"  # 1.5KB
        assert ConvertUtils.bytes_to_human(1024 * 500) == "500.00KB"

    def test_megabytes_range(self):
        """Values 1MB–1023MB should show as MB."""
        assert ConvertUtils.bytes_to_human(1024 * 1024) == "1.00MB"
        assert ConvertUtils.bytes_to_human(int(1.5 * 1024 * 1024)) == "1.50MB"
        assert ConvertUtils.bytes_to_human(100 * 1024 * 1024) == "100.00MB"

    def test_gigabytes_range(self):
        """Values >=1GB should show as GB."""
        assert ConvertUtils.bytes_to_human(1024 * 1024 * 1024) == "1.00GB"
        assert ConvertUtils.bytes_to_human(500 * 1024 * 1024 * 1024) == "500.00GB"

    def test_precision(self):
        """Should show exactly 2 decimal places."""
        assert ConvertUtils.bytes_to_human(1500) == "1.46KB"  # 1500/1024 = 1.4648...
        assert ConvertUtils.bytes_to_human(1024 * 1024 + 512 * 1024) == "1.50MB"  # 1.5MB exactly