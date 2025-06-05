"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License

utils/size_utils.py
"""

class SizeUtils:
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
                return f"{size_bytes:.1f}{unit}"
            size_bytes //= 1024
        return f"{size_bytes:.1f}EB"

    @staticmethod
    def human_to_bytes(size_str: str) -> int:
        """
        Convert human-readable size string to bytes.
        Supports formats like '1.5GB', '2048KB', '1000', etc.
        """
        size_str = size_str.strip().upper()
        units = {
            'B': 1,
            'KB': 1024,
            'MB': 1024 ** 2,
            'GB': 1024 ** 3,
            'TB': 1024 ** 4,
            'PB': 1024 ** 5,
        }

        for unit in sorted(units.keys(), key=lambda u: -len(u)):
            if size_str.endswith(unit):
                value_str = size_str[:-len(unit)].strip()
                try:
                    return int(float(value_str) * units[unit])
                except ValueError:
                    raise ValueError(f"Invalid numeric value in size: '{value_str}'")

        # If no unit specified, assume bytes
        try:
            return int(size_str)
        except ValueError:
            raise ValueError(
                f"Invalid size format: '{size_str}'. "
                f"Supported formats: 1.5GB, 2048KB, 1000, etc."
            )

    @staticmethod
    def is_valid_size_format(size_str: str) -> bool:
        """
        Check if the input string has a valid size format.
        """
        try:
            SizeUtils.human_to_bytes(size_str)
            return True
        except ValueError:
            return False