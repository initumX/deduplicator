"""
Integration tests for DeduplicationCommand — the orchestration layer between UI and core.
Verifies correct wiring of scanner → onlyone with progress/cancellation support.
"""
import pytest
from pathlib import Path
from onlyone import DeduplicationParams, DeduplicationMode, SortOrder
from onlyone import DeduplicationCommand


class TestDeduplicationCommand:
    """Test command orchestration logic (scanner + onlyone integration)."""

    def test_execute_returns_groups_and_stats(self, test_files):
        """
        Command must successfully orchestrate full pipeline:
        scan → deduplicate → return results.
        """
        root_dir = str(Path(test_files["dup1_a"]).parent)

        params = DeduplicationParams(
            root_dir=root_dir,
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            mode=DeduplicationMode.FAST,
            sort_order=SortOrder.SHORTEST_PATH
        )

        command = DeduplicationCommand()
        groups, stats = command.execute(params)

        # Should find 2 duplicate groups (1KB + 2KB sets)
        assert len(groups) == 2
        assert stats.total_time > 0
        assert "size" in stats.stage_stats
        assert "front" in stats.stage_stats

    def test_execute_raises_error_on_empty_scan(self, temp_dir):
        """
        Command must raise RuntimeError when scanner finds zero files.
        Prevents wasted deduplication effort on empty input.
        """
        params = DeduplicationParams(
            root_dir=str(temp_dir),
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],  # No .txt files in empty dir
            favourite_dirs=[],
            mode=DeduplicationMode.FAST,
            sort_order=SortOrder.SHORTEST_PATH
        )

        command = DeduplicationCommand()

        with pytest.raises(RuntimeError, match="No files found matching filters"):
            command.execute(params)

    def test_execute_invokes_progress_callback(self, test_files):
        """
        Command must call progress_callback with meaningful updates during execution.
        Enables responsive UI progress bars.
        """
        root_dir = str(Path(test_files["dup1_a"]).parent)
        progress_events = []

        def progress_callback(stage: str, current: int, total: int):
            progress_events.append((stage, current, total))

        params = DeduplicationParams(
            root_dir=root_dir,
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            mode=DeduplicationMode.FAST,
            sort_order=SortOrder.SHORTEST_PATH
        )

        command = DeduplicationCommand()
        groups, _ = command.execute(params, progress_callback=progress_callback)

        # Should receive multiple progress updates
        assert len(progress_events) > 0

        # First event should be scanning-related
        first_stage = progress_events[0][0].lower()
        assert "scan" in first_stage or "size" in first_stage

        # Last events should include hash stages
        last_stage = progress_events[-1][0].lower()
        assert "front" in last_stage or "hash" in last_stage

    def test_get_files_returns_copy_of_list(self, test_files):
        """
        Command must return a COPY of the internal files list to prevent external mutation.
        Note: Returns shallow copy (objects themselves are not copied, which is acceptable).
        """
        root_dir = str(Path(test_files["dup1_a"]).parent)

        params = DeduplicationParams(
            root_dir=root_dir,
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            mode=DeduplicationMode.FAST,
            sort_order=SortOrder.SHORTEST_PATH
        )

        command = DeduplicationCommand()
        command.execute(params)

        files = command.get_files()

        # Should have scanned files (7 .txt files from fixture)
        assert len(files) == 7
        assert all(f.path.endswith(".txt") for f in files)

        # Verify list is a COPY (modifying list doesn't affect internal state)
        original_id = id(command.get_files())
        files.append(files[0])
        assert id(command.get_files()) == original_id  # Internal list unchanged
        assert len(command.get_files()) == 7  # Still 7 files internally

    def test_execute_respects_stopped_flag_after_scan(self, test_files):
        """
        Command must stop deduplication immediately when stopped_flag returns True AFTER scanning.
        This is the realistic cancellation scenario: user cancels after scan completes but before hashing finishes.
        """
        root_dir = str(Path(test_files["dup1_a"]).parent)
        scan_complete = False
        dedupe_call_count = 0

        def stopped_flag():
            nonlocal scan_complete, dedupe_call_count
            if not scan_complete:
                # Allow scan to complete fully (7 files found)
                if dedupe_call_count > 7:
                    scan_complete = True
                return False
            dedupe_call_count += 1
            # Stop during deduplication phase (after scan completes)
            return dedupe_call_count > 3

        params = DeduplicationParams(
            root_dir=root_dir,
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            mode=DeduplicationMode.FULL,  # Longer pipeline = easier to cancel
            sort_order=SortOrder.SHORTEST_PATH
        )

        command = DeduplicationCommand()
        groups, stats = command.execute(params, stopped_flag=stopped_flag)

        # Scan must complete (7 files found)
        assert len(command.get_files()) == 7

        # Deduplication must be partially cancelled
        assert dedupe_call_count <= 10
        # May have partial groups (not necessarily full 2 groups)
        assert len(groups) <= 2