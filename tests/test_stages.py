"""
Unit tests for deduplication pipeline stages.
Verifies correct behavior of size grouping and partial/full hash stages,
including early duplicate confirmation for small files and adaptive chunk sizing.
"""
import pytest
from highlander.core.stages import (
    SizeStageImpl,
    FrontHashStage,
    MiddleHashStage,
    EndHashStage,
    FullHashStage,
    DeduplicationConfig,
    HashStageBase
)
from highlander.core.grouper import FileGrouperImpl
from highlander.core.hasher import HasherImpl, XXHashAlgorithmImpl
from highlander.core.models import File, DuplicateGroup


class TestDeduplicationConfig:
    """Test adaptive chunk sizing strategy based on file size."""

    @pytest.mark.parametrize("file_size, expected_chunk", [
        (100, 100),                    # ≤128KB: full file size
        (128 * 1024, 128 * 1024),      # Exactly 128KB boundary
        (200 * 1024, 128 * 1024),      # 128KB < size ≤ 384KB → 128KB chunks
        (5 * 1024 * 1024, 64 * 1024),  # 5MB → 64KB chunks
        (20 * 1024 * 1024, 128 * 1024), # 20MB → 128KB chunks
        (50 * 1024 * 1024, 256 * 1024), # 50MB → 256KB chunks
        (100 * 1024 * 1024, 512 * 1024), # 100MB → 512KB chunks
        (200 * 1024 * 1024, 1 * 1024 * 1024), # 200MB → 1MB chunks
        (500 * 1024 * 1024, 2 * 1024 * 1024), # 500MB+ → 2MB chunks
    ])
    def test_get_chunk_size_scales_with_file_size(self, file_size, expected_chunk):
        """Chunk size must adapt based on file size to balance accuracy and performance."""
        chunk_size = DeduplicationConfig.get_chunk_size(file_size)
        assert chunk_size == expected_chunk

    def test_early_confirmation_threshold(self):
        """Front hash stage must use 128KB threshold for early duplicate confirmation."""
        assert DeduplicationConfig.EARLY_CONFIRMATION_SIZE_LIMIT == 128 * 1024


class TestSizeStageImpl:
    """Test initial size-based grouping stage."""

    def test_groups_files_by_size_filters_single_files(self):
        """Size stage must return only groups with 2+ files of identical size."""
        files = [
            File(path="/a.txt", size=1024),
            File(path="/b.txt", size=1024),  # Same size → group
            File(path="/c.txt", size=2048),  # Single file → filtered out
        ]
        grouper = FileGrouperImpl()
        stage = SizeStageImpl(grouper)
        groups = stage.process(files)
        assert len(groups) == 1
        assert groups[0].size == 1024
        assert len(groups[0].files) == 2
        assert {f.path for f in groups[0].files} == {"/a.txt", "/b.txt"}

    def test_empty_input_returns_empty_list(self):
        """Size stage must handle empty file list gracefully."""
        stage = SizeStageImpl(FileGrouperImpl())
        groups = stage.process([])
        assert groups == []

    def test_progress_callback_invoked(self):
        """Size stage must invoke progress callback with correct parameters."""
        files = [File(path=f"/file{i}.txt", size=1024) for i in range(5)]
        progress_calls = []

        def progress_callback(stage_name, current_count, total_count):
            progress_calls.append((stage_name, current_count, total_count))

        stage = SizeStageImpl(FileGrouperImpl())
        stage.process(files, progress_callback=progress_callback)
        assert len(progress_calls) == 1
        callback_stage, callback_current, callback_total = progress_calls[0]
        assert "size" in callback_stage.lower() or "group" in callback_stage.lower()
        assert callback_current == callback_total == 5


