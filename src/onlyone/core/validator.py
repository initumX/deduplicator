"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License

core/validator.py
Centralized validation logic for deduplication parameters.
"""
import logging
from pathlib import Path
from typing import List, Tuple, Optional
from enum import Enum
from onlyone.core.measurer import bytes_to_human

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when parameter validation fails."""
    def __init__(self, message: str, field: Optional[str] = None):
        self.field = field
        super().__init__(message)


class FilterMode(str, Enum):
    """Extension filter mode."""
    WHITELIST = "whitelist"
    BLACKLIST = "blacklist"


class PathValidator:
    """Utility class for path-related validation and normalization."""

    @staticmethod
    def normalize_path(path_str: str, *, require_exists: bool = True, require_dir: bool = True) -> str:
        """Normalize a single path string."""
        if not path_str or not isinstance(path_str, str):
            raise ValidationError("Path must be a non-empty string")

        path = Path(path_str).expanduser().resolve()

        if require_exists and not path.exists():
            raise ValidationError(f"Path does not exist: {path_str}", field="path")

        if require_dir and not path.is_dir():
            raise ValidationError(f"Path is not a directory: {path_str}", field="path")

        return str(path)

    @staticmethod
    def normalize_path_list(
            paths: List[str],
            *,
            require_exists: bool = True,
            require_dir: bool = True,
            field_name: str = "paths"
    ) -> List[str]:
        """Normalize and validate a list of paths."""
        if not paths:
            return []

        if not isinstance(paths, list):
            raise ValidationError(f"{field_name} must be a list of strings", field=field_name)

        normalized = []
        for i, path_str in enumerate(paths):
            try:
                norm_path = PathValidator.normalize_path(
                    path_str,
                    require_exists=require_exists,
                    require_dir=require_dir
                )
                normalized.append(norm_path)
            except ValidationError as e:
                raise ValidationError(f"{field_name}[{i}]: {e}", field=field_name)

        # Remove duplicates while preserving order
        seen = set()
        result = []
        for p in normalized:
            if p not in seen:
                seen.add(p)
                result.append(p)

        return result

    @staticmethod
    def is_subpath(child: str, parent: str) -> bool:
        """
        Check if child path is a STRICT subpath of parent.
        Returns False if paths are identical.
        """
        try:
            child_resolved = Path(child).resolve()
            parent_resolved = Path(parent).resolve()

            if child_resolved == parent_resolved:
                return False

            child_resolved.relative_to(parent_resolved)
            return True
        except ValueError:
            return False


class ExtensionValidator:
    """Utility class for extension-related validation and normalization."""

    @staticmethod
    def normalize_extensions(extensions: List[str]) -> Tuple[List[str], FilterMode]:
        """Normalize extension list with forgiving input handling."""
        if not extensions:
            return [], FilterMode.WHITELIST

        normalized = []
        filter_mode = FilterMode.WHITELIST
        seen = set()

        for ext in extensions:
            if not ext:
                continue

            ext_clean = str(ext).strip().lower()
            if not ext_clean:
                continue

            if ext_clean == "^":
                filter_mode = FilterMode.BLACKLIST
                continue

            if ext_clean.startswith("^"):
                filter_mode = FilterMode.BLACKLIST
                ext_clean = ext_clean[1:].strip()
                if not ext_clean:
                    continue

            if not ext_clean.startswith('.'):
                ext_clean = f".{ext_clean}"

            if ext_clean not in seen:
                seen.add(ext_clean)
                normalized.append(ext_clean)

        return normalized, filter_mode


class SizeValidator:
    """Utility class for size-related validation."""

    @staticmethod
    def validate_size_range(min_bytes: int, max_bytes: int) -> None:
        """Validate that size range is logical."""
        if min_bytes < 0:
            raise ValidationError("Minimum size cannot be negative", field="min_size")

        if max_bytes < min_bytes:
            raise ValidationError(
                f"Maximum size ({bytes_to_human(max_bytes)}) "
                f"cannot be less than minimum size ({bytes_to_human(min_bytes)})",
                field="max_size"
            )


