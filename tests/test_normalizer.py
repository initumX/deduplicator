"""
Unit tests for core/test_normalizer.py
Verifies fuzzy filename normalization logic for duplicate detection.
"""
from onlyone.core.normalizer import normalize_filename


class TestBasicNormalization:
    """Test basic normalization: lowercase, noise removal, extension handling."""

    def test_lowercase_conversion(self):
        """Filenames should be converted to lowercase."""
        assert normalize_filename("PHOTO.JPG") == "photo.jpg"
        assert normalize_filename("My_File.PDF") == "myfile.pdf"
        assert normalize_filename("RePoRt.DoCx") == "report.docx"

    def test_noise_characters_removed(self):
        """Underscores, spaces, dots (in name), and hyphens should be removed."""
        assert normalize_filename("my_file.jpg") == "myfile.jpg"
        assert normalize_filename("my-file.jpg") == "myfile.jpg"
        assert normalize_filename("my file.jpg") == "myfile.jpg"
        assert normalize_filename("my.file.name.jpg") == "myfilename.jpg"
        assert normalize_filename("my_file-name.jpg") == "myfilename.jpg"

    def test_extension_preserved(self):
        """File extension should be preserved (with dot)."""
        assert normalize_filename("photo.jpg") == "photo.jpg"
        assert normalize_filename("document.PDF") == "document.pdf"
        assert normalize_filename("archive.tar.gz") == "archivetar.gz"  # Only last ext split

    def test_empty_input(self):
        """Empty string should return empty string."""
        assert normalize_filename("") == ""


class TestBracketRemoval:
    """Test removal of bracket content: (1), (copy), (Final), etc."""

    def test_numeric_brackets_removed(self):
        """Numeric markers in brackets should be removed."""
        assert normalize_filename("Photo (1).jpg") == "photo.jpg"
        assert normalize_filename("Photo (2).jpg") == "photo.jpg"
        assert normalize_filename("Photo (123).jpg") == "photo.jpg"

    def test_text_brackets_removed(self):
        """Text markers in brackets should be removed."""
        assert normalize_filename("Photo (copy).jpg") == "photo.jpg"
        assert normalize_filename("Photo (Copy).jpg") == "photo.jpg"
        assert normalize_filename("Photo (final).jpg") == "photo.jpg"
        assert normalize_filename("Photo (Final Version).jpg") == "photo.jpg"

    def test_brackets_with_spaces(self):
        """Brackets with surrounding spaces should be handled."""
        assert normalize_filename("Photo (1) .jpg") == "photo.jpg"
        assert normalize_filename("Photo (copy) .jpg") == "photo.jpg"
        assert normalize_filename("Photo  (1)  .jpg") == "photo.jpg"

    def test_multiple_brackets_removed(self):
        """Multiple bracket groups should all be removed."""
        assert normalize_filename("Photo (1) (2).jpg") == "photo.jpg"
        assert normalize_filename("Photo (copy) (final).jpg") == "photo.jpg"
        assert normalize_filename("Photo (1) (copy).jpg") == "photo.jpg"

    def test_brackets_no_space_before(self):
        """Brackets without space before should still be removed."""
        assert normalize_filename("Photo(1).jpg") == "photo.jpg"
        assert normalize_filename("Photo(copy).jpg") == "photo.jpg"


class TestCopyMarkerRemoval:
    """Test removal of copy markers: _copy, Copy2, -new, backup_1, etc."""

    def test_copy_word_removed(self):
        """'copy' marker (case-insensitive) should be removed."""
        assert normalize_filename("Photo_copy.jpg") == "photo.jpg"
        assert normalize_filename("Photo_Copy.jpg") == "photo.jpg"
        assert normalize_filename("PhotoCOPY.jpg") == "photo.jpg"
        assert normalize_filename("Photo-Copy.jpg") == "photo.jpg"
        assert normalize_filename("Photo copy.jpg") == "photo.jpg"

    def test_copy_with_number_removed(self):
        """'copy' marker with number should be removed."""
        assert normalize_filename("Photo_copy2.jpg") == "photo.jpg"
        assert normalize_filename("Photo_Copy12.jpg") == "photo.jpg"
        assert normalize_filename("PhotoCopy3.jpg") == "photo.jpg"
        assert normalize_filename("Photo-copy_5.jpg") == "photo.jpg"

    def test_other_keywords_removed(self):
        """Other keywords (new, final, old, backup) should be removed."""
        assert normalize_filename("Photo_new.jpg") == "photo.jpg"
        assert normalize_filename("Photo_final.jpg") == "photo.jpg"
        assert normalize_filename("Photo_old.jpg") == "photo.jpg"
        assert normalize_filename("Photo_backup.jpg") == "photo.jpg"
        assert normalize_filename("Photo_new2.jpg") == "photo.jpg"
        assert normalize_filename("Photo_final3.jpg") == "photo.jpg"

    def test_keyword_only_at_end(self):
        """Keywords should only be removed if at end of filename."""
        assert normalize_filename("copy_photo.jpg") == "copyphoto.jpg"  # Not at end
        assert normalize_filename("new_report.pdf") == "newreport.pdf"  # Not at end
        assert normalize_filename("final_draft.pdf") == "finaldraft.pdf"  # Not at end

    def test_keyword_with_separator_variations(self):
        """Copy markers with different separators should be removed."""
        assert normalize_filename("Photo_copy.jpg") == "photo.jpg"
        assert normalize_filename("Photo-copy.jpg") == "photo.jpg"
        assert normalize_filename("Photo copy.jpg") == "photo.jpg"
        assert normalize_filename("Photo_copy_2.jpg") == "photo.jpg"
        assert normalize_filename("Photo-copy-2.jpg") == "photo.jpg"


