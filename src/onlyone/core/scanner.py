"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License

core/scanner.py
Implements file scanning functionality using object-oriented design and modern pathlib.

Features:
- Uses pathlib.Path for robust, cross-platform path handling
- Recursively scans multiple root directories
- Applies size and extension filters
- Prevents duplicate file processing when root directories overlap
- Returns a List containing scanned files
"""
import os
import sys
from typing import List, Optional, Callable, Set, Dict
from pathlib import Path
import time
import logging

logger = logging.getLogger(__name__)

# Local imports
from onlyone.core.models import File, DeduplicationParams


class FileScanner:
    """
    Scans directories recursively and filters files based on size and extensions.
    Uses `pathlib.Path` for safe and consistent cross-platform behavior.
    Supports multiple root directories with overlap protection.

    Attributes:
        root_dirs: List of root directories to scan
        min_size: Minimum file size in bytes (optional)
        max_size: Maximum file size in bytes (optional)
        extensions: List of allowed file extensions (e.g., [".txt", ".jpg"])
        favourite_dirs: Directories marked as favourites for special processing
        excluded_dirs: Directories to ignore during scanning
    """

    def __init__(self, params: DeduplicationParams):
        """
        Initialize the scanner with validated parameters.

        Args:
            params: DeduplicationParams object containing all configuration.
        """
        # Use normalized roots from params (already validated and resolved)
        self.root_dirs = params.normalized_root_dirs
        self.min_size = params.min_size_bytes
        self.max_size = params.max_size_bytes
        self.extensions = params.normalized_extensions
        self._exclude_mode = (params.extension_filter_mode == "blacklist")

        # Normalize favourite and excluded directories for consistent comparison
        self.favourite_dirs = [str(Path(d).resolve()) for d in params.favourite_dirs] if params.favourite_dirs else []
        self.excluded_dirs = [str(Path(d).resolve()) for d in params.excluded_dirs] if params.excluded_dirs else []

    def scan(
        self,
        stopped_flag: Optional[Callable[[], bool]] = None,
        progress_callback: Optional[Callable[[str, int, object], None]] = None
    ) -> List[File]:
        """
        Single-pass scanner with real-time progress updates and debug logging.
        Scans all configured root directories.
        Prevents processing the same file twice if root directories overlap.

        Args:
            stopped_flag: Function that returns True if operation should be canceled.
            progress_callback: Callback for reporting progress (stage, current, total).

        Returns:
            List[File]: Filtered list of files found in the directory tree.
        """
        logger.debug("Starting scan operation")
        logger.debug(f"Root directories: {self.root_dirs}")
        logger.debug(f"Filters: min_size={self.min_size}, max_size={self.max_size}, extensions={self.extensions}")

        found_files: List[File] = []
        # Track resolved absolute paths to prevent duplicates when roots overlap
        seen_paths: Set[str] = set()

        processed_files = 0

        stats = {
            "skipped_size": 0,
            "skipped_ext": 0,
            "skipped_symlink": 0,
        }

        # Check for cancellation before starting
        if stopped_flag and stopped_flag():
            logger.debug("Scan cancelled before start")
            return []

        # Progress throttling: update every 200ms for smooth UI updates
        progress_interval = 0.2  # seconds
        last_progress_time = time.time()

        try:
            start_time = time.time()

            for root_dir in self.root_dirs:
                root_path = Path(root_dir)

                # Validate root directory exists and is accessible
                if not root_path.exists():
                    logger.warning(f"Directory does not exist (skipping): {root_dir}")
                    continue

                if not root_path.is_dir():
                    logger.warning(f"Not a directory (skipping): {root_dir}")
                    continue

                logger.debug(f"Scanning directory: {root_dir}")

                # Use os.walk instead of Path.rglob for faster traversal
                for root, dirs, files in os.walk(str(root_path)):
                    # Check for cancellation at each directory level
                    if stopped_flag and stopped_flag():
                        logger.debug("Scan interrupted by user")
                        return []

                    # Pre-filter subdirectories BEFORE os.walk enters them
                    dirs[:] = [d for d in dirs if self._prefilter_dirs(Path(root) / d)]

                    for filename in files:
                        path = Path(root) / filename
                        # avoid symlinks BEFORE resolve
                        try:
                            if path.is_symlink():
                                logger.debug(f"Skipping symbolic link: {path}")
                                continue
                        except (OSError, PermissionError):
                            continue

                        # Resolve absolute path to detect overlaps across different roots
                        try:
                            resolved_path = str(path.resolve())
                        except (OSError, ValueError):
                            # If resolution fails, skip file to avoid crashes
                            logger.debug(f"Could not resolve path (skipping): {path}")
                            continue

                        # Skip if already processed (overlap protection)
                        if resolved_path in seen_paths:
                            logger.debug(f"Duplicate path detected (skipping): {resolved_path}")
                            continue

                        seen_paths.add(resolved_path)

                        file_info = self._process_file(path, stopped_flag=stopped_flag, stats=stats)
                        if file_info:
                            found_files.append(file_info)
                            processed_files += 1

                            # Timer-based progress throttling
                            current_time = time.time()
                            if progress_callback and (current_time - last_progress_time) >= progress_interval:
                                progress_callback('scanning', processed_files, None)
                                last_progress_time = current_time

            # Final progress update for remaining count
            if progress_callback:
                progress_callback('scanning', processed_files, None)

            end_time = time.time()
            elapsed_time = end_time - start_time
            logger.debug(f"Total scan time: {elapsed_time:.2f} seconds")
            logger.debug(f"Scan completed. Found {len(found_files)} matching files.")

        except PermissionError as pe:
            logger.warning(f"Permission denied during scan: {pe}")
        except Exception:
            logger.exception("Unexpected error during scanning")
            raise

        if any(stats.values()):
            logger.info(
                f"Skipped "
                f"{stats['skipped_size']} files because of size filter, "
                f"{stats['skipped_ext']} files because of extension filter, "
                f"and {stats['skipped_symlink']} symlink"
            )

        return found_files

    @staticmethod
    def _is_system_trash(path: Path) -> bool:
        """
        Check if path belongs to OS trash/recycle bin (cross-platform).
        Returns False on any error (fail-safe: better to scan than skip valid data).

        Args:
            path: Path object to check.

        Returns:
            bool: True if path is within system trash, False otherwise.
        """
        try:
            # Resolve to absolute path for reliable substring matching
            path_str = str(path.resolve(strict=False))
            if sys.platform == "win32":
                # Windows: $Recycle.Bin on system drive (C: by default)
                if "$Recycle.Bin" in path_str or "\\Recycler\\" in path_str:
                    return True
            elif sys.platform == "darwin":
                # macOS: user-specific .Trash
                if "/.Trash/" in path_str or path_str.endswith("/.Trash"):
                    return True
            else:
                # Linux/BSD: freedesktop.org standard locations
                if ".local/share/Trash" in path_str or "/.trash/" in path_str:
                    return True
            return False
        except (OSError, ValueError):
            # Fail-safe: on any filesystem error, assume NOT trash
            return False

    @staticmethod
    def _is_excluded_directory(path: Path, excluded_dirs: List[str]) -> bool:
        """
        Check if path is within an excluded directory.

        Args:
            path: Path object to check.
            excluded_dirs: List of normalized excluded directory paths.

        Returns:
            bool: True if path is excluded, False otherwise.
        """
        try:
            path_str = str(path.resolve(strict=False))
            for excluded_dir in excluded_dirs:
                normalized_excluded = os.path.normpath(excluded_dir)
                if path_str.startswith(normalized_excluded + os.sep) or \
                   path_str == normalized_excluded:
                    return True
            return False
        except (OSError, ValueError):
            return False

    def _prefilter_dirs(self, path: Path) -> bool:
        """
        Pre-filter directories: skip system trash and inaccessible locations.

        Args:
            path: Path object of the directory to check.

        Returns:
            bool: True if directory should be scanned, False if skipped.
        """
        # Skip system trash directories to avoid rescanning deleted files
        if FileScanner._is_system_trash(path):
            return False

        if self.excluded_dirs and self._is_excluded_directory(path, self.excluded_dirs):
            return False

        # Skip inaccessible directories
        try:
            return path.is_dir() and os.access(path, os.R_OK | os.X_OK)
        except (OSError, PermissionError):
            logger.warning(f"Skipping inaccessible directory: {path}")
            return False

    def _process_file(
        self,
        path: Path,
        stopped_flag: Optional[Callable[[], bool]] = None,
        stats: Optional[Dict[str, int]] = None,
    ) -> Optional[File]:
        """
        Process an individual file path and return a File if it passes all filters.

        Args:
            path: Path object pointing to the file.
            stopped_flag: Function that returns True if operation should be stopped.

        Returns:
            Optional[File]: File object if it passes filters, else None.
        """
        if stopped_flag and stopped_flag():
            return None

        try:
            if path.is_symlink():
                stats["skipped_symlink"] += 1
                return None
        except PermissionError:
            logger.warning(f"Permission denied checking symlink: {path}")
            return None
        except OSError as e:
            logger.warning(f"Error checking symlink status for {path}: {e}")
            return None

        try:
            # Get file size directly
            stat_result = path.stat()
            size = stat_result.st_size
        except PermissionError:
            logger.warning(f"Permission denied getting file size: {path}")
            return None
        except OSError as e:
            logger.warning(f"Error getting file size for {path}: {e}")
            return None

        # Skip zero-byte files
        if size == 0:
            return None

        # Apply size filter
        if not self._size_passes(size):
            stats["skipped_size"] += 1
            return None

        # Apply extension filter
        if not self._extension_passes(path):
            stats["skipped_ext"] += 1
            return None

        try:
            path_depth = str(path).rstrip(os.sep).count(os.sep)  # Number of path separators
            file = File(
                path=str(path),
                size=size,
                path_depth=path_depth
            )
        except Exception as e:
            logger.debug(f"Failed to create File object for {path}: {e}")
            return None

        if self.favourite_dirs:
            try:
                file.set_favourite_status(self.favourite_dirs)
            except Exception as e:
                logger.debug(f"Error setting favourite status for {path}: {e}")
                # Continue processing — favourite status is optional metadata

        return file

    def _size_passes(self, size: int) -> bool:
        """
        Check if file size is within configured limits.

        Args:
            size: File size in bytes.

        Returns:
            bool: True if file meets size criteria.
        """
        if self.min_size is not None and size < self.min_size:
            return False
        if self.max_size is not None and size > self.max_size:
            return False
        return True

    def _extension_passes(self, path: Path) -> bool:
        """
        Check if a file matches the configured extension filter rules.

        Filter modes:
        - If extensions list starts with "^" (as a separate first element):
          BLACKLIST mode — exclude files whose extensions are in the list.
        - Otherwise: WHITELIST mode — include only files whose extensions are in the list.
        - Empty list: no filtering applied (all extensions pass).

        Args:
            path: Path object pointing to the file.

        Returns:
            bool: True if the file passes the extension filter, False otherwise.
        """
        if not self.extensions:
            return True

        ext = path.suffix.lower()

        if self._exclude_mode:
            # Blacklist mode: accept file if its extension is NOT in the exclude list
            if ext in self.extensions:
                logger.debug(f"Skipping {path} (extension '{ext}' is excluded)")
                return False
            return True
        else:
            # Whitelist mode: accept file only if its extension IS in the allow list
            if ext in self.extensions:
                return True
            logger.debug(f"Skipping {path} (extension '{ext}' not in allowed list)")
            return False