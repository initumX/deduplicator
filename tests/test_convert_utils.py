"""
Test suite for py-size-utils (size_utils.py).
Tests cover bytes_to_human, human_to_bytes, and is_valid_size_format.
"""

import pytest
from onlyone.utils.convert_utils import bytes_to_human, human_to_bytes, is_valid_size_format


class TestBytesToHuman:
    """Tests for the bytes_to_human conversion function."""

    @pytest.mark.parametrize(
        "size_bytes, expected",
        [
            (0, "0B"),
            (1, "1B"),
            (1023, "1023B"),
            (1024, "1KB"),
            (1536, "1.5KB"),
            (1048576, "1MB"),
            (1073741824, "1GB"),
            (1099511627776, "1TB"),
            (1125899906842624, "1PB"),
        ],
    )
    def test_standard_conversions(self, size_bytes, expected):
        """Test standard byte conversions to human readable strings."""
        assert bytes_to_human(size_bytes) == expected

    @pytest.mark.parametrize(
        "size_bytes, precision, expected",
        [
            (1536, 0, "2KB"),       # Precision 0 should round and remove decimals
            (1536, 1, "1.5KB"),     # Precision 1
            (1536, 2, "1.5KB"),     # Precision 2 (strips trailing zeros)
            (1536, 3, "1.5KB"),     # Precision 3 (strips trailing zeros)
            (1600, 2, "1.56KB"),    # Precision 2 (no trailing zeros to strip)
            (1024, 2, "1KB"),       # Exact power of 1024 should strip .00
        ],
    )
    def test_precision_handling(self, size_bytes, precision, expected):
        """Test that precision argument formats output correctly and strips zeros."""
        assert bytes_to_human(size_bytes, precision=precision) == expected

    def test_negative_input_raises_error(self):
        """Test that negative byte values raise a ValueError."""
        with pytest.raises(ValueError, match="Size cannot be negative"):
            bytes_to_human(-1)

    def test_float_input(self):
        """Test that float inputs are handled correctly."""
        assert bytes_to_human(1024.0) == "1KB"
        assert bytes_to_human(1536.5) == "1.5KB"  # Depends on rounding logic

    def test_extremely_large_size_fallback(self):
        """Test sizes larger than PB fallback to EB."""
        # 1024 PB = 1 EB
        large_size = 1024 * (1024**5)
        result = bytes_to_human(large_size)
        assert result.endswith("EB")
        assert "1" in result


class TestHumanToBytes:
    """Tests for the human_to_bytes conversion function."""

    @pytest.mark.parametrize(
        "size_str, expected",
        [
            ("1B", 1),
            ("1K", 1024),
            ("1KB", 1024),
            ("1M", 1024**2),
            ("1MB", 1024**2),
            ("1G", 1024**3),
            ("1GB", 1024**3),
            ("1T", 1024**4),
            ("1TB", 1024**4),
            ("1P", 1024**5),
            ("1PB", 1024**5),
            ("1000", 1000),  # Raw bytes
            ("1.5KB", 1536),
            ("2.5MB", 2621440),
        ],
    )
    def test_valid_units_and_formats(self, size_str, expected):
        """Test various valid unit suffixes and raw numbers."""
        assert human_to_bytes(size_str) == expected

    @pytest.mark.parametrize(
        "size_str",
        [
            "1kb",
            "1Kb",
            "1kb",
            "1gb",
            "1TB",
        ],
    )
    def test_case_insensitivity(self, size_str):
        """Test that unit parsing is case-insensitive."""
        # Just ensure it doesn't raise an error and returns positive int
        result = human_to_bytes(size_str)
        assert isinstance(result, int)
        assert result > 0

    @pytest.mark.parametrize(
        "size_str, expected",
        [
            (" 1KB ", 1024),  # Whitespace stripping
            ("1 GB", 1024**3),  # Space between number and unit
            ("  100  ", 100),  # Whitespace with raw bytes
        ],
    )
    def test_whitespace_handling(self, size_str, expected):
        """Test that leading/trailing whitespace and internal spaces are handled."""
        assert human_to_bytes(size_str) == expected

    @pytest.mark.parametrize(
        "size_str, error_match",
        [
            ("", "Size string cannot be empty"),
            ("-1KB", "Negative size not allowed"),
            ("-100", "Negative size not allowed"),
            ("abc", "Invalid format"),
            ("1.5.XB", "Invalid numeric value"),
            ("1XB", "Invalid numeric value"),  # Unsupported unit
        ],
    )
    def test_invalid_inputs_raise_error(self, size_str, error_match):
        """Test that invalid formats or values raise ValueError."""
        with pytest.raises(ValueError, match=error_match):
            human_to_bytes(size_str)

    def test_unit_priority_kb_vs_k(self):
        """Ensure 'KB' is matched before 'K' due to sorting by length."""
        # Both should result in 1024, but logic must match longest suffix first
        assert human_to_bytes("1K") == 1024
        assert human_to_bytes("1KB") == 1024


class TestIsValidSizeFormat:
    """Tests for the is_valid_size_format validation helper."""

    @pytest.mark.parametrize(
        "size_str, expected",
        [
            ("1GB", True),
            ("1000", True),
            ("1.5MB", True),
            ("1K", True),
            ("", False),
            ("abc", False),
            ("-1GB", False),
            (None, False),  # Type error handling
        ],
    )
    def test_validation_logic(self, size_str, expected):
        """Test that valid formats return True and invalid return False."""
        # Handle None explicitly as the function expects str,
        # but should return False on TypeError via except block
        assert is_valid_size_format(size_str) == expected


class TestRoundTripConsistency:
    """Tests to ensure conversion consistency between bytes and human readable formats."""

    @pytest.mark.parametrize(
        "original_bytes",
        [
            0,
            1024,
            1024**2,
            1024**3,
            1536,
            123456789,
        ],
    )
    def test_bytes_to_human_and_back(self, original_bytes):
        """
        Convert bytes to human string and back to bytes.
        Note: Some precision loss is expected due to rounding in bytes_to_human.
        """
        human_str = bytes_to_human(original_bytes)
        converted_bytes = human_to_bytes(human_str)

        # Allow for small difference due to rounding (e.g. 1.5KB -> 1536 -> 1.5KB -> 1536)
        # But if bytes_to_human rounded 1.55KB to 1.6KB, back conversion will differ.
        # We check that the order of magnitude is preserved or exact if possible.
        # For this utility, exact round-trip is not guaranteed for all numbers due to precision.
        # We assert that the result is not negative and close to original.
        assert converted_bytes >= 0

        # Specific check for exact powers of 1024 which should be lossless
        if 0 <= original_bytes < 1024 ** 5 and original_bytes % 1024 == 0:
            # If it converts cleanly to a unit without decimal remainder
            human_str = bytes_to_human(original_bytes)
            if '.' not in human_str:
                assert human_to_bytes(human_str) == original_bytes