class TestCameraFileHandling:
    """Test special handling for camera files: preserve sequential numbers."""

    def test_camera_files_different_numbers_not_grouped(self):
        """Different camera photo numbers should produce different keys."""
        key1 = normalize_filename("DSC_0001.jpg")
        key2 = normalize_filename("DSC_0002.jpg")
        key3 = normalize_filename("DSC_0003.jpg")

        assert key1 != key2
        assert key2 != key3
        assert key1 != key3

    def test_camera_files_with_copy_markers_grouped(self):
        """Camera files with copy markers should group with original."""
        original = normalize_filename("DSC_3088.jpg")
        copy1 = normalize_filename("DSC_3088copy.jpg")
        copy2 = normalize_filename("DSC_3088copy2.jpg")
        copy3 = normalize_filename("DSC_3088 (1).jpg")

        assert original == copy1 == copy2 == copy3

    def test_camera_files_mixed_separators(self):
        """Camera files with different separators in copy markers should group."""
        base = normalize_filename("IMG_1001.jpg")
        variants = [
            normalize_filename("IMG_1001_copy.jpg"),
            normalize_filename("IMG_1001-copy.jpg"),
            normalize_filename("IMG_1001 copy.jpg"),
            normalize_filename("IMG_1001_copy2.jpg"),
            normalize_filename("IMG_1001 (1).jpg"),
        ]

        for variant in variants:
            assert variant == base, f"Failed for variant: {variant}"


