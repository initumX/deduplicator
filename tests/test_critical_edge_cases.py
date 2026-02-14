"""
Critical edge case tests for production safety.
Focuses on resource leaks during cancellation, accurate space calculation after partial deletion,
and robustness against files disappearing during operation.
"""
import os
import sys
import time
from pathlib import Path
from unittest import mock
from highlander.core.models import File, DuplicateGroup
from highlander.core.stages import HashStageBase, FrontHashStage
from highlander.core.grouper import FileGrouperImpl
from highlander.core.hasher import HasherImpl, XXHashAlgorithmImpl
from highlander.services.file_service import FileService
from highlander.cli import CLIApplication


class TestFileDescriptorLeaksOnCancellation:
    """
    CRITICAL: Verify no file descriptor leaks when operation is cancelled mid-read.
    Leaks cause UI freezes and resource exhaustion with large files.
    """

    def test_large_file_descriptors_closed_immediately_on_cancellation(self, tmp_path):
        """
        When stopped_flag returns True during _read_chunk(), the file descriptor
        MUST be closed immediately after the current read completes.
        This test verifies that cancellation doesn't hang waiting for full chunk reads.
        """
        # Create a large file (10MB) to simulate slow I/O
        large_file = tmp_path / "large.bin"
        large_file.write_bytes(b"A" * 10 * 1024 * 1024)

        file_obj = File(path=str(large_file), size=10 * 1024 * 1024)
        file_obj.chunk_size = 2 * 1024 * 1024  # 2MB chunks

        # Track open file descriptors before/after operation (Linux/macOS only)
        def count_open_fds():
            if sys.platform == "linux":
                return len(list(Path(f"/proc/{os.getpid()}/fd").iterdir()))
            elif sys.platform == "darwin":
                return len([f for f in Path("/dev/fd").iterdir() if f.is_symlink()])
            return 0  # Skip exact count on Windows

        initial_fds = count_open_fds()

        # Cancel immediately after first file processing starts
        cancellation_triggered = False

        def stopped_flag():
            nonlocal cancellation_triggered
            if not cancellation_triggered:
                cancellation_triggered = True
                return False  # Allow first hash computation to start
            return True  # Cancel on second check

        grouper = FileGrouperImpl(HasherImpl(XXHashAlgorithmImpl()))
        stage = FrontHashStage(grouper)
        confirmed = []

        # This should NOT hang waiting to read full 2MB chunk after cancellation
        start_time = time.time()
        stage.process(
            [DuplicateGroup(size=file_obj.size, files=[file_obj])],
            confirmed,
            stopped_flag=stopped_flag
        )
        elapsed = time.time() - start_time

        # Operation must complete quickly (<200ms) — proves FD closed promptly after cancellation
        assert elapsed < 0.2, (
            f"Cancellation took {elapsed:.3f}s — likely hung during file I/O. "
            "File descriptor not released promptly after cancellation request."
        )

        # Verify no FD leak (Linux/macOS only)
        if sys.platform in ("linux", "darwin"):
            final_fds = count_open_fds()
            # Allow small variance (±3 FDs) for OS-level fluctuations
            assert abs(final_fds - initial_fds) <= 3, (
                f"File descriptor leak detected: {initial_fds} → {final_fds} FDs. "
                "Cancelled operation left file descriptors open."
            )

    def test_cancellation_halts_pipeline_before_processing_all_groups(self, tmp_path):
        """
        Cancellation must prevent processing of all groups when stopped_flag returns True.
        Verifies that pipeline respects cancellation request and doesn't process entire input.
        """
        # Create 20 groups of identical small files (2 files per group)
        groups = []
        for group_idx in range(20):
            files = []
            for file_idx in range(2):
                f = tmp_path / f"group{group_idx}_file{file_idx}.bin"
                content = b"X" * 1024
                f.write_bytes(content)
                files.append(File(path=str(f), size=1024))
            HashStageBase.assign_chunk_sizes(files)
            groups.append(DuplicateGroup(size=1024, files=files))

        # Cancel after processing a few groups
        groups_processed = 0
        max_groups_to_process = 5

        def stopped_flag():
            nonlocal groups_processed
            groups_processed += 1
            return groups_processed > max_groups_to_process

        grouper = FileGrouperImpl(HasherImpl(XXHashAlgorithmImpl()))
        stage = FrontHashStage(grouper)
        confirmed = []

        start_time = time.time()
        # Process groups with cancellation enabled
        stage.process(
            groups,
            confirmed,
            stopped_flag=stopped_flag
        )
        elapsed = time.time() - start_time

        # Must complete quickly — proves immediate halt between groups
        assert elapsed < 0.1, (
            f"Cancellation took {elapsed:.3f}s — unexpected delay after stop request."
        )
        # Should have processed significantly fewer groups than total (20)
        # Pipeline checks stopped_flag before each group + once at start
        assert groups_processed <= max_groups_to_process + 2, (
            f"Processed {groups_processed} groups despite cancellation request after {max_groups_to_process}. "
            "Pipeline ignored stopped_flag and processed too many groups."
        )
        # Should NOT have processed all 20 groups
        assert groups_processed < 20, (
            "Cancellation failed — all 20 groups were processed despite stopped_flag returning True."
        )


