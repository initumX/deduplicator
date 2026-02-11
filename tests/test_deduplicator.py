"""
Integration tests for full deduplication pipeline.
Verifies end-to-end workflow: scan → pipeline execution → sorted groups.
"""
from pathlib import Path
from deduplicator.core import FileScannerImpl, DeduplicatorImpl
from deduplicator.core import DeduplicationParams, DeduplicationMode, SortOrder, File, FileHashes


class TestDeduplicatorIntegration:
    """Test full deduplication pipeline with real file operations."""

    def test_fast_mode_finds_duplicates(self, test_files):
        """FAST mode should detect duplicates using size → front hash."""
        root_dir = str(Path(test_files["dup1_a"]).parent)

        # Step 1: Scan files
        scanner = FileScannerImpl(
            root_dir=root_dir,
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favorite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files

        # Step 2: Run deduplication in FAST mode
        params = DeduplicationParams(
            root_dir=root_dir,
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favorite_dirs=[],
            mode=DeduplicationMode.FAST,
            sort_order=SortOrder.OLDEST_FIRST
        )

        deduper = DeduplicatorImpl()
        groups, stats = deduper.find_duplicates(
            files=files,
            params=params,
            stopped_flag=lambda: False,
            progress_callback=None
        )

        # Should find 2 groups: dup1 pair (1KB) + dup2 pair (2KB)
        assert len(groups) == 2

        # Group 1: 1KB duplicates (dup1_a, dup1_b, sub_dup)
        group_1kb = next(g for g in groups if g.size == 1024)
        assert len(group_1kb.files) == 3

        # Group 2: 2KB duplicates (dup2_a, dup2_b)
        group_2kb = next(g for g in groups if g.size == 2048)
        assert len(group_2kb.files) == 2

        # Verify stats collected (compute totals from stage_stats)
        total_files = sum(data["files"] for data in stats.stage_stats.values())
        total_groups = sum(data["groups"] for data in stats.stage_stats.values())
        assert total_files > 0
        assert total_groups >= 2  # May include intermediate groups

    def test_normal_mode_processes_all_stages(self, test_files):
        """NORMAL mode should execute size → front → middle → end stages."""
        root_dir = str(Path(test_files["dup1_a"]).parent)

        scanner = FileScannerImpl(
            root_dir=root_dir,
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favorite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files

        params = DeduplicationParams(
            root_dir=root_dir,
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favorite_dirs=[],
            mode=DeduplicationMode.NORMAL,
            sort_order=SortOrder.OLDEST_FIRST
        )

        deduper = DeduplicatorImpl()
        groups, stats = deduper.find_duplicates(
            files=files,
            params=params,
            stopped_flag=lambda: False,
            progress_callback=None
        )

        # Should find same 2 groups as FAST mode
        assert len(groups) == 2
        assert "middle" in stats.stage_stats
        assert "end" in stats.stage_stats

    def test_cancellation_stops_pipeline_immediately(self, test_files):
        """
        Setting stopped_flag=True should halt deduplication immediately.
        """
        call_count = 0

        def stopped_flag():
            nonlocal call_count
            call_count += 1
            return call_count > 5  # Cancel after 5 checks

        root_dir = str(Path(test_files["dup1_a"]).parent)

        scanner = FileScannerImpl(
            root_dir=root_dir,
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favorite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files

        params = DeduplicationParams(
            root_dir=root_dir,
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favorite_dirs=[],
            mode=DeduplicationMode.FULL,
            sort_order=SortOrder.OLDEST_FIRST
        )

        deduper = DeduplicatorImpl()
        groups, stats = deduper.find_duplicates(
            files=files,
            params=params,
            stopped_flag=stopped_flag,
            progress_callback=None
        )

        # Pipeline should have been cancelled early — partial results only
        assert call_count <= 10  # Should not process all files
        assert len(groups) <= 2  # May have partial groups

    def test_groups_sorted_by_size_descending(self, test_files):
        """Final groups should be sorted by size descending."""
        root_dir = str(Path(test_files["dup1_a"]).parent)

        scanner = FileScannerImpl(
            root_dir=root_dir,
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favorite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files

        params = DeduplicationParams(
            root_dir=root_dir,
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favorite_dirs=[],
            mode=DeduplicationMode.FAST,
            sort_order=SortOrder.OLDEST_FIRST
        )

        groups, _ = DeduplicatorImpl().find_duplicates(
            files=files,
            params=params,
            stopped_flag=lambda: False,
            progress_callback=None
        )

        # Groups should be sorted: largest first (2048B group before 1024B group)
        assert groups[0].size == 2048
        assert groups[1].size == 1024

    def test_empty_directory_returns_empty_result(self, temp_dir):
        """Deduplication on empty directory should return zero groups."""
        scanner = FileScannerImpl(
            root_dir=str(temp_dir),
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favorite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files

        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favorite_dirs=[],
            mode=DeduplicationMode.FAST,
            sort_order=SortOrder.OLDEST_FIRST
        )

        groups, stats = DeduplicatorImpl().find_duplicates(
            files=files,
            params=params,
            stopped_flag=lambda: False,
            progress_callback=None
        )

        assert len(groups) == 0
        # Verify stats show zero processing
        total_files = sum(data["files"] for data in stats.stage_stats.values())
        total_groups = sum(data["groups"] for data in stats.stage_stats.values())
        assert total_files == 0
        assert total_groups == 0

    def test_deduplicator_empty_input(self):
        """
        Deduplicator must handle empty file list gracefully without crashing.
        This scenario occurs when filters exclude all files or directory is empty.
        """
        params = DeduplicationParams(
            root_dir="/tmp",
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favorite_dirs=[],
            mode=DeduplicationMode.FAST,
            sort_order=SortOrder.OLDEST_FIRST
        )

        deduper = DeduplicatorImpl()
        groups, stats = deduper.find_duplicates(
            files=[],  # Empty input list
            params=params,
            stopped_flag=lambda: False,
            progress_callback=None
        )

        # Must not crash and return empty results
        assert len(groups) == 0
        assert stats.total_time >= 0  # Time should be non-negative

    def test_deduplicator_favorite_dirs_sorting(self, temp_dir):
        """
        Files from favorite directories must appear first within each duplicate group.
        This ensures users' preferred versions are kept when deleting duplicates.
        """
        # Create identical files (same size, same hash)
        content = b"identical content"
        file1 = temp_dir / "fav_file.txt"
        file2 = temp_dir / "nonfav_file.txt"
        file1.write_bytes(content)
        file2.write_bytes(content)

        # Create File objects with identical hashes
        file_obj1 = File(path=str(file1), size=len(content), creation_time=1000.0)
        file_obj2 = File(path=str(file2), size=len(content), creation_time=2000.0)
        file_obj1.is_from_fav_dir = True   # Mark as favorite
        file_obj2.is_from_fav_dir = False  # Not favorite

        # Set identical hashes to force grouping
        identical_hash = b"same_hash8"
        file_obj1.hashes = FileHashes(front=identical_hash, full=identical_hash)
        file_obj2.hashes = FileHashes(front=identical_hash, full=identical_hash)

        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favorite_dirs=[str(temp_dir)],  # temp_dir is favorite
            mode=DeduplicationMode.FULL,
            sort_order=SortOrder.NEWEST_FIRST  # Newer files first (file2 is newer)
        )

        deduper = DeduplicatorImpl()
        groups, _ = deduper.find_duplicates(
            files=[file_obj1, file_obj2],
            params=params,
            stopped_flag=lambda: False,
            progress_callback=None
        )

        # Should have exactly 1 group with 2 files
        assert len(groups) == 1
        group = groups[0]
        assert len(group.files) == 2

        # CRITICAL: Favorite file must be FIRST regardless of creation time
        # Business rule: favorite status > creation time
        assert group.files[0].is_from_fav_dir is True
        assert group.files[1].is_from_fav_dir is False
        assert group.files[0].path == str(file1)  # Favorite file first
        assert group.files[1].path == str(file2)  # Non-favorite second

        # Verify secondary sort (creation time) works for files with same favorite status
        # Create 3 files: 2 favorites (different times) + 1 non-favorite
        file3 = temp_dir / "fav_old.txt"
        file3.write_bytes(content)
        file_obj3 = File(path=str(file3), size=len(content), creation_time=500.0)
        file_obj3.is_from_fav_dir = True
        file_obj3.hashes = FileHashes(front=identical_hash, full=identical_hash)

        params_oldest = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favorite_dirs=[str(temp_dir)],
            mode=DeduplicationMode.FULL,
            sort_order=SortOrder.OLDEST_FIRST  # Oldest first within favorites
        )

        groups2, _ = deduper.find_duplicates(
            files=[file_obj1, file_obj2, file_obj3],
            params=params_oldest,
            stopped_flag=lambda: False,
            progress_callback=None
        )

        group2 = groups2[0]
        # Favorites first (file_obj3 and file_obj1), then non-favorite (file_obj2)
        assert group2.files[0].is_from_fav_dir is True
        assert group2.files[1].is_from_fav_dir is True
        assert group2.files[2].is_from_fav_dir is False

        # Within favorites: oldest first (file_obj3 created at 500.0 < file_obj1 at 1000.0)
        assert group2.files[0].creation_time == 500.0  # Oldest favorite
        assert group2.files[1].creation_time == 1000.0  # Newer favorite