class DeduplicationParamsValidator:
    """Main validator class for deduplication parameters."""

    def __init__(
            self,
            root_dirs: List[str],
            min_size_bytes: int,
            max_size_bytes: int,
            extensions: Optional[List[str]] = None,
            favourite_dirs: Optional[List[str]] = None,
            excluded_dirs: Optional[List[str]] = None,
    ):
        self.root_dirs_raw = root_dirs or []
        self.min_size_bytes = min_size_bytes
        self.max_size_bytes = max_size_bytes
        self.extensions_raw = extensions or []
        self.favourite_dirs_raw = favourite_dirs or []
        self.excluded_dirs_raw = excluded_dirs or []

        self.root_dirs: List[str] = []
        self.excluded_dirs: List[str] = []
        self.favourite_dirs: List[str] = []
        self.normalized_extensions: List[str] = []
        self.extension_filter_mode: FilterMode = FilterMode.WHITELIST

    def validate_all(self) -> None:
        """Run complete validation pipeline."""
        self._validate_sizes()
        self._normalize_and_validate_paths()
        self._normalize_extensions()

        # Cross-field validation
        self._validate_root_vs_excluded()
        self._validate_favourite_vs_excluded()
        self._validate_favourite_within_roots()

    def _validate_sizes(self) -> None:
        SizeValidator.validate_size_range(self.min_size_bytes, self.max_size_bytes)

    def _normalize_and_validate_paths(self) -> None:
        # Root directories: required, must exist
        self.root_dirs = PathValidator.normalize_path_list(
            self.root_dirs_raw,
            require_exists=True,
            require_dir=True,
            field_name="root_dirs"
        )
        if not self.root_dirs:
            raise ValidationError("At least one valid root directory is required", field="root_dirs")

        # Excluded directories: optional, validate if provided
        # require_exists=False allows excluding paths that might be created later
        if self.excluded_dirs_raw:
            self.excluded_dirs = PathValidator.normalize_path_list(
                self.excluded_dirs_raw,
                require_exists=False,
                require_dir=True,
                field_name="excluded_dirs"
            )

        # Favourite directories: optional
        if self.favourite_dirs_raw:
            self.favourite_dirs = PathValidator.normalize_path_list(
                self.favourite_dirs_raw,
                require_exists=True,
                require_dir=True,
                field_name="favourite_dirs"
            )

    def _normalize_extensions(self) -> None:
        self.normalized_extensions, self.extension_filter_mode = \
            ExtensionValidator.normalize_extensions(self.extensions_raw)

    def _validate_root_vs_excluded(self) -> None:
        """
        CRITICAL: Validate relationship between root_dirs and excluded_dirs.

        Logic:
        - excluded_dirs SHOULD typically be subpaths of root_dirs (to skip subfolders).
        - ERROR: If an excluded_dir is EQUAL to a root_dir (useless configuration).
        - ERROR: If an excluded_dir is a PARENT of a root_dir (would exclude the root itself).
        """
        if not self.excluded_dirs:
            return

        errors = []
        for excluded in self.excluded_dirs:
            excluded_path = Path(excluded)
            for root in self.root_dirs:
                root_path = Path(root)

                # Case 1: Exact match (excluding the root itself)
                if excluded_path == root_path:
                    errors.append(
                        f"Excluded directory '{excluded}' is identical to root directory '{root}'. "
                        f"This would prevent any scanning."
                    )

                # Case 2: Excluded is a parent of root (e.g., root=/data/a, excluded=/data)
                # This means the excluded folder contains the root, effectively disabling the root.
                elif PathValidator.is_subpath(root, excluded):
                    errors.append(
                        f"Excluded directory '{excluded}' contains root directory '{root}'. "
                        f"This would prevent scanning of the root."
                    )

        if errors:
            raise ValidationError(
                "Invalid configuration between root and excluded directories:\n" + "\n".join(f"  - {e}" for e in errors),
                field="root_dirs/excluded_dirs"
            )

    def _validate_favourite_vs_excluded(self) -> None:
        """Check that favourite directories are not explicitly excluded."""
        if not self.favourite_dirs or not self.excluded_dirs:
            return

        conflicts = []
        for fav in self.favourite_dirs:
            for exc in self.excluded_dirs:
                # If favourite is inside excluded, it's a logic error
                if PathValidator.is_subpath(fav, exc) or Path(fav) == Path(exc):
                    conflicts.append(f"Favourite '{fav}' is inside excluded directory '{exc}'")

        if conflicts:
            raise ValidationError(
                "Favourite directories conflict with excluded directories:\n" + "\n".join(f"  - {c}" for c in conflicts),
                field="favourite_dirs/excluded_dirs"
            )

    def _validate_favourite_within_roots(self) -> None:
        """Warn if favourite directories are outside root directories."""
        if not self.favourite_dirs:
            return

        for fav in self.favourite_dirs:
            if not any(PathValidator.is_subpath(fav, root) or Path(fav) == Path(root) for root in self.root_dirs):
                logger.warning(
                    f"Favourite directory '{fav}' is outside all root directories. "
                    f"Files in this directory will not be scanned."
                )

    @property
    def validated_params(self) -> dict:
        """Return validated and normalized parameters as a dictionary."""
        return {
            "root_dirs": self.root_dirs,
            "min_size_bytes": self.min_size_bytes,
            "max_size_bytes": self.max_size_bytes,
            "extensions": self.normalized_extensions,
            "extension_filter_mode": self.extension_filter_mode.value,
            "favourite_dirs": self.favourite_dirs,
            "excluded_dirs": self.excluded_dirs,
        }


def validate_deduplication_params(
        root_dirs: List[str],
        min_size_bytes: int,
        max_size_bytes: int,
        extensions: Optional[List[str]] = None,
        favourite_dirs: Optional[List[str]] = None,
        excluded_dirs: Optional[List[str]] = None,
) -> dict:
    """
    One-stop function to validate and normalize deduplication parameters.
    """
    validator = DeduplicationParamsValidator(
        root_dirs=root_dirs,
        min_size_bytes=min_size_bytes,
        max_size_bytes=max_size_bytes,
        extensions=extensions,
        favourite_dirs=favourite_dirs,
        excluded_dirs=excluded_dirs,
    )
    validator.validate_all()
    return validator.validated_params