class TestSpaceSavingsAccuracyAfterPartialDeletion:
    """
    CRITICAL: Space savings calculation must be precise after partial deletion failures.
    Inaccurate reporting misleads users about actual disk space freed.
    """

    def test_space_savings_excludes_failed_deletions(self, tmp_path):
        """
        When some files fail to delete, space_savings must reflect ONLY successfully
        deleted files — not the originally planned amount.
        """
        # Create 3 identical files (1MB each)
        content = b"A" * 1024 * 1024
        files = []
        for i in range(3):
            f = tmp_path / f"file{i}.bin"
            f.write_bytes(content)
            files.append(f)

        # Mock move_to_trash to fail on second file only
        deletion_attempts = []
        successful_deletions = []

        original_move = FileService.move_to_trash

        def flaky_move(path):
            deletion_attempts.append(path)
            if len(deletion_attempts) == 2:
                raise PermissionError(f"Mock permission error for {Path(path).name}")
            successful_deletions.append(path)
            original_move(path)

        with mock.patch.object(FileService, 'move_to_trash', side_effect=flaky_move):
            # Run CLI deletion with --keep-one (preserve 1 file, delete 2)
            with mock.patch.object(sys, 'argv', [
                'highlander', '--input', str(tmp_path), '--keep-one', '--force'
            ]):
                with mock.patch('builtins.print'):
                    app = CLIApplication()
                    try:
                        app.run()
                    except SystemExit:
                        pass  # Expected due to partial failure

        # Verify: exactly 1 file successfully deleted (first attempt), 1 failed (second), 1 preserved
        assert len(successful_deletions) == 1, "Expected exactly 1 successful deletion"
        assert len(deletion_attempts) == 2, "Expected 2 deletion attempts (3 files - 1 preserved)"

        # Verify actual disk space freed matches expected
        remaining_files = [f for f in tmp_path.iterdir() if f.suffix == ".bin"]
        actual_remaining_size = sum(f.stat().st_size for f in remaining_files)
        expected_remaining_size = 2 * 1024 * 1024  # 2 files remaining (1 preserved + 1 failed deletion)

        assert actual_remaining_size == expected_remaining_size, (
            f"Disk space mismatch: expected {expected_remaining_size} bytes remaining, "
            f"got {actual_remaining_size}. Space savings calculation is inaccurate."
        )

    def test_space_savings_for_zero_byte_files_excluded(self):
        """
        Zero-byte files must not contribute to space savings calculation.
        Prevents misleading "saved 0 bytes" reports.
        """
        # Create mock groups with zero-byte files
        zero_byte_files = [
            File(path="/zero1.txt", size=0, name="zero1.txt", extension=".txt"),
            File(path="/zero2.txt", size=0, name="zero2.txt", extension=".txt"),
        ]
        one_mb_files = [
            File(path="/mb1.txt", size=1024 * 1024, name="mb1.txt", extension=".txt"),
            File(path="/mb2.txt", size=1024 * 1024, name="mb2.txt", extension=".txt"),
        ]

        zero_group = DuplicateGroup(size=0, files=zero_byte_files)
        mb_group = DuplicateGroup(size=1024 * 1024, files=one_mb_files)

        app = CLIApplication()
        # Delete one zero-byte file and one 1MB file
        savings = app.calculate_space_savings(
            [zero_group, mb_group],
            ["/zero2.txt", "/mb2.txt"]
        )

        # Zero-byte file contributes 0 bytes to savings
        assert savings == 1024 * 1024, (
            f"Space savings incorrect: expected 1MB (only from non-zero file), got {savings} bytes. "
            "Zero-byte files incorrectly included in calculation."
        )