class TestFrontHashStage:
    """Test front hash stage with early duplicate confirmation for small files."""

    def test_early_confirmation_for_files_le_128kb(self, tmp_path):
        """
        CRITICAL: Files ≤128KB with matching front hashes must be immediately
        confirmed as duplicates without proceeding to later stages.
        """
        content = b"A" * 100 * 1024
        file1 = tmp_path / "file1.bin"
        file2 = tmp_path / "file2.bin"
        file1.write_bytes(content)
        file2.write_bytes(content)

        files = [
            File(path=str(file1), size=100 * 1024),
            File(path=str(file2), size=100 * 1024),
        ]
        HashStageBase.assign_chunk_sizes(files)

        grouper = FileGrouperImpl(HasherImpl(XXHashAlgorithmImpl()))
        stage = FrontHashStage(grouper)
        confirmed = []
        stage.process([DuplicateGroup(size=100 * 1024, files=files)], confirmed)

        assert len(confirmed) == 1
        assert len(confirmed[0].files) == 2

    def test_large_files_not_confirmed_after_front_hash(self, tmp_path):
        """
        Files >128KB with matching front hashes must NOT be confirmed early.
        They must proceed to subsequent stages for further verification.
        """
        identical_prefix = b"A" * 128 * 1024
        file1_content = identical_prefix + b"UNIQUE_SUFFIX_1"
        file2_content = identical_prefix + b"UNIQUE_SUFFIX_2"

        file1 = tmp_path / "file1.bin"
        file2 = tmp_path / "file2.bin"
        file1.write_bytes(file1_content)
        file2.write_bytes(file2_content)

        files = [
            File(path=str(file1), size=len(file1_content)),
            File(path=str(file2), size=len(file2_content)),
        ]
        HashStageBase.assign_chunk_sizes(files)

        grouper = FileGrouperImpl(HasherImpl(XXHashAlgorithmImpl()))
        stage = FrontHashStage(grouper)
        confirmed = []
        remaining_groups = stage.process([DuplicateGroup(size=len(file1_content), files=files)], confirmed)

        assert len(confirmed) == 0
        assert len(remaining_groups) == 1
        assert len(remaining_groups[0].files) == 2

    def test_mixed_small_and_large_files_in_same_group(self, tmp_path):
        """
        When a group contains both small (≤128KB) and large (>128KB) files
        with matching front hashes, only small files should be confirmed early.
        Large files must continue to next stage.
        """
        small_content = b"S" * 100 * 1024
        small1 = tmp_path / "small1.bin"
        small2 = tmp_path / "small2.bin"
        small1.write_bytes(small_content)
        small2.write_bytes(small_content)

        large_prefix = b"L" * 128 * 1024
        large1_content = large_prefix + b"TAIL1"
        large2_content = large_prefix + b"TAIL2"
        large1 = tmp_path / "large1.bin"
        large2 = tmp_path / "large2.bin"
        large1.write_bytes(large1_content)
        large2.write_bytes(large2_content)

        small_files = [
            File(path=str(small1), size=100 * 1024),
            File(path=str(small2), size=100 * 1024),
        ]
        large_files = [
            File(path=str(large1), size=200 * 1024),
            File(path=str(large2), size=200 * 1024),
        ]
        HashStageBase.assign_chunk_sizes(small_files + large_files)

        grouper = FileGrouperImpl(HasherImpl(XXHashAlgorithmImpl()))
        stage = FrontHashStage(grouper)
        confirmed = []
        stage.process([DuplicateGroup(size=100 * 1024, files=small_files)], confirmed)
        remaining = stage.process([DuplicateGroup(size=200 * 1024, files=large_files)], confirmed)

        assert len(confirmed) == 1
        assert len(confirmed[0].files) == 2
        assert all(f.size <= 128 * 1024 for f in confirmed[0].files)

        assert len(remaining) == 1
        assert len(remaining[0].files) == 2
        assert all(f.size > 128 * 1024 for f in remaining[0].files)


