"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License

progress_bar.py
A lightweight, dependency-free progress bar for CLI applications.
"""
import sys
import time
from typing import Optional


class ProgressBar:
    """Lightweight progress: counter + optional spinner for unknown totals."""

    def __init__(
        self,
        prefix: str = "Processing",
        total: Optional[int] = None,
        ascii_only: bool = False,
        min_interval: float = 0.2,  # Throttle updates to avoid flicker
    ):
        self.prefix = prefix
        self.total = total  # None = indeterminate mode
        self.ascii_only = ascii_only
        self.min_interval = min_interval
        self._count = 0
        self._last_update = 0.0
        self._enabled = sys.stderr.isatty()  # Auto-disable when piped

        # Minimal spinner sets
        self._spin_ascii = ['|', '/', '-', '\\']
        self._spin_unicode = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']

    def update(self, count: Optional[int] = None) -> None:
        """Update progress. Pass absolute count, or None to increment by 1."""
        if not self._enabled:
            return

        # Increment or set absolute value
        self._count = count if count is not None else self._count + 1

        # Throttle: skip redraw if too soon (unless we're finishing)
        now = time.time()
        is_done = self.total is not None and self._count >= self.total
        if not is_done and now - self._last_update < self.min_interval:
            return
        self._last_update = now

        # Build status text
        if self.total:
            # Determinate: show counter + percentage
            pct = 100 * self._count / self.total
            status = f"{self._count:,}/{self.total:,} ({pct:.1f}%)"
            marker = "✓" if is_done else "•"
        else:
            # Indeterminate: spinner + counter only
            spin_set = self._spin_ascii if self.ascii_only else self._spin_unicode
            marker = spin_set[self._count % len(spin_set)]
            status = f"{self._count:,} files"

        # Single-line carriage-return update
        sys.stderr.write(f"\r{self.prefix}: {marker} {status}")
        sys.stderr.flush()

        # Final newline when determinate progress completes
        if is_done:
            print(file=sys.stderr)

    def finish(self) -> None:
        """Ensure final state is rendered (especially for indeterminate mode)."""
        if self._enabled and self.total is None:
            sys.stderr.write(f"\r{self.prefix}: ✓ {self._count:,} files\n")
            sys.stderr.flush()