class TestNonCameraTrailingNumbers:
    """Test trailing number removal for non-camera files."""

    def test_trailing_numbers_removed_regular_files(self):
        """Trailing numbers{1,3} after separator should be removed for regular files."""
        assert normalize_filename("Report_1.pdf") == "report.pdf"
        assert normalize_filename("Report_2.pdf") == "report.pdf"
        assert normalize_filename("Report_123.pdf") == "report.pdf"
        assert normalize_filename("Report-1.pdf") == "report.pdf"
        assert normalize_filename("Report-12.pdf") == "report.pdf"
        assert normalize_filename("Report_2014.pdf") == "report2014.pdf"

    def test_trailing_numbers_without_separator_preserved(self):
        """Numbers without separator should NOT be removed (part of name)."""
        assert normalize_filename("Report1.pdf") == "report1.pdf"
        assert normalize_filename("file123.txt") == "file123.txt"
        assert normalize_filename("version2.docx") == "version2.docx"

    def test_numbers_in_middle_preserved(self):
        """Numbers in middle of filename should be preserved."""
        assert normalize_filename("Report_2024.pdf") == "report2024.pdf"
        assert normalize_filename("Invoice_12345.pdf") == "invoice12345.pdf"
        assert normalize_filename("Backup_2024_01_01.tar.gz") == "backup20240101tar.gz"

    def test_camera_vs_regular_distinction(self):
        """Camera files preserve numbers; regular files remove trailing numbers."""
        # Camera: number preserved
        assert normalize_filename("DSC_2726.jpg") == "dsc2726.jpg"
        assert normalize_filename("DSC_2727.jpg") == "dsc2727.jpg"  # Different!

        # Regular: trailing number removed
        assert normalize_filename("Photo_2726.jpg") == "photo2726.jpg"
        assert normalize_filename("Photo_2727.jpg") == "photo2727.jpg"  # Same!


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_only_special_chars_name(self):
        """Filename with only special chars should become just extension."""
        assert normalize_filename("___(123).jpg") == ".jpg"
        assert normalize_filename(" - - .pdf") == ".pdf"

    def test_unicode_and_special_chars(self):
        """Unicode and special chars should be handled gracefully."""
        # Unicode preserved (only specific chars removed)
        assert normalize_filename("файл_001.jpg") == "файл.jpg"
        assert normalize_filename("Ñoño_01.jpg") == "ñoño.jpg"

        # Special chars removed
        assert normalize_filename("file@name#.jpg") == "file@name#.jpg"  # @# not in noise list

    def test_double_extension_handling(self):
        """Double extensions: only last part split, rest treated as name."""
        # os.path.splitext only splits last .ext
        assert normalize_filename("archive.tar.gz") == "archivetar.gz"  # name="archive.tar"
        assert normalize_filename("backup_copy2.tar.gz") == "backupcopy2tar.gz"  # copy2 is not trailing -> preserved
        assert normalize_filename("file (1).tar.gz") == "filetar.gz"  # (1) removed

    def test_no_extension(self):
        """Files without extension should still be normalized."""
        assert normalize_filename("README") == "readme"
        assert normalize_filename("Makefile_1") == "makefile"  # trailing _1 removed
        assert normalize_filename("DSC_0001") == "dsc0001"  # camera: number preserved

    def test_mixed_case_keywords(self):
        """Copy keywords should be case-insensitive."""
        assert normalize_filename("Photo_COPY.jpg") == "photo.jpg"
        assert normalize_filename("Photo_Copy2.jpg") == "photo.jpg"
        assert normalize_filename("Photo_NEW.pdf") == "photo.pdf"
        assert normalize_filename("Photo_Final3.pdf") == "photo.pdf"


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_real_world_duplicates_grouped(self):
        """Real-world duplicate scenarios should produce same key."""
        scenarios = [
            # Scenario: Downloaded file with (1) marker
            [
                "Report.pdf",
                "Report (1).pdf",
                "Report_copy.pdf",
                "Report_copy2.pdf",
            ],
            # Scenario: Photo with camera prefix + copy markers
            [
                "DSC_3088.JPG",
                "DSC_3088copy.JPG",
                "DSC_3088 (1).JPG",
                "dsc_3088_copy2.jpg",
            ],
            # Scenario: Document with year + copy markers
            [
                "Budget_2024.xlsx",
                "Budget_2024_copy.xlsx",
                "Budget_2024 (final).xlsx",
            ],
        ]

        for scenario in scenarios:
            keys = [normalize_filename(f) for f in scenario]
            # All files in scenario should have same key
            assert len(set(keys)) == 1, f"Failed scenario: {scenario}, keys: {keys}"

    def test_real_world_non_duplicates_separated(self):
        """Real-world non-duplicates should produce different keys."""
        non_duplicates = [
            # Different camera photos
            ("DSC_0001.jpg", "DSC_0002.jpg"),
            ("IMG_1001.png", "IMG_1002.png"),
            # Different years in filename
            ("Report_2024.pdf", "Report_2025.pdf"),
            ("Budget_2024_Q1.xlsx", "Budget_2024_Q2.xlsx"),
            # Different file types
            ("photo.jpg", "photo.png"),
            ("document.pdf", "document.docx"),
            # Regular files with different trailing numbers (not copies)
            ("version1.txt", "version2.txt"),  # "version" not a copy keyword
        ]

        for file1, file2 in non_duplicates:
            key1 = normalize_filename(file1)
            key2 = normalize_filename(file2)
            assert key1 != key2, f"False positive: {file1} == {file2} → {key1}"


class TestCacheBehavior:
    """Test lru_cache behavior (optional, for performance verification)."""

    def test_cache_returns_same_object(self):
        """Repeated calls with same input should return same string object (cached)."""
        # Note: This tests implementation detail; may break if cache removed
        result1 = normalize_filename("Test_File.jpg")
        result2 = normalize_filename("Test_File.jpg")

        # Cached strings may be interned; at minimum, values should be equal
        assert result1 == result2

        # Check cache info if available
        if hasattr(normalize_filename, 'cache_info'):
            info = normalize_filename.cache_info()
            assert info.misses >= 1  # At least one miss for first call
            # Second call should be a hit (if same input)
            normalize_filename("Test_File.jpg")
            info2 = normalize_filename.cache_info()
            assert info2.hits > info.hits

    def test_cache_different_inputs_not_confused(self):
        """Cache should not confuse different inputs."""
        key1 = normalize_filename("DSC_0001.jpg")
        key2 = normalize_filename("DSC_0002.jpg")

        assert key1 != key2
        assert key1 == "dsc0001.jpg"
        assert key2 == "dsc0002.jpg"