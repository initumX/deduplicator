#!/usr/bin/env python3
"""
CLI for File Deduplication and Similar Image Finder Application.

Usage:
    cli.py scan <directory> [options]
    cli.py find_duplicates [options]
    cli.py find_similar_images [options]
    cli.py delete
    cli.py list_files
    cli.py show_stats
"""

import sys
import json
import argparse
from pathlib import Path
from typing import List, Any
from core.models import File, DeduplicationMode
from api import FileDeduplicateApp
from utils.size_utils import SizeUtils


# =============================
# Constants
# =============================
STATE_FILE = "cli_state.json"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}


# =============================
# Utility Functions
# =============================
def load_state() -> FileDeduplicateApp:
    if Path(STATE_FILE).exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        files = [File(**f) for f in data["files"]]
        app = FileDeduplicateApp(data["root_dir"])
        app.files = files
        return app
    else:
        print("❌ No state found. Run 'scan' first.")
        sys.exit(1)


def save_state(app: FileDeduplicateApp):
    data = {
        "root_dir": app.root_dir,
        "files": [file.to_dict() for file in app.files]
    }
    with open(STATE_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def output_json(data: Any):
    print(json.dumps(data, indent=2))


def input_paths_from_stdin() -> List[str]:
    return [line.strip() for line in sys.stdin if line.strip()]


# =============================
# CLI Commands
# =============================
def cmd_scan(args: argparse.Namespace):
    """Scan a directory and save the file list."""
    root_dir = args.directory

    min_size = None
    max_size = None

    if args.min_size:
        if not SizeUtils.is_valid_size_format(args.min_size):
            print(f"Invalid --min-size format: {args.min_size}")
            sys.exit(1)
        min_size = SizeUtils.human_to_bytes(args.min_size)

    if args.max_size:
        if not SizeUtils.is_valid_size_format(args.max_size):
            print(f"Invalid --max-size format: {args.max_size}")
            sys.exit(1)
        max_size = SizeUtils.human_to_bytes(args.max_size)

    extensions = None
    if args.extensions:
        extensions = [f".{ext.strip().lower()}" for ext in args.extensions.split(",")]

    app = FileDeduplicateApp(root_dir=root_dir)
    collection = app.scan_directory(
        min_size=min_size,
        max_size=max_size,
        extensions=extensions,
        stopped_flag=lambda: False
    )
    save_state(app)

    result = {"files_scanned": len(collection.files)}
    if args.verbose:
        result["file_list"] = [
            {"path": f.path, "size_human": SizeUtils.bytes_to_human(f.size)} for f in collection.files
        ]
    output_json(result)


def cmd_find_duplicates(args: argparse.Namespace):
    """Find duplicate files based on content hashes."""
    app = load_state()
    mode = DeduplicationMode(args.mode)
    groups = app.find_duplicates(mode=mode)
    result = [{"group": [f.path for f in g.files]} for g in groups]

    if args.verbose:
        stats = app.get_stats()
        result.append({"stats": stats.stage_stats})

    output_json(result)


def cmd_find_similar_images(args: argparse.Namespace):
    """Find visually similar images using perceptual hashing."""
    app = load_state()
    threshold = args.threshold
    groups = app.find_similar_images(threshold=threshold)
    result = [{"group": [f.path for f in g.files]} for g in groups]
    output_json(result)


def cmd_delete(_):
    """Delete selected files via stdin."""
    paths = input_paths_from_stdin()
    app = load_state()
    app.delete_files(paths)
    save_state(app)
    output_json({"deleted": len(paths)})


def cmd_list_files(_):
    """List all scanned files."""
    app = load_state()
    output = [
        {
            "path": f.path,
            "size": f.size,
            "human_size": SizeUtils.bytes_to_human(f.size)
        }
        for f in app.files
    ]
    output_json(output)


def cmd_show_stats(_):
    """Show deduplication statistics."""
    app = load_state()
    stats = app.get_stats()
    output_json(stats.stage_stats)


# =============================
# Main CLI Setup
# =============================
def main():
    parser = argparse.ArgumentParser(description="File Deduplicator & Similar Image Finder")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Scan command
    scan_parser = subparsers.add_parser("scan", help="Scan directory for files")
    scan_parser.add_argument("directory", help="Root directory to scan")
    scan_parser.add_argument("--min-size", type=str, default=None, help="Minimum size (e.g., 1.5GB)")
    scan_parser.add_argument("--max-size", type=str, default=None, help="Maximum size (e.g., 20MB)")
    scan_parser.add_argument("--ext", dest="extensions", default=None, help="Comma-separated extensions, e.g., jpg,png")
    scan_parser.add_argument("-v", "--verbose", action="store_true", help="Output full file list")

    # Find duplicates command
    dup_parser = subparsers.add_parser("find_duplicates", help="Find exact duplicate files")
    dup_parser.add_argument("--mode", choices=["FAST", "NORMAL", "FULL"], default="NORMAL",
                           help="Deduplication mode")
    dup_parser.add_argument("-v", "--verbose", action="store_true", help="Include detailed stats")

    # Find similar images command
    sim_parser = subparsers.add_parser("find_similar_images", help="Find visually similar images")
    sim_parser.add_argument("--threshold", type=int, default=5, help="Max perceptual hash difference")

    # Delete command
    del_parser = subparsers.add_parser("delete", help="Delete files listed via stdin")

    # List files command
    subparsers.add_parser("list_files", help="List all scanned files")

    # Show stats command
    subparsers.add_parser("show_stats", help="Show deduplication statistics")

    args = parser.parse_args()

    commands = {
        "scan": cmd_scan,
        "find_duplicates": cmd_find_duplicates,
        "find_similar_images": cmd_find_similar_images,
        "delete": cmd_delete,
        "list_files": cmd_list_files,
        "show_stats": cmd_show_stats,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()