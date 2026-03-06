"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License

reporter.py
Formatting helpers for CLI output. Returns strings; cli.py handles printing.
"""

from typing import List, Optional
from onlyone.core.models import DuplicateGroup, DeduplicationStats
from onlyone.core.measurer import bytes_to_human


def _get_icons(ascii_only: bool) -> dict:
    """Return icon set based on ascii_only flag."""
    if ascii_only:
        return {
            'group': '[G]',
            'fav': ' (FAV)',
            'warning': 'WARNING: ',
            'success': 'OK: ',
            'bullet': '  -',
        }
    else:
        return {
            'group': '📁',
            'fav': ' (FAV)',
            'warning': 'WARNING:',
            'success': '✅ ',
            'bullet': '  •',
        }

def format_groups_output(
        groups: List[DuplicateGroup],
        show_fav_markers: bool = True,
        ascii_only: bool = False,
        stats: Optional[DeduplicationStats] = None
) -> str:
    """Format duplicate groups as human-readable text. Returns a single string."""
    if not groups:
        return "No duplicate groups found."

    lines = []
    total_files = sum(len(g.files) for g in groups)

    if stats and stats.groups_truncated:
        icons = _get_icons(ascii_only)
        print()
        lines.append(f"{icons['warning']}\nResults limited to {len(groups)} groups (showing largest first)")
        lines.append(f"Total groups found: {stats.total_groups_found}")
        lines.append(f"Use --max-groups with higher value for full results")
        lines.append("")
    else:
        lines.append(f"Found {len(groups)} duplicate groups ({total_files} files)")

    for idx, group in enumerate(groups, 1):
        lines.extend(format_group(group, idx, show_fav_markers, ascii_only))

    return "\n".join(lines)

def format_group(group: DuplicateGroup, idx: int, show_fav_markers: bool = True, ascii_only: bool = False) -> List[str]:
    """Format a single duplicate group. Returns list of lines."""
    icons = _get_icons(ascii_only)
    lines = []
    size_str = bytes_to_human(group.size)
    lines.append(f"\n{icons['group']} Group {idx} | File size {size_str} ")

    for file in group.files:
        marker = icons['fav'] if show_fav_markers and file.is_from_fav_dir else ""
        lines.append(f"   {file.path} [{bytes_to_human(file.size)}]{marker}")

    return lines


def format_deletion_preview(
    groups: List[DuplicateGroup],
    files_to_delete: List[str],
    space_saved: int,
    show_fav_markers: bool = True,
    ascii_only: bool = False
) -> str:
    """Format preview of files to be deleted. Returns a single string."""
    icons = _get_icons(ascii_only)
    lines = []
    preserved = len(groups)

    for idx, group in enumerate(groups, 1):
        size_str = bytes_to_human(group.size)
        lines.append(f"{icons['group']} Group {idx} | File size: {size_str}")
        lines.append("-" * 60)

        preserved_file = group.files[0]
        marker = icons['fav'] if show_fav_markers and preserved_file.is_from_fav_dir else ""
        lines.append(f"   [KEEP] {preserved_file.path}{marker}")

        for file in group.files[1:]:
            marker = icons['fav'] if show_fav_markers and file.is_from_fav_dir else ""
            lines.append(f"   [DEL]  {file.path} {marker}")
        lines.append("")

    lines.append("=" * 60)
    lines.append(f"Summary: Keep 1 file per group ({preserved} preserved, {len(files_to_delete)} deleted)")
    lines.append(f"Total space saved: {bytes_to_human(space_saved)}")
    lines.append("")

    return "\n".join(lines)


def format_deletion_result(
    deleted_count: int,
    total_count: int,
    space_saved: int,
    failed_files: List[tuple],
    ascii_only: bool = False
) -> str:
    """Format deletion result message. Returns a single string."""
    import os
    icons = _get_icons(ascii_only)

    if failed_files:
        lines = [
            f"\n{icons['warning']}Partial success: {deleted_count}/{total_count} files moved to trash.",
            f"Failed to delete {len(failed_files)} file(s):"
        ]
        for path, error in failed_files[:5]:
            name = os.path.basename(path)
            msg = error.split(':')[-1].strip()
            lines.append(f"{icons['bullet']} {name}: {msg}")
        if len(failed_files) > 5:
            lines.append(f"  ...and {len(failed_files) - 5} more files")
        return "\n".join(lines)
    else:
        return f"\n{icons['success']}Successfully moved {deleted_count} files to trash.\nTotal space saved: {bytes_to_human(space_saved)}"