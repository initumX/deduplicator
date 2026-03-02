"""
Unit tests for core/validator.py
Tests validation logic in isolation from DeduplicationParams model.
"""
import pytest
from pathlib import Path
from onlyone.core.validator import (
    PathValidator,
    ExtensionValidator,
    SizeValidator,
    DeduplicationParamsValidator,
    FilterMode,
    validate_deduplication_params
)


# =============================================================================
# 1. PATH VALIDATOR TESTS
# =============================================================================
class TestPathValidator:
    """Tests for PathValidator utility class."""

    def test_normalize_single_path(self, temp_dir):
        """Single valid path should be normalized to absolute."""
        result = PathValidator.normalize_path(str(temp_dir))
        assert Path(result).is_absolute()
        assert Path(result) == temp_dir.resolve()

    def test_normalize_nonexistent_path_raises(self, temp_dir):
        """Non-existent path should raise ValueError."""
        fake_path = temp_dir / "does_not_exist"
        with pytest.raises(ValueError, match="does not exist"):
            PathValidator.normalize_path(str(fake_path))

    def test_normalize_file_as_dir_raises(self, temp_dir):
        """File path should raise ValueError when require_dir=True."""
        file_path = temp_dir / "file.txt"
        file_path.write_bytes(b"content")
        with pytest.raises(ValueError, match="not a directory"):
            PathValidator.normalize_path(str(file_path), require_dir=True)

    def test_normalize_path_list_deduplicates(self, temp_dir):
        """Path list should remove duplicates while preserving order."""
        result = PathValidator.normalize_path_list(
            [str(temp_dir), str(temp_dir), str(temp_dir)]
        )
        assert len(result) == 1

    def test_is_subpath_true(self, temp_dir):
        """is_subpath should return True for actual subpaths."""
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        assert PathValidator.is_subpath(str(subdir), str(temp_dir)) is True

    def test_is_subpath_false(self, temp_dir):
        """is_subpath should return False for unrelated paths."""
        unrelated = temp_dir.parent / "unrelated"
        unrelated.mkdir(exist_ok=True)
        assert PathValidator.is_subpath(str(unrelated), str(temp_dir)) is False

    def test_is_subpath_detects_overlap(self, temp_dir):
        """is_subpath should detect when one path is inside another."""
        subdir = temp_dir / "subdir"
        subdir.mkdir()

        # subdir is inside temp_dir
        assert PathValidator.is_subpath(str(subdir), str(temp_dir)) is True

        # temp_dir is NOT inside subdir
        assert PathValidator.is_subpath(str(temp_dir), str(subdir)) is False

        # Same path is NOT a subpath
        assert PathValidator.is_subpath(str(temp_dir), str(temp_dir)) is False


# =============================================================================
# 2. EXTENSION VALIDATOR TESTS
# =============================================================================
class TestExtensionValidator:
    """Tests for ExtensionValidator utility class."""

    def test_normalize_whitelist(self):
        """Whitelist mode should normalize extensions."""
        exts, mode = ExtensionValidator.normalize_extensions(["jpg", "png"])
        assert mode == FilterMode.WHITELIST
        assert exts == [".jpg", ".png"]

    def test_normalize_blacklist_marker(self):
        """Blacklist mode should be triggered by '^' marker."""
        exts, mode = ExtensionValidator.normalize_extensions(["^", "tmp"])
        assert mode == FilterMode.BLACKLIST
        assert exts == [".tmp"]

    def test_normalize_blacklist_prefix(self):
        """Blacklist mode should be triggered by '^' prefix."""
        exts, mode = ExtensionValidator.normalize_extensions(["^tmp", "^log"])
        assert mode == FilterMode.BLACKLIST
        assert exts == [".tmp", ".log"]

    def test_normalize_lowercase(self):
        """Extensions should be lowercased."""
        exts, mode = ExtensionValidator.normalize_extensions(["JPG", "PNG"])
        assert exts == [".jpg", ".png"]

    def test_normalize_adds_dot(self):
        """Dot should be added if missing."""
        exts, mode = ExtensionValidator.normalize_extensions(["txt"])
        assert exts == [".txt"]

    def test_normalize_removes_duplicates(self):
        """Duplicate extensions should be removed."""
        exts, mode = ExtensionValidator.normalize_extensions(["txt", "txt", "txt"])
        assert exts == [".txt"]

    def test_normalize_empty_list(self):
        """Empty list should return whitelist mode."""
        exts, mode = ExtensionValidator.normalize_extensions([])
        assert mode == FilterMode.WHITELIST
        assert exts == []


