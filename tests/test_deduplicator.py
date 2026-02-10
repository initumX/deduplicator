"""
Integration tests for full deduplication pipeline.
Verifies end-to-end workflow: scan → pipeline execution → sorted groups.
"""
from pathlib import Path
from core.scanner import FileScannerImpl
from core.deduplicator import DeduplicatorImpl
from core.models import DeduplicationParams, DeduplicationMode, SortOrder


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