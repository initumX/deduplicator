"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License

core/measurer.py

This module provides functions to handle file size conversions,
making it easier to display storage information in UIs, logs, or APIs.
"""

from typing import Union

# Define conversion constants globally for performance.
# Using binary prefixes (1 KB = 1024 bytes) as is standard in most OS file systems.
_UNITS = {
    'PB': 1024 ** 5, 'P': 1024 ** 5,
    'TB': 1024 ** 4, 'T': 1024 ** 4,
    'GB': 1024 ** 3, 'G': 1024 ** 3,
    'MB': 1024 ** 2, 'M': 1024 ** 2,
    'KB': 1024, 'K': 1024,
    'B': 1,
}

def bytes_to_human(size_bytes: Union[int, float], precision: int = 2) -> str:
    """
    Convert bytes to a human-readable string representation.

    Args:
        size_bytes (int | float): The size in bytes to convert.
        precision (int): Number of decimal places to display. Defaults to 2.

    Returns:
        str: A human-readable string (e.g., "1.5KB", "3MB", "0B").

    Raises:
        ValueError: If the input size is negative.

    Examples:
        >>> bytes_to_human(0)
        '0B'
        >>> bytes_to_human(1024)
        '1KB'
        >>> bytes_to_human(1536)
        '1.5KB'
        >>> bytes_to_human(1048576)
        '1MB'
    """
    if size_bytes < 0:
        raise ValueError("Size cannot be negative")

    # Handle zero explicitly to avoid division logic
    if size_bytes == 0:
        return "0B"

    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = float(size_bytes)

    for unit in units:
        if size < 1024:
            # Format the number with specified precision
            formatted = f"{size:.{precision}f}{unit}"
            # Remove trailing zeros and decimal point for cleaner output (e.g., "1.00KB" -> "1KB")
            if precision > 0:
                # Split number and unit, strip zeros from number only
                num_str = formatted[:-len(unit)]
                # Remove trailing zeros then trailing decimal point
                num_str = num_str.rstrip('0').rstrip('.')
                return f"{num_str}{unit}"
            return formatted
        size /= 1024

    # Fallback for extremely large sizes (Exabytes)
    return f"{size:.{precision}f}EB"

def human_to_bytes(size_str: str) -> int:
    """
    Convert a human-readable size string back to bytes.

    Supports formats with or without spaces, case-insensitive.
    Examples: '1.5GB', '2048KB', '1000', '1K', '1M', '1G'.

    Args:
        size_str (str): The human-readable size string.

    Returns:
        int: The size in bytes.

    Raises:
        ValueError: If the format is invalid or the value is negative.

    Examples:
        >>> human_to_bytes("1KB")
        1024
        >>> human_to_bytes("1.5MB")
        1572864
        >>> human_to_bytes("1000")
        1000
    """
    if not size_str:
        raise ValueError("Size string cannot be empty")

    size_str = size_str.strip().upper()

    # Check for unit suffixes.
    # Sort by length (descending) to ensure 'KB' is matched before 'K'.
    for unit in sorted(_UNITS.keys(), key=len, reverse=True):
        if size_str.endswith(unit):
            value_str = size_str[:-len(unit)].strip()
            try:
                value = float(value_str)
            except ValueError:
                raise ValueError(f"Invalid numeric value: '{value_str}'")

            if value < 0:
                raise ValueError("Negative size not allowed")
            return int(value * _UNITS[unit])

    # No unit specified — treat as raw bytes
    try:
        value = float(size_str)
    except ValueError:
        raise ValueError(f"Invalid format: '{size_str}'. Expected formats: '1.5GB', '1000', '1K', etc.")

    if value < 0:
        raise ValueError("Negative size not allowed")
    return int(value)

def is_valid_size_format(size_str: str) -> bool:
    """
    Check if the input string has a valid size format.
    """
    try:
        human_to_bytes(size_str)
        return True
    except (ValueError, TypeError):
        return False