"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License

progress_bar.py
A lightweight, dependency-free progress bar for CLI applications.
"""

import sys
import time
from typing import Optional, Iterable, Any, Union, Sized


class ProgressBar:
    """
    A simple, reusable progress bar without external dependencies.
    """

    def __init__(
        self,
        total: Optional[int] = None,
        prefix: str = 'Progress',
        suffix: str = 'Complete',
        decimals: int = 1,
        length: int = 50,
        fill: str = '█',
        empty: str = '-',
        enable: bool = True,
        indeterminate: bool = False,
        min_interval: float = 0.1
    ):
        self.total = total
        self.indeterminate = indeterminate or (total is None)
        self.current = 0
        self._animation_frame = 0
        self._animation_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self.prefix = prefix
        self.suffix = suffix
        self.decimals = max(decimals, 0)
        self.length = max(length, 1)
        self.fill = fill
        self.empty = empty
        self.enable = enable
        self.min_interval = min_interval
        self._last_update = 0.0

    def _format_percent(self) -> str:
        if self.indeterminate or self.total is None or self.total == 0:
            return "---"
        percent = 100 * (self.current / float(self.total))
        return f"{percent:.{self.decimals}f}"

    def _format_bar(self) -> str:
        if self.indeterminate or self.total is None or self.total == 0:
            # Spinner animation
            char = self._animation_chars[self._animation_frame % len(self._animation_chars)]
            self._animation_frame += 1
            return f"{char} Processing..."
        else:
            # Normal progress-bar
            filled = int(self.length * self.current // self.total)
            filled = min(filled, self.length)
            return self.fill * filled + self.empty * (self.length - filled)

    def update(self, iteration: Optional[int] = None, increment: int = 1) -> None:
        if not self.enable:
            return

        if iteration is not None:
            self.current = iteration
        else:
            self.current += increment

        if self.total is not None:
            self.current = min(self.current, self.total)

        # Throttling by time
        if self.min_interval > 0:
            now = time.time()
            if now - self._last_update < self.min_interval:
                if self.total is None or self.current < self.total:
                    return
            self._last_update = now

        percent = self._format_percent()
        bar = self._format_bar()

        sys.stdout.write(f'\r{self.prefix}: |{bar}| {percent}% {self.suffix}')
        sys.stdout.flush()

        if self.total is not None and self.current >= self.total:
            print()

    def reset(self) -> None:
        self.current = 0
        if self.enable:
            self.update(0)

    def finish(self) -> None:
        if self.total is not None:
            self.current = self.total
            self.update(self.total)
        else:
            # For indeterminated progress bar
            self.current = 0
            sys.stdout.write(f'\r{self.prefix}: |✓| Done {self.suffix}')
            sys.stdout.flush()
            print()


def progress_iter(
    iterable: Union[Iterable[Any], Sized],
    total: Optional[int] = None,
    prefix: str = 'Progress',
    suffix: str = 'Complete',
    decimals: int = 1,
    length: int = 50,
    fill: str = '█',
    enable: bool = True
) -> Iterable[Any]:
    """
    Wrap any iterable with a progress bar.
    """
    if total is None:
        try:
            total = len(iterable)  # type: ignore[arg-type]
        except TypeError:
            total = None

    bar = ProgressBar(
        total=total,
        prefix=prefix,
        suffix=suffix,
        decimals=decimals,
        length=length,
        fill=fill,
        enable=enable,
        indeterminate=(total is None)
    )

    bar.update(0)
    for item in iterable:
        yield item
        bar.update()


class ProgressContext:
    """
    Context manager for use with 'with' statements.
    """

    def __init__(
        self,
        total: Optional[int] = None,
        prefix: str = 'Progress',
        suffix: str = 'Complete',
        decimals: int = 1,
        length: int = 50,
        fill: str = '█',
        enable: bool = True
    ):
        self.bar = ProgressBar(
            total=total,
            prefix=prefix,
            suffix=suffix,
            decimals=decimals,
            length=length,
            fill=fill,
            enable=enable,
            indeterminate=(total is None)
        )

    def __enter__(self) -> ProgressBar:
        self.bar.update(0)
        return self.bar

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.bar.finish()


# Convenience function
def progress(
    total: Optional[int] = None,
    prefix: str = 'Progress',
    suffix: str = 'Complete',
    decimals: int = 1,
    length: int = 50,
    fill: str = '█',
    enable: bool = True,
) -> ProgressBar:
    """
    Create and return a ProgressBar instance.
    """
    return ProgressBar(
        total=total,
        prefix=prefix,
        suffix=suffix,
        decimals=decimals,
        length=length,
        fill=fill,
        enable=enable,
        indeterminate=(total is None)
    )