# =============================================================================
# 3. SIZE VALIDATOR TESTS
# =============================================================================
class TestSizeValidator:
    """Tests for SizeValidator utility class."""

    def test_valid_range(self):
        """Valid size range should not raise."""
        SizeValidator.validate_size_range(100, 1000)  # Should pass

    def test_negative_min_raises(self):
        """Negative min_size should raise ValueError."""
        with pytest.raises(ValueError, match="Minimum size cannot be negative"):
            SizeValidator.validate_size_range(-1, 1000)

    def test_max_less_than_min_raises(self):
        """max_size < min_size should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be less than minimum size"):
            SizeValidator.validate_size_range(1000, 100)

    def test_equal_min_max_allowed(self):
        """Equal min and max should be allowed."""
        SizeValidator.validate_size_range(100, 100)  # Should pass


# =============================================================================
# 4. DEDUPLICATION PARAMS VALIDATOR TESTS
# =============================================================================
class TestDeduplicationParamsValidator:
    """Tests for DeduplicationParamsValidator class."""

    def test_validate_all_success(self, temp_dir):
        """Valid parameters should pass validation."""
        validator = DeduplicationParamsValidator(
            root_dirs=[str(temp_dir)],
            min_size_bytes=0,
            max_size_bytes=1000000,
        )
        validator.validate_all()  # Should not raise
        assert len(validator.root_dirs) == 1

    def test_validate_root_excluded_identical(self, temp_dir):
        """Identical root and excluded dirs should raise."""
        validator = DeduplicationParamsValidator(
            root_dirs=[str(temp_dir)],
            min_size_bytes=0,
            max_size_bytes=1000000,
            excluded_dirs=[str(temp_dir)]
        )
        with pytest.raises(ValueError, match="identical to root"):
            validator.validate_all()

    def test_validate_root_excluded_parent(self, temp_dir):
        """Excluded dir containing root should raise."""
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        validator = DeduplicationParamsValidator(
            root_dirs=[str(subdir)],
            min_size_bytes=0,
            max_size_bytes=1000000,
            excluded_dirs=[str(temp_dir)]
        )
        with pytest.raises(ValueError, match="contains root"):
            validator.validate_all()

    def test_validate_favourite_excluded_conflict(self, temp_dir):
        """Favourite inside excluded should raise."""
        special_dir = temp_dir / "special"
        special_dir.mkdir()
        validator = DeduplicationParamsValidator(
            root_dirs=[str(temp_dir)],
            min_size_bytes=0,
            max_size_bytes=1000000,
            favourite_dirs=[str(special_dir)],
            excluded_dirs=[str(special_dir)]
        )
        with pytest.raises(ValueError, match="conflict with excluded"):
            validator.validate_all()

    def test_validate_favourite_outside_root_warning(self, temp_dir, caplog):
        """Favourite outside root should log warning."""
        import logging

        # Create a separate existing directory outside temp_dir
        outside_dir = temp_dir.parent / "outside_fav"
        outside_dir.mkdir(exist_ok=True)

        try:
            with caplog.at_level(logging.WARNING):
                validator = DeduplicationParamsValidator(
                    root_dirs=[str(temp_dir)],
                    min_size_bytes=0,
                    max_size_bytes=1000000,
                    favourite_dirs=[str(outside_dir)]  # Use existing path
                )
                validator.validate_all()
                assert "outside all root directories" in caplog.text
        finally:
            # Cleanup
            import shutil
            shutil.rmtree(outside_dir, ignore_errors=True)

    def test_validated_params_returns_dict(self, temp_dir):
        """validated_params should return complete dict."""
        validator = DeduplicationParamsValidator(
            root_dirs=[str(temp_dir)],
            min_size_bytes=100,
            max_size_bytes=1000,
            extensions=[".txt"],
        )
        validator.validate_all()
        params = validator.validated_params

        assert "root_dirs" in params
        assert "extensions" in params
        assert "extension_filter_mode" in params
        assert params["min_size_bytes"] == 100


# =============================================================================
# 5. VALIDATE_DEDUPLICATION_PARAMS FUNCTION TESTS
# =============================================================================
class TestValidateDeduplicationParamsFunction:
    """Tests for the convenience factory function."""

    def test_function_success(self, temp_dir):
        """Function should return validated params dict."""
        result = validate_deduplication_params(
            root_dirs=[str(temp_dir)],
            min_size_bytes=0,
            max_size_bytes=1000,
        )
        assert isinstance(result, dict)
        assert len(result["root_dirs"]) == 1

    def test_function_raises_on_error(self, temp_dir):
        """Function should raise ValueError on invalid params."""
        with pytest.raises(ValueError):
            validate_deduplication_params(
                root_dirs=[],  # Invalid
                min_size_bytes=0,
                max_size_bytes=1000,
            )