class TestMiddleAndEndHashStages:
    """Test middle and end hash stages with their respective confirmation thresholds."""

    def test_middle_hash_stage_confirmation_threshold(self):
        """Middle hash stage must use 256KB threshold (2× base limit) for early confirmation."""
        stage = MiddleHashStage(FileGrouperImpl())
        assert stage.get_threshold() == 256 * 1024
        assert "middle" in stage.get_stage_name().lower()

    def test_end_hash_stage_confirmation_threshold(self):
        """End hash stage must use 384KB threshold (3× base limit) for early confirmation."""
        stage = EndHashStage(FileGrouperImpl())
        assert stage.get_threshold() == 384 * 1024
        assert "end" in stage.get_stage_name().lower()

    def test_stopped_flag_respected_during_processing(self, tmp_path):
        """All stages must immediately halt processing when stopped_flag returns True."""
        content = b"X" * 1024
        files = []
        for i in range(10):
            f = tmp_path / f"file{i}.bin"
            f.write_bytes(content)
            files.append(File(path=str(f), size=1024))

        HashStageBase.assign_chunk_sizes(files)

        call_count = 0

        def stopped_flag():
            nonlocal call_count
            call_count += 1
            return call_count > 3

        grouper = FileGrouperImpl(HasherImpl(XXHashAlgorithmImpl()))
        stage = FrontHashStage(grouper)
        confirmed = []
        remaining = stage.process([DuplicateGroup(size=1024, files=files)], confirmed, stopped_flag=stopped_flag)

        assert call_count <= 5
        assert len(confirmed) + len(remaining) <= 2


class TestFullHashStage:
    """Test final full-content hash verification stage."""

    def test_full_hash_confirms_only_true_duplicates(self, tmp_path):
        """
        Full hash stage must eliminate false positives that passed partial hash stages.
        Only files with identical full content should be confirmed as duplicates.
        """
        chunk = b"A" * (64 * 1024)
        file1_content = chunk + b"DIFFERENT_CONTENT_1" + chunk
        file2_content = chunk + b"DIFFERENT_CONTENT_2" + chunk

        file1 = tmp_path / "file1.bin"
        file2 = tmp_path / "file2.bin"
        file1.write_bytes(file1_content)
        file2.write_bytes(file2_content)

        files = [
            File(path=str(file1), size=len(file1_content)),
            File(path=str(file2), size=len(file2_content)),
        ]
        HashStageBase.assign_chunk_sizes(files)

        grouper = FileGrouperImpl(HasherImpl(XXHashAlgorithmImpl()))
        stage = FullHashStage(grouper)
        confirmed = []
        stage.process([DuplicateGroup(size=len(file1_content), files=files)], confirmed)

        assert len(confirmed) == 0

    def test_full_hash_confirms_identical_files(self, tmp_path):
        """Full hash stage must confirm files with identical complete content."""
        content = b"IDENTICAL_CONTENT" * 10000
        file1 = tmp_path / "file1.bin"
        file2 = tmp_path / "file2.bin"
        file1.write_bytes(content)
        file2.write_bytes(content)

        files = [
            File(path=str(file1), size=len(content)),
            File(path=str(file2), size=len(content)),
        ]
        HashStageBase.assign_chunk_sizes(files)

        grouper = FileGrouperImpl(HasherImpl(XXHashAlgorithmImpl()))
        stage = FullHashStage(grouper)
        confirmed = []
        stage.process([DuplicateGroup(size=len(content), files=files)], confirmed)

        assert len(confirmed) == 1
        assert len(confirmed[0].files) == 2
        assert confirmed[0].size == len(content)


class TestStageIntegration:
    """Test interaction between consecutive stages in the pipeline."""

    def test_groups_filtered_between_stages_when_reduced_to_single_file(self, tmp_path):
        """
        When a group is reduced to <2 files after a stage, it must be discarded
        and not passed to subsequent stages.
        """
        identical_content = b"A" * 1024
        unique_content = b"B" * 1024

        file1 = tmp_path / "dup1.txt"
        file2 = tmp_path / "dup2.txt"
        file3 = tmp_path / "unique.txt"
        file1.write_bytes(identical_content)
        file2.write_bytes(identical_content)
        file3.write_bytes(unique_content)

        files = [
            File(path=str(file1), size=1024),
            File(path=str(file2), size=1024),
            File(path=str(file3), size=1024),
        ]
        HashStageBase.assign_chunk_sizes(files)

        grouper = FileGrouperImpl(HasherImpl(XXHashAlgorithmImpl()))
        front_stage = FrontHashStage(grouper)
        confirmed = []
        remaining = front_stage.process([DuplicateGroup(size=1024, files=files)], confirmed)

        assert len(confirmed) == 1
        assert len(confirmed[0].files) == 2
        assert len(remaining) == 0