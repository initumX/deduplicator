"""Basic tests for ProgressBar — smoke + edge cases."""
from unittest.mock import patch
from onlyone.progress_bar import ProgressBar


def test_format_percent_known_total():
    """Percentage calculation with known total."""
    bar = ProgressBar(total=100, force_tty=True)
    bar.current = 50
    assert bar._format_percent() == "50.0"

    bar.current = 100
    assert bar._format_percent() == "100.0"


def test_format_percent_indeterminate():
    """Percentage returns '---' when total is unknown."""
    bar = ProgressBar(total=None, force_tty=True)
    assert bar._format_percent() == "---"

    bar = ProgressBar(total=0, force_tty=True)
    assert bar._format_percent() == "---"


def test_format_bar_determinate():
    """Progress bar fills correctly."""
    bar = ProgressBar(total=100, length=10, force_tty=True)
    bar.current = 50
    result = bar._format_bar()
    fill_char = '#' if bar.ascii_only else '█'
    assert result.count(fill_char) == 5


def test_format_bar_indeterminate_spinner():
    """Spinner cycles through animation chars."""
    bar = ProgressBar(total=None, ascii_only=False, force_tty=True)
    first = bar._format_bar()
    second = bar._format_bar()
    assert first != second  # Spinner should advance


def test_ascii_mode_switches_chars():
    """ASCII mode uses different characters."""
    bar_unicode = ProgressBar(ascii_only=False, total=10, force_tty=True)
    bar_ascii = ProgressBar(ascii_only=True, total=10, force_tty=True)

    bar_unicode.current = 5
    bar_ascii.current = 5

    assert '█' in bar_unicode._format_bar()
    assert '#' in bar_ascii._format_bar()
    assert '|' in bar_ascii._animation_chars  # ASCII spinner


def test_throttling_skips_updates():
    """Updates are skipped when min_interval not elapsed."""
    with patch('time.time') as mock_time:
        # _last_update initialized to -0.1
        # Call 1: now=0 → 0-(-0.1)=0.1 >= 0.1 → PASS ✓
        # Call 2: now=0.05 → 0.05-0=0.05 < 0.1 → SKIP ✓
        # Call 3: now=0.15 → 0.15-0=0.15 >= 0.1 → PASS ✓
        mock_time.side_effect = [0, 0.05, 0.15]

        bar = ProgressBar(total=100, min_interval=0.1, force_tty=True)

        with patch('onlyone.progress_bar.sys.stderr.write') as mock_write:
            bar.update(1)  # t=0: should update
            bar.update(2)  # t=0.05: should skip
            bar.update(3)  # t=0.15: should update

            # Expect 2 writes: first + third
            assert mock_write.call_count == 2


def test_finish_completes_without_error():
    """finish() doesn't crash on any configuration."""
    # Determinate
    bar1 = ProgressBar(total=10, force_tty=True)
    bar1.finish()  # Should not raise

    # Indeterminate
    bar2 = ProgressBar(total=None, force_tty=True)
    bar2.finish()  # Should not raise

def test_auto_disable_when_not_tty():
    with patch('onlyone.progress_bar.sys.stderr.isatty', return_value=False):
        bar = ProgressBar(total=100)  # force_tty=False by default
        assert bar.enable is False