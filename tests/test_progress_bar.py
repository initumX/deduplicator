"""Minimal tests for ProgressBar — core behavior only."""
from unittest.mock import patch
import sys

from onlyone.progress_bar import ProgressBar


@patch.object(sys.stderr, 'isatty', return_value=True)
def test_count_increments(_mock):
    """Counter increments when update() called without args."""
    bar = ProgressBar(total=10)
    bar.update()
    bar.update()
    assert bar._count == 2


@patch.object(sys.stderr, 'isatty', return_value=True)
def test_count_absolute(_mock):
    """Counter sets absolute value when update(n) called."""
    bar = ProgressBar(total=10)
    bar.update(5)
    assert bar._count == 5


@patch.object(sys.stderr, 'isatty', return_value=True)
def test_indeterminate_mode(_mock):
    """total=None triggers indeterminate mode (no percentage)."""
    bar = ProgressBar(total=None)
    bar.update(100)
    assert bar.total is None


@patch.object(sys.stderr, 'isatty', return_value=True)
def test_determinate_mode(_mock):
    """total=N triggers determinate mode (with percentage)."""
    bar = ProgressBar(total=100)
    bar.update(50)
    assert bar.total == 100


@patch.object(sys.stderr, 'isatty', return_value=True)
def test_ascii_mode_stored(_mock):
    """ascii_only flag is stored correctly."""
    bar_ascii = ProgressBar(ascii_only=True)
    bar_unicode = ProgressBar(ascii_only=False)
    assert bar_ascii.ascii_only is True
    assert bar_unicode.ascii_only is False


def test_auto_disable_when_not_tty():
    """Progress auto-disables when stderr is not a TTY."""
    with patch.object(sys.stderr, 'isatty', return_value=False):
        bar = ProgressBar(total=10)
        assert bar._enabled is False


@patch.object(sys.stderr, 'isatty', return_value=True)
def test_finish_no_crash(_mock):
    """finish() doesn't crash in any mode."""
    # Determinate
    bar1 = ProgressBar(total=10)
    bar1.finish()

    # Indeterminate
    bar2 = ProgressBar(total=None)
    bar2.finish()


@patch.object(sys.stderr, 'isatty', return_value=True)
def test_throttling_exists(_mock):
    """min_interval is stored (throttling logic tested manually)."""
    bar = ProgressBar(total=10, min_interval=0.5)
    assert bar.min_interval == 0.5