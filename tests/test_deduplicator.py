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
        scanner = FileScannerImpl(
            root_dir=root_dir,
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files
        params = DeduplicationParams(
            root_dir=root_dir,
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
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
        assert len(groups) == 2
        group_1kb = next(g for g in groups if g.size == 1024)
        assert len(group_1kb.files) == 3
        group_2kb = next(g for g in groups if g.size == 2048)
        assert len(group_2kb.files) == 2
        total_files = sum(data["files"] for data in stats.stage_stats.values())
        total_groups = sum(data["groups"] for data in stats.stage_stats.values())
        assert total_files > 0
        assert total_groups >= 2

    def test_normal_mode_processes_all_stages(self, test_files):
        """NORMAL mode should execute size → front → middle → end stages."""
        root_dir = str(Path(test_files["dup1_a"]).parent)
        scanner = FileScannerImpl(
            root_dir=root_dir,
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files
        params = DeduplicationParams(
            root_dir=root_dir,
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
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
        assert len(groups) == 2
        assert "middle" in stats.stage_stats
        assert "end" in stats.stage_stats

    def test_full_mode_executes_full_hash_stage(self, test_files):
        """FULL mode must execute size → front → middle → full_hash stages."""
        root_dir = str(Path(test_files["dup1_a"]).parent)
        scanner = FileScannerImpl(
            root_dir=root_dir,
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files
        params = DeduplicationParams(
            root_dir=root_dir,
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            mode=DeduplicationMode.FULL,
            sort_order=SortOrder.OLDEST_FIRST
        )
        deduper = DeduplicatorImpl()
        groups, stats = deduper.find_duplicates(
            files=files,
            params=params,
            stopped_flag=lambda: False,
            progress_callback=None
        )
        assert len(groups) == 2
        assert "full" in stats.stage_stats
        assert stats.stage_stats["full"]["files"] > 0

    def test_full_mode_filters_false_positives_with_full_hash(self, temp_dir):
        """
        FULL mode must eliminate false positives that pass partial hash stages.
        Create files with identical size + front/middle hashes but different content.
        """
        chunk = b"A" * (64 * 1024)
        file1_content = chunk + b"DIFFERENT_1" + chunk
        file2_content = chunk + b"DIFFERENT_2" + chunk

        file1 = temp_dir / "file1.bin"
        file2 = temp_dir / "file2.bin"
        file1.write_bytes(file1_content)
        file2.write_bytes(file2_content)

        scanner = FileScannerImpl(
            root_dir=str(temp_dir),
            min_size=0,
            max_size=1024 * 1024 * 1024,
            extensions=[".bin"],
            favourite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files

        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1024 * 1024 * 1024,
            extensions=[".bin"],
            favourite_dirs=[],
            mode=DeduplicationMode.FULL,
            sort_order=SortOrder.NEWEST_FIRST
        )
        deduper = DeduplicatorImpl()
        groups, _ = deduper.find_duplicates(
            files=files,
            params=params,
            stopped_flag=lambda: False,
            progress_callback=None
        )
        assert len(groups) == 0

    def test_cancellation_after_front_stage_returns_partial_results(self, test_files):
        """
        Cancellation after front hash stage must return confirmed groups + unprocessed groups.
        """
        call_count = 0
        def stopped_flag():
            nonlocal call_count
            call_count += 1
            return call_count > 15

        root_dir = str(Path(test_files["dup1_a"]).parent)
        scanner = FileScannerImpl(
            root_dir=root_dir,
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files
        params = DeduplicationParams(
            root_dir=root_dir,
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            mode=DeduplicationMode.NORMAL,
            sort_order=SortOrder.OLDEST_FIRST
        )
        deduper = DeduplicatorImpl()
        groups, stats = deduper.find_duplicates(
            files=files,
            params=params,
            stopped_flag=stopped_flag,
            progress_callback=None
        )
        assert call_count <= 25
        assert len(groups) > 0
        assert len(groups) <= 2

    def test_cancellation_returns_sorted_partial_results(self, test_files):
        """Partial results after cancellation must still be sorted by size descending."""
        call_count = 0
        def stopped_flag():
            nonlocal call_count
            call_count += 1
            return call_count > 10

        root_dir = str(Path(test_files["dup1_a"]).parent)
        scanner = FileScannerImpl(
            root_dir=root_dir,
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files
        params = DeduplicationParams(
            root_dir=root_dir,
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            mode=DeduplicationMode.FULL,
            sort_order=SortOrder.OLDEST_FIRST
        )
        deduper = DeduplicatorImpl()
        groups, _ = deduper.find_duplicates(
            files=files,
            params=params,
            stopped_flag=stopped_flag,
            progress_callback=None
        )
        if len(groups) > 1:
            sizes = [g.size for g in groups]
            assert sizes == sorted(sizes, reverse=True)

    def test_groups_sorted_by_size_descending(self, test_files):
        """Final groups should be sorted by size descending."""
        root_dir = str(Path(test_files["dup1_a"]).parent)
        scanner = FileScannerImpl(
            root_dir=root_dir,
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files
        params = DeduplicationParams(
            root_dir=root_dir,
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            mode=DeduplicationMode.FAST,
            sort_order=SortOrder.OLDEST_FIRST
        )
        groups, _ = DeduplicatorImpl().find_duplicates(
            files=files,
            params=params,
            stopped_flag=lambda: False,
            progress_callback=None
        )
        assert groups[0].size == 2048
        assert groups[1].size == 1024

    def test_empty_directory_returns_empty_result(self, temp_dir):
        """Deduplication on empty directory should return zero groups."""
        scanner = FileScannerImpl(
            root_dir=str(temp_dir),
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files
        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
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
        total_files = sum(data["files"] for data in stats.stage_stats.values())
        total_groups = sum(data["groups"] for data in stats.stage_stats.values())
        assert total_files == 0
        assert total_groups == 0

    def test_deduplicator_empty_input(self):
        """Deduplicator must handle empty file list gracefully without crashing."""
        params = DeduplicationParams(
            root_dir="/tmp",
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            mode=DeduplicationMode.FAST,
            sort_order=SortOrder.OLDEST_FIRST
        )
        deduper = DeduplicatorImpl()
        groups, stats = deduper.find_duplicates(
            files=[],
            params=params,
            stopped_flag=lambda: False,
            progress_callback=None
        )
        assert len(groups) == 0
        assert stats.total_time >= 0

    def test_deduplicator_favourite_dirs_sorting(self, temp_dir):
        """Files from favourite directories must appear first within each duplicate group."""
        content = b"identical content"
        file1 = temp_dir / "fav_file.txt"
        file2 = temp_dir / "nonfav_file.txt"
        file1.write_bytes(content)
        file2.write_bytes(content)
        file_obj1 = File(path=str(file1), size=len(content), creation_time=1000.0)
        file_obj2 = File(path=str(file2), size=len(content), creation_time=2000.0)
        file_obj1.is_from_fav_dir = True
        file_obj2.is_from_fav_dir = False
        identical_hash = b"same_hash8"
        file_obj1.hashes = FileHashes(front=identical_hash, full=identical_hash)
        file_obj2.hashes = FileHashes(front=identical_hash, full=identical_hash)
        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[str(temp_dir)],
            mode=DeduplicationMode.FULL,
            sort_order=SortOrder.NEWEST_FIRST
        )
        deduper = DeduplicatorImpl()
        groups, _ = deduper.find_duplicates(
            files=[file_obj1, file_obj2],
            params=params,
            stopped_flag=lambda: False,
            progress_callback=None
        )
        assert len(groups) == 1
        group = groups[0]
        assert len(group.files) == 2
        assert group.files[0].is_from_fav_dir is True
        assert group.files[1].is_from_fav_dir is False
        assert group.files[0].path == str(file1)
        assert group.files[1].path == str(file2)

    def test_single_file_groups_filtered_between_stages(self, temp_dir):
        """
        Groups reduced to 1 file after front hash must not proceed to subsequent stages.
        Verify filtering by checking decreasing file counts between stages.
        """
        identical_content = b"A" * 1024
        unique_content = b"B" * 1024

        file1 = temp_dir / "dup1.txt"
        file2 = temp_dir / "dup2.txt"
        file3 = temp_dir / "unique.txt"
        file1.write_bytes(identical_content)
        file2.write_bytes(identical_content)
        file3.write_bytes(unique_content)

        scanner = FileScannerImpl(
            root_dir=str(temp_dir),
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files
        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
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
        assert len(groups) == 1
        assert len(groups[0].files) == 2
        assert stats.stage_stats["size"]["files"] == 3
        assert stats.stage_stats["front"]["files"] == 2

    def test_stats_collected_for_all_stages_in_full_mode(self, test_files):
        """FULL mode stats must contain entries for all stages including 'full'."""
        root_dir = str(Path(test_files["dup1_a"]).parent)
        scanner = FileScannerImpl(
            root_dir=root_dir,
            min_size=0,
            max_size=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[]
        )
        files = scanner.scan(stopped_flag=lambda: False).files
        params = DeduplicationParams(
            root_dir=root_dir,
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            mode=DeduplicationMode.FULL,
            sort_order=SortOrder.OLDEST_FIRST
        )
        deduper = DeduplicatorImpl()
        _, stats = deduper.find_duplicates(
            files=files,
            params=params,
            stopped_flag=lambda: False,
            progress_callback=None
        )
        required_stages = {"size", "front", "middle", "full"}
        assert required_stages.issubset(set(stats.stage_stats.keys()))
        for stage in required_stages:
            assert stats.stage_stats[stage]["files"] >= 0
            assert stats.stage_stats[stage]["groups"] >= 0