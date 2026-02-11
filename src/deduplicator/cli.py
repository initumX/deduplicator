#!/usr/bin/env python3
"""
File Deduplicator - Command Line Interface
A fast, safe tool for finding and removing duplicate files.
"""
import argparse
import sys
import os
import time
from pathlib import Path
from typing import List, Optional
from deduplicator.core.models import SortOrder

# === EARLY DEPENDENCY VALIDATION ===
_MISSING_DEPS = []
try:
    from send2trash import send2trash
except ImportError:
    _MISSING_DEPS.append("send2trash")
try:
    import xxhash
except ImportError:
    _MISSING_DEPS.append("xxhash")
if _MISSING_DEPS:
    print("❌ Missing required dependencies:", file=sys.stderr)
    print(f"   pip install {' '.join(_MISSING_DEPS)}", file=sys.stderr)
    print("\nOr install all dependencies:", file=sys.stderr)
    print("   pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

# === NORMAL IMPORTS (after validation) ===
from core.models import DeduplicationMode, DeduplicationParams, DuplicateGroup
from commands import DeduplicationCommand
from utils.convert_utils import ConvertUtils
from services.file_service import FileService
from services.duplicate_service import DuplicateService
from core.interfaces import TranslatorProtocol

class CLITranslator(TranslatorProtocol):
    """Minimal translator for CLI output."""
    def tr(self, key: str) -> str:
        translations = {
            "error_please_select_root": "Please specify a root directory with --root",
            "error_invalid_size_format": "Invalid size format",
            "error_directory_not_found": "Directory not found: {}",
            "error_permission_denied": "Permission denied accessing: {}",
            "message_no_duplicates_found": "No duplicate groups found.",
            "message_found_groups": "Found {} duplicate groups ({} files)",
            "message_dry_run_header": "DRY RUN - No files will be deleted",
            "message_confirm_deletion": "Are you sure you want to move {} files to trash? [y/N]: ",
            "message_deletion_confirmed": "Moving {} files to trash...",
            "message_deletion_cancelled": "Deletion cancelled by user.",
            "message_files_deleted": "Successfully moved {} files to trash.",
            "message_keep_one_preview": "Would keep 1 file per group ({} files preserved, {} files deleted)",
            "message_scanning": "Scanning files...",
            "message_deduplicating": "Finding duplicates (mode: {})...",
            "message_stats_header": "Deduplication Statistics",
            "message_total_space_saved": "Total space saved: {}",
            "error_deduplication_failed": "Deduplication failed: {}",
            "error_deletion_failed": "Failed to delete files: {}",
        }
        return translations.get(key, key)

class CLIApplication:
    """Main CLI application controller."""
    def __init__(self):
        self.translator: TranslatorProtocol = CLITranslator()
        self.command: Optional[DeduplicationCommand] = None
        self.start_time: float = time.time()
        self.verbose: bool = False
        self.quiet: bool = False

    @staticmethod
    def parse_args() -> argparse.Namespace:
        """Parse and validate command-line arguments."""
        parser = argparse.ArgumentParser(
            description="File Deduplicator - Find and remove duplicate files",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Basic usage - find duplicates in photos folder
  %(prog)s --root ./photos

  # Filter by size and extensions
  %(prog)s -r ./photos -m 500KB -M 10MB -e .jpg,.png

  # Prioritize files in 'keep' folder when deleting duplicates
  %(prog)s -r ./photos -f ./photos/keep --keep-one

  # Dry run to see what would be deleted
  %(prog)s -r ./photos --keep-one --dry-run

  # Full content comparison (slowest but most accurate)
  %(prog)s -r ./photos --mode full
"""
        )
        # Required arguments
        parser.add_argument(
            "--root", "-r",
            required=True,
            type=str,
            help="Root directory to scan for duplicates"
        )
        # Filtering options
        parser.add_argument(
            "--min-size", "-m",
            default="0",
            type=str,
            help="Minimum file size (e.g., 500KB, 1MB). Default: 0"
        )
        parser.add_argument(
            "--max-size", "-M",
            default="100GB",
            type=str,
            help="Maximum file size (e.g., 10MB, 1GB). Default: 100GB"
        )
        parser.add_argument(
            "--extensions", "-e",
            default="",
            type=str,
            help="Comma-separated file extensions to include (e.g., .jpg,.png)"
        )
        parser.add_argument(
            "--favorite-dirs", "-f",
            nargs="+",
            default=[],
            type=str,
            help="Directories with files to prioritize when deleting duplicates"
        )
        # Deduplication options
        parser.add_argument(
            "--mode",
            choices=["fast", "normal", "full"],
            default="normal",
            type=str,
            help="Deduplication mode: "
                 "fast (size + front hash), "
                 "normal (size + front/middle/end hashes), "
                 "full (full content hash). Default: normal"
        )
        parser.add_argument(
            "--keep-one",
            action="store_true",
            help="Keep one file per duplicate group (first file from favorite dirs if available)"
        )
        parser.add_argument(
            "--sort-order",
            choices=["newest", "oldest"],
            default="newest",
            help="Which file to keep when deleting duplicates: newest or oldest. Default: newest"
        )
        # Output options
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting files"
        )
        parser.add_argument(
            "--quiet", "-q",
            action="store_true",
            help="Suppress non-essential output"
        )
        parser.add_argument(
            "--verbose", "-v",
            action="store_true",
            help="Show detailed statistics and progress"
        )
        return parser.parse_args()

    def validate_args(self, args: argparse.Namespace) -> None:
        """Validate command-line arguments before execution."""
        root_path = Path(args.root).resolve()
        if not root_path.exists():
            self.error_exit(self.translator.tr("error_directory_not_found").format(args.root))
        if not root_path.is_dir():
            self.error_exit(f"Path is not a directory: {args.root}")
        # Validate size formats
        try:
            min_size = ConvertUtils.human_to_bytes(args.min_size)
            max_size = ConvertUtils.human_to_bytes(args.max_size)
            if min_size < 0:
                self.error_exit("Minimum size cannot be negative")
            if max_size < min_size:
                self.error_exit("Maximum size cannot be less than minimum size")
        except ValueError as e:
            self.error_exit(f"{self.translator.tr('error_invalid_size_format')}: {e}")
        # Validate favorite directories
        for fav_dir in args.favorite_dirs:
            fav_path = Path(fav_dir).resolve()
            if not fav_path.exists():
                self.warning(f"Warning: Favorite directory not found: {fav_dir}")
            elif not fav_path.is_dir():
                self.warning(f"Warning: Favorite path is not a directory: {fav_dir}")

    def create_params(self, args: argparse.Namespace) -> DeduplicationParams:
        """Create DeduplicationParams from CLI arguments."""
        try:
            min_size_bytes = ConvertUtils.human_to_bytes(args.min_size)
            max_size_bytes = ConvertUtils.human_to_bytes(args.max_size)
            # Parse extensions
            extensions = []
            if args.extensions:
                extensions = [
                    ext.strip().lower()
                    for ext in args.extensions.split(",")
                    if ext.strip()
                ]
                extensions = [
                    ext if ext.startswith(".") else f".{ext}"
                    for ext in extensions
                ]
            # Resolve favorite directories to absolute paths
            favorite_dirs = [
                str(Path(d).resolve())
                for d in args.favorite_dirs
            ]
            mode = DeduplicationMode[args.mode.upper()]
            sort_order = SortOrder(args.sort_order)
            return DeduplicationParams(
                root_dir=str(Path(args.root).resolve()),
                min_size_bytes=min_size_bytes,
                max_size_bytes=max_size_bytes,
                extensions=extensions,
                favourite_dirs=favorite_dirs,
                sort_order=sort_order,
                mode=mode
            )
        except ValueError as e:
            self.error_exit(f"Parameter error: {e}")

    def progress_callback(self, stage: str, current: int, total: Optional[int]) -> None:
        """CLI progress callback - shows progress in console."""
        if not self.verbose:
            return
        if total and total > 0:
            percent = (current / total) * 100
            sys.stderr.write(
                f"\r  [{stage}] {current}/{total} ({percent:.1f}%)"
            )
            sys.stderr.flush()
        else:
            sys.stderr.write(f"\r  [{stage}] {current} files processed...")
            sys.stderr.flush()

    @staticmethod
    def stopped_flag() -> bool:
        """Check if operation should stop (placeholder for signal handling)."""
        return False

    @staticmethod
    def calculate_space_savings(groups: List[DuplicateGroup], files_to_delete: List[str]) -> int:
        """Calculate total space that would be freed by deleting files."""
        total_bytes = 0
        delete_set = set(files_to_delete)
        for group in groups:
            for file in group.files:
                if file.path in delete_set:
                    total_bytes += file.size
        return total_bytes

    def run_deduplication(self, params: DeduplicationParams) -> List[DuplicateGroup]:
        """Execute deduplication workflow."""
        self.command = DeduplicationCommand()
        if self.verbose:
            mode_display = params.mode.value.capitalize()
            print(self.translator.tr("message_deduplicating").format(mode_display))
        try:
            groups, stats = self.command.execute(
                params,
                progress_callback=self.progress_callback if self.verbose else None,
                stopped_flag=self.stopped_flag
            )
            if self.verbose:
                sys.stderr.write("\n")
                print(f"\n{self.translator.tr('message_stats_header')}:")
                print(stats.print_summary())
            return groups
        except Exception as e:
            self.error_exit(self.translator.tr("error_deduplication_failed").format(e))

    def output_results(self, groups: List[DuplicateGroup]) -> None:
        """Output duplicate groups as plain text without additional sorting."""
        if self.quiet:
            return
        if not groups:
            print(self.translator.tr("message_no_duplicates_found"))
            return
        total_files = sum(len(g.files) for g in groups)
        print(self.translator.tr("message_found_groups").format(len(groups), total_files))
        for idx, group in enumerate(groups, 1):
            size_str = ConvertUtils.bytes_to_human(group.size)
            print(f"\n📁 Group {idx} | Size: {size_str} | Files: {len(group.files)}")
            # Use order from core (already sorted by favorite dirs + sort_order)
            for file in group.files:
                fav_marker = " ✅" if file.is_from_fav_dir else ""
                time_str = ConvertUtils.timestamp_to_human(file.creation_time) if file.creation_time else "N/A"
                print(f"   {file.path} [{ConvertUtils.bytes_to_human(file.size)}] ({time_str}){fav_marker}")

    def execute_keep_one(self, groups: List[DuplicateGroup], params: DeduplicationParams, dry_run: bool = False) -> None:
        """Keep one file per group, delete the rest."""
        if not groups:
            if not self.quiet:
                print(self.translator.tr("message_no_duplicates_found"))
            return
        files_to_delete, _ = DuplicateService.keep_only_one_file_per_group(groups)
        if not files_to_delete:
            if not self.quiet:
                print("No files to delete (all groups already have only one file).")
            return
        # Calculate space savings
        space_saved = self.calculate_space_savings(groups, files_to_delete)
        space_saved_str = ConvertUtils.bytes_to_human(space_saved)
        # Always show deletion preview before action
        print()
        if dry_run:
            print(self.translator.tr("message_dry_run_header"))
            print()
            preserved = len(groups)
            for idx, group in enumerate(groups, 1):
                size_str = ConvertUtils.bytes_to_human(group.size)
                print(f"📁 Group {idx} | Total size: {size_str} | Files: {len(group.files)}")
                print("-" * 60)
                # File that will be preserved (first file after core sorting)
                preserved_file = group.files[0]
                fav_marker = " ⭐" if preserved_file.is_from_fav_dir else ""
                print(f"   [KEEP] {preserved_file.path}")
                print(f"          Size: {ConvertUtils.bytes_to_human(preserved_file.size)}{fav_marker}")
                if preserved_file.is_from_fav_dir:
                    print(f"          Reason: from favorite directory")
                else:
                    print(f"          Reason: based on sort order ({params.sort_order.value})")
                # Files that would be deleted
                for file in group.files[1:]:
                    fav_marker = " ⭐" if file.is_from_fav_dir else ""
                    print(f"   [DEL]  {file.path}")
                    print(f"          Size: {ConvertUtils.bytes_to_human(file.size)}{fav_marker}")
                print()
            print("=" * 60)
            print(self.translator.tr("message_keep_one_preview").format(preserved, len(files_to_delete)))
            print(self.translator.tr("message_total_space_saved").format(space_saved_str))
            print()
            print("ℹ️  No files were deleted. This was a dry run simulation.")
            return
        # Show marked list BEFORE asking for confirmation (no unmarked list shown first)
        preserved = len(groups)
        for idx, group in enumerate(groups, 1):
            size_str = ConvertUtils.bytes_to_human(group.size)
            print(f"📁 Group {idx} | Total size: {size_str} | Files: {len(group.files)}")
            print("-" * 60)
            # File that will be preserved
            preserved_file = group.files[0]
            fav_marker = " ⭐" if preserved_file.is_from_fav_dir else ""
            print(f"   [KEEP] {preserved_file.path}")
            print(f"          Size: {ConvertUtils.bytes_to_human(preserved_file.size)}{fav_marker}")
            if preserved_file.is_from_fav_dir:
                print(f"          Reason: from favorite directory")
            else:
                print(f"          Reason: based on sort order ({params.sort_order.value})")
            # Files that would be deleted
            for file in group.files[1:]:
                fav_marker = " ⭐" if file.is_from_fav_dir else ""
                print(f"   [DEL]  {file.path}")
                print(f"          Size: {ConvertUtils.bytes_to_human(file.size)}{fav_marker}")
            print()
        print("=" * 60)
        print(self.translator.tr("message_keep_one_preview").format(preserved, len(files_to_delete)))
        print(self.translator.tr("message_total_space_saved").format(space_saved_str))
        print()
        # Ask for confirmation before actual deletion
        response = input(self.translator.tr("message_confirm_deletion").format(len(files_to_delete)))
        if response.strip().lower() not in ("y", "yes"):
            print(self.translator.tr("message_deletion_cancelled"))
            return
        # Execute deletion
        print(self.translator.tr("message_deletion_confirmed").format(len(files_to_delete)))
        try:
            for i, path in enumerate(files_to_delete, 1):
                if self.verbose:
                    print(f"  [{i}/{len(files_to_delete)}] {os.path.basename(path)}")
                FileService.move_to_trash(path)
            print(self.translator.tr("message_files_deleted").format(len(files_to_delete)))
            print(self.translator.tr("message_total_space_saved").format(space_saved_str))
        except Exception as e:
            self.error_exit(self.translator.tr("error_deletion_failed").format(e))

    def warning(self, message: str) -> None:
        """Print a warning message to stderr."""
        if not self.quiet:
            print(f"⚠️  {message}", file=sys.stderr)

    @staticmethod
    def error_exit(message: str, code: int = 1) -> None:
        """Print error and exit."""
        print(f"❌ Error: {message}", file=sys.stderr)
        sys.exit(code)

    def run(self) -> None:
        """Main entry point with conditional output behavior."""
        args = self.parse_args()
        self.verbose = args.verbose
        self.quiet = args.quiet
        # Validate arguments
        self.validate_args(args)
        # Create params
        params = self.create_params(args)
        # Scan and find duplicates
        if not self.quiet:
            print(self.translator.tr("message_scanning"))
        groups = self.run_deduplication(params)
        # Conditional output based on flags - NO redundant output
        if args.keep_one:
            # Show ONLY marked list with [KEEP]/[DEL] - skip unmarked output entirely
            self.execute_keep_one(groups, params=params, dry_run=args.dry_run)
        else:
            # Show standard unmarked duplicate groups list
            self.output_results(groups)
        # Show completion time
        elapsed = time.time() - self.start_time
        if self.verbose:
            print(f"\n✅ Completed in {elapsed:.2f} seconds")

def main() -> None:
    """Application entry point."""
    app = CLIApplication()
    try:
        app.run()
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user (Ctrl+C)")
        sys.exit(130)
    except Exception as e:
        if os.environ.get("DEBUG"):
            raise
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()