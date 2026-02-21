"""
Copyright (c) 2026 initumX (initum.x@gmail.com)
Licensed under the MIT License

core/normalizer.py
Implements fuzzy filename normalization for duplicate detection.
"""

import re
import os
from functools import lru_cache

# Pre-compiled regex patterns (performance optimization)
_PATTERN_BRACKETS = re.compile(r'\s*\([^)]*\)\s*')
_PATTERN_COPY_MARKERS = re.compile(r'[_\-]?(copy|new|final|old|backup)[_\-\s]?\d*\s*$', re.IGNORECASE)
_PATTERN_TRAILING_NUMBERS = re.compile(r'[_\-]\d{1,3}\s*$')
_PATTERN_NOISE = re.compile(r'[_\s.\-]')

@lru_cache(maxsize=8192)
def normalize_filename(filename: str) -> str:
    """
    Normalize a filename for fuzzy duplicate detection.

    Normalization rules:
    - Convert to lowercase
    - Remove bracket content: (1), (copy), (Final Version), etc.
    - Remove trailing copy markers: _copy, Copy2, -new3, _final, backup_1, etc.
    - Remove 1-3 trailing digits after separators: _1, _12, _123 (not _1234!)
    - Remove noise characters: underscores, spaces, dots, hyphens
…        str: Normalized filename for comparison (e.g., "dsc0001.jpg")

    Examples:
        "DSC_0001.JPG" → "dsc0001.jpg"
        "DSC_0001Copy2.JPG" → "dsc0001.jpg"
        "Report (1).pdf" → "report.pdf"
        "Report_2024.pdf" → "report2024.pdf"
        "Report_123.pdf" → "report.pdf"
    """
    if not filename:
        return ""

    # Separate name and extension
    name, ext = os.path.splitext(filename.lower())

    # Step 1: Remove bracket content
    name = _PATTERN_BRACKETS.sub('', name)

    # Step 2: Remove trailing copy markers with words
    name = _PATTERN_COPY_MARKERS.sub('', name)

    # Step 3: Remove trailing numbers (1-3 digits only, 4+ preserved)
    name = _PATTERN_TRAILING_NUMBERS.sub('', name)

    # Step 4: Remove noise characters
    name = _PATTERN_NOISE.sub('', name)

    # Add extension back
    return name + ext