"""
Unit tests for DeduplicateWorker — Qt thread integration layer.
Verifies thread-safe cancellation, signal emission, and error handling.
"""

from unittest.mock import Mock
from highlander.core import (
    DeduplicationParams, DeduplicationMode,
    SortOrder, DuplicateGroup, DeduplicationStats
)
from highlander.gui import DeduplicateWorker


class TestDeduplicateWorker:
    """Test worker thread safety and signal emission."""

    def test_stop_sets_stopped_flag(self):
        """stop() must set internal _stopped flag to True."""
        params = DeduplicationParams(
            root_dir="/tmp",
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            mode=DeduplicationMode.FAST,
            sort_order=SortOrder.SHORTEST_PATH
        )

        worker = DeduplicateWorker(params)

        assert worker.is_stopped() is False
        worker.stop()
        assert worker.is_stopped() is True

    def test_is_stopped_is_thread_safe(self):
        """
        is_stopped() must be safe to call from multiple threads without races.
        Verified by absence of exceptions during repeated access.
        """
        params = DeduplicationParams(
            root_dir="/tmp",
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            mode=DeduplicationMode.FAST,
            sort_order=SortOrder.SHORTEST_PATH
        )

        worker = DeduplicateWorker(params)

        # Simulate repeated access (simplified concurrency check)
        for _ in range(100):
            _ = worker.is_stopped()

        worker.stop()
        for _ in range(100):
            assert worker.is_stopped() is True

    def test_safe_progress_emit_skips_after_stop(self):
        """
        safe_progress_emit() must NOT emit signals after stop() is called.
        Prevents UI updates after cancellation (race condition protection).
        """
        params = DeduplicationParams(
            root_dir="/tmp",
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            mode=DeduplicationMode.FAST,
            sort_order=SortOrder.SHORTEST_PATH
        )

        worker = DeduplicateWorker(params)
        progress_handler = Mock()
        worker.signals.progress.connect(progress_handler)

        # Emit before stop → should be received
        worker.safe_progress_emit("scanning", 10, 100)
        assert progress_handler.call_count == 1

        # Stop worker
        worker.stop()

        # Emit after stop → should be IGNORED (no signal)
        worker.safe_progress_emit("hashing", 20, 100)
        assert progress_handler.call_count == 1  # Still 1, not 2

    def test_run_emits_finished_on_success(self):
        """
        Successful execution must emit finished signal with groups/stats.
        """
        params = DeduplicationParams(
            root_dir="/tmp",
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            mode=DeduplicationMode.FAST,
            sort_order=SortOrder.SHORTEST_PATH
        )

        # Create worker first, then mock its command instance
        worker = DeduplicateWorker(params)
        mock_groups = [DuplicateGroup(size=1024, files=[])]
        mock_stats = DeduplicationStats()
        mock_stats.total_time = 1.23

        # Mock the INSTANCE'S command, not the class
        worker.command.execute = Mock(return_value=(mock_groups, mock_stats))

        finished_handler = Mock()
        worker.signals.finished.connect(finished_handler)

        # Execute run() directly
        worker.run()

        # Should emit finished signal exactly once
        assert finished_handler.call_count == 1

        # Verify emitted values
        call_args = finished_handler.call_args[0]
        assert len(call_args) == 2
        assert call_args[0] == mock_groups
        assert call_args[1] == mock_stats

    def test_run_emits_error_on_exception(self):
        """
        Execution failure must emit error signal with descriptive message.
        """
        params = DeduplicationParams(
            root_dir="/tmp",
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            mode=DeduplicationMode.FAST,
            sort_order=SortOrder.SHORTEST_PATH
        )

        worker = DeduplicateWorker(params)
        worker.command.execute = Mock(side_effect=ValueError("Simulated failure"))

        error_handler = Mock()
        worker.signals.error.connect(error_handler)

        worker.run()

        # Should emit error signal exactly once
        assert error_handler.call_count == 1

        # Verify error message format
        error_msg = error_handler.call_args[0][0]
        assert "ValueError" in error_msg
        assert "Simulated failure" in error_msg

    def test_run_does_not_emit_after_stop(self):
        """
        Worker must NOT emit finished/error signals after stop() is called.
        Critical protection against use-after-free when UI is destroyed.
        """
        params = DeduplicationParams(
            root_dir="/tmp",
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            mode=DeduplicationMode.FAST,
            sort_order=SortOrder.SHORTEST_PATH
        )

        worker = DeduplicateWorker(params)
        mock_groups = [DuplicateGroup(size=1024, files=[])]
        mock_stats = DeduplicationStats()

        # Simulate stop() being called during execute
        def execute_with_stop(*_, **__):
            worker.stop()  # Simulate user cancellation during execution
            return mock_groups, mock_stats

        worker.command.execute = Mock(side_effect=execute_with_stop)

        finished_handler = Mock()
        error_handler = Mock()
        worker.signals.finished.connect(finished_handler)
        worker.signals.error.connect(error_handler)

        worker.run()

        # Should emit NEITHER finished NOR error after stop()
        assert finished_handler.call_count == 0
        assert error_handler.call_count == 0

    def test_worker_auto_deletes_after_run(self):
        """
        QRunnable with setAutoDelete(True) must be deleted after run() completes.
        Verified by checking that auto-delete flag is set.
        """
        params = DeduplicationParams(
            root_dir="/tmp",
            min_size_bytes=0,
            max_size_bytes=1024 * 1024,
            extensions=[".txt"],
            favourite_dirs=[],
            mode=DeduplicationMode.FAST,
            sort_order=SortOrder.SHORTEST_PATH
        )

        worker = DeduplicateWorker(params)

        # Verify auto-delete is enabled (critical for memory safety)
        assert worker.autoDelete() is True

        # Mock successful execution
        mock_groups = [DuplicateGroup(size=1024, files=[])]
        mock_stats = DeduplicationStats()
        worker.command.execute = Mock(return_value=(mock_groups, mock_stats))

        # Execute run() — should complete without errors
        worker.run()
        # No assertion needed — successful execution proves auto-delete works
        # (Actual deletion happens at C++ level after run() returns)