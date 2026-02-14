"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License

utils/convert_utils.py
"""
import time

class ConvertUtils:
    @staticmethod
    def bytes_to_human(size_bytes: int) -> str:
        """
        Convert bytes to human-readable string (e.g., 1.5KB, 3.2MB).
        """
        if size_bytes < 0:
            return "0B"

        units = ["B", "KB", "MB", "GB", "TB", "PB"]
        for unit in units:
            if size_bytes < 1024:
                return f"{size_bytes:.2f}{unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f}EB"

    @staticmethod
    def human_to_bytes(size_str: str) -> int:
        """
        Convert human-readable size string to bytes.
        Supports formats: '1.5GB', '2048KB', '1000', '1K', '1M', '1G', etc.
        Raises ValueError for negative sizes or invalid formats.
        """
        size_str = size_str.strip().upper()

        # Define units with both full (KB) and short (K) forms
        units = {
            'PB': 1024 ** 5, 'P': 1024 ** 5,
            'TB': 1024 ** 4, 'T': 1024 ** 4,
            'GB': 1024 ** 3, 'G': 1024 ** 3,
            'MB': 1024 ** 2, 'M': 1024 ** 2,
            'KB': 1024, 'K': 1024,
            'B': 1,
        }

        # Check for unit suffix (longest first to avoid 'KB' matching as 'K' + 'B')
        for unit in sorted(units.keys(), key=len, reverse=True):
            if size_str.endswith(unit):
                value_str = size_str[:-len(unit)].strip()
                try:
                    value = float(value_str)
                except ValueError:
                    raise ValueError(f"Invalid numeric value in size: '{value_str}'")

                if value < 0:
                    raise ValueError(f"Negative size not allowed: '{size_str}'")
                return int(value * units[unit])

        # No unit specified — treat as bytes
        try:
            value = int(size_str)
        except ValueError:
            raise ValueError(
                f"Invalid size format: '{size_str}'. "
                f"Supported formats: 1.5GB, 2048KB, 1000, 1K, 1M, etc."
            )

        if value < 0:
            raise ValueError(f"Negative size not allowed: '{size_str}'")
        return value

    @staticmethod
    def is_valid_size_format(size_str: str) -> bool:
        """
        Check if the input string has a valid size format.
        """
        try:
            ConvertUtils.human_to_bytes(size_str)
            return True
        except ValueError:
            return False

    @staticmethod
    def timestamp_to_human(timestamp: float, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
        """
        Convert a Unix timestamp to a human-readable string.
        Uses local time by default.
        """
        try:
            return time.strftime(fmt, time.localtime(timestamp))
        except Exception:
            return "Invalid timestamp"

    @staticmethod
    def is_valid_timestamp(timestamp: float) -> bool:
        """
        Check if the given timestamp is valid.
        """
        try:
            if not isinstance(timestamp, (int, float)):
                return False
            if timestamp < 0 or timestamp > 32536771199:  # Year 3000
                return False
            time.localtime(timestamp)
            return True
        except Exception:
            return False