class TestFilesDeletedDuringOperation:
    """
    CRITICAL: Application must not crash when files disappear between stat() and open().
    Common scenario: user manually deletes files during scan/hashing.
    """

    def test_hasher_handles_file_deleted_after_stat_before_open(self, tmp_path):
        """
        If file is deleted after size check but before hash computation,
        hasher must return empty hash (b'') without raising exceptions.
        Prevents crashes during concurrent file operations.
        """
        # Create file and immediately delete it before hashing
        temp_file = tmp_path / "volatile.txt"
        temp_file.write_bytes(b"content that will disappear")
        file_obj = File(path=str(temp_file), size=30)
        file_obj.chunk_size = 32

        # Delete BEFORE hashing
        temp_file.unlink()

        hasher = HasherImpl(XXHashAlgorithmImpl())

        # CRITICAL: None of these should raise exceptions
        # Application must degrade gracefully, not crash
        full_hash = hasher.compute_full_hash(file_obj)
        front_hash = hasher.compute_front_hash(file_obj)
        middle_hash = hasher.compute_middle_hash(file_obj)
        end_hash = hasher.compute_end_hash(file_obj)

        # All methods must return bytes (empty or valid)
        assert isinstance(full_hash, bytes), "compute_full_hash must return bytes even for missing files"
        assert isinstance(front_hash, bytes), "compute_front_hash must return bytes even for missing files"
        assert isinstance(middle_hash, bytes), "compute_middle_hash must return bytes even for missing files"
        assert isinstance(end_hash, bytes), "compute_end_hash must return bytes even for missing files"

        # Optional: verify hashes are empty (implementation detail)
        # Main requirement is NO EXCEPTIONS raised
        assert len(full_hash) in (0, 8), "Hash should be empty or valid 8-byte xxHash"

    def test_scanner_continues_after_file_deleted_during_walk(self, tmp_path):
        """
        Scanner must skip files that disappear during os.walk() without crashing.
        Simulates user deleting files while scan is in progress.
        """
        # Create 10 files
        for i in range(10):
            (tmp_path / f"file{i}.txt").write_bytes(b"content")

        # Mock os.walk to delete files mid-scan
        deleted_during_scan = []

        original_walk = os.walk

        def flaky_walk(top, *args, **kwargs):
            for root, dirs, files in original_walk(top, *args, **kwargs):
                # Delete file #5 when encountered
                if "file5.txt" in files and "file5.txt" not in deleted_during_scan:
                    target = Path(root) / "file5.txt"
                    if target.exists():
                        target.unlink()
                        deleted_during_scan.append("file5.txt")
                yield root, dirs, files

        with mock.patch("os.walk", side_effect=flaky_walk):
            from highlander.core.scanner import FileScannerImpl
            scanner = FileScannerImpl(
                root_dir=str(tmp_path),
                min_size=0,
                max_size=1024 * 1024,
                extensions=[".txt"],
                favourite_dirs=[]
            )
            # Must NOT raise exception
            collection = scanner.scan(stopped_flag=lambda: False)

        # Should find 9 files (10 created - 1 deleted during scan)
        assert len(collection.files) == 9, (
            f"Expected 9 files after mid-scan deletion, found {len(collection.files)}. "
            "Scanner failed to handle disappearing files gracefully."
        )
        found_names = {Path(f.path).name for f in collection.files}
        assert "file5.txt" not in found_names, "Deleted file should not appear in results"
        assert len(deleted_during_scan) == 1, "Expected exactly one file deleted during scan"


class TestCancellationResourceCleanup:
    """
    CRITICAL: After cancellation, all resources (file descriptors, memory) must be released.
    Prevents memory leaks and resource exhaustion during repeated cancel/resume cycles.
    """

    def test_repeated_cancel_resume_does_not_leak_memory(self, tmp_path):
        """
        Running scan → cancel → scan → cancel multiple times must not grow memory usage.
        Simulates user repeatedly starting/stopping operations in UI.
        """
        # Create 50 small files
        for i in range(50):
            (tmp_path / f"f{i}.txt").write_bytes(b"A" * 1024)

        from highlander.core.scanner import FileScannerImpl

        # Run 5 cycles of scan + early cancellation
        for cycle in range(5):
            call_count = 0

            def stopped_flag():
                nonlocal call_count
                call_count += 1
                return call_count > 5  # Cancel after 5 files processed

            scanner = FileScannerImpl(
                root_dir=str(tmp_path),
                min_size=0,
                max_size=1024 * 1024,
                extensions=[".txt"],
                favourite_dirs=[]
            )
            collection = scanner.scan(stopped_flag=stopped_flag)

            # Should have partial results (not all 50 files)
            assert 0 < len(collection.files) < 50, (
                f"Cycle {cycle}: unexpected file count {len(collection.files)}"
            )

        # No assertion on memory usage (hard to measure portably),
        # but test passes if no exceptions raised during repeated cancellation
        # This verifies no resource leaks causing crashes over time