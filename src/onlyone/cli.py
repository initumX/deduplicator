#!/usr/bin/env python3
"""
OnlyOne CLI — Command line interface for duplicate file detection and removal.
Implements the same core engine as GUI but with console-based interaction.
All operations are safe: deletion moves files to system trash, never permanent erase.
"""
from __future__ import annotations  # Enable postponed evaluation of annotations (PEP 563)
import argparse
import sys
import os
import time
from pathlib import Path
from typing import List, Optional, NoReturn
import logging

logging.basicConfig(
    level=logging.ERROR,
    format="%(levelname)-8s | %(name)-25s | %(message)s"
)

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
from onlyone.core.models import DeduplicationMode, DeduplicationParams, DuplicateGroup, SortOrder, BoostMode
from onlyone.commands import DeduplicationCommand
from onlyone.utils.convert_utils import ConvertUtils
from onlyone.services.file_service import FileService
from onlyone.services.duplicate_service import DuplicateService
from onlyone.aliases import (
    BOOST_ALIASES, BOOST_CHOICES, BOOST_HELP_TEXT,
    DEDUP_MODE_ALIASES, DEDUP_MODE_CHOICES, DEDUP_MODE_HELP_TEXT,
    EPILOG_TEXT
)


class CLIApplication:
    """Main CLI application controller."""

    def __init__(self):
        self.start_time: float = time.time()
        self.verbose: bool = False
        self.quiet: bool = False

        # Fix encoding for Windows consoles to prevent UnicodeEncodeError
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')

    @staticmethod
    def parse_args(args=None) -> argparse.Namespace:
        """Parse and validate command-line arguments."""
        parser = argparse.ArgumentParser(
            description="OnlyOne — Fast duplicate file finder with safe deletion",
            formatter_class=argparse.RawTextHelpFormatter,
            epilog=EPILOG_TEXT
        )

        # Required arguments
        parser.add_argument(
            "--input", "-i",
            required=True,
            type=str,
            help="Input directory to scan for duplicates"
        )

        # Filtering options
        parser.add_argument(
            "--min-size", "-m",
            default="0",
            type=str,
            metavar='',
            help="Minimum file size (e.g., 500KB, 1MB). Default: 0"
        )
        parser.add_argument(
            "--max-size", "-M",
            default="100GB",
            type=str,
            metavar='',
            help="Maximum file size (e.g., 10MB, 1GB). Default: 100GB"
        )
        parser.add_argument(
            "--extensions", "-x",
            nargs="+",
            default=[],
            type=str,
            metavar='',
            help="File extensions (space separated) to include (e.g., .jpg .png)"
        )
        parser.add_argument(
            "--priority-dirs", '-p',
            nargs="+",
            default=[],
            type=str,
            metavar='',
            dest="priority_dirs",
            help="Directories (space separated) with files to prioritize when deleting duplicates"
        )

        parser.add_argument(
            "--excluded-dirs", '-e',
            nargs="+",
            default=[],
            type=str,
            metavar='',
            dest="excluded_dirs",
            help="Excluded/ignored directories (space separated)"
        )

        # Deduplication options
        parser.add_argument(
            "--mode",
            choices=DEDUP_MODE_CHOICES,
            default="normal",
            type=str,
            help=DEDUP_MODE_HELP_TEXT
        )

        parser.add_argument(
            "--boost",
            choices=BOOST_CHOICES,
            default="size",
            type=str,
            help=BOOST_HELP_TEXT
        )

        parser.add_argument(
            "--sort",
            choices=["shortest-path", "shortest-filename"],
            default="shortest-path",
            type=str,
            help="Sorting inside duplicate groups: \n"
                 "  'shortest-path' (files closer to root first), \n"
                 "  'shortest-filename' (shorter filenames first). Default: shortest-path\n"
        )

        # Actions
        parser.add_argument(
            "--keep-one",
            action="store_true",
            help="Keep one file per duplicate group and move the rest to trash. "
                 "Always shows preview before deletion for safety."
        )

        # Output options
        parser.add_argument(
            "--force",
            action="store_true",
            help="Skip confirmation prompt when used with --keep-one (for automation/scripts)"
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

        return parser.parse_args(args)

    def validate_args(self, args: argparse.Namespace) -> None:
        """Validate command-line arguments before execution."""
        if args.force and not args.keep_one:
            self.error_exit("--force can only be used with --keep-one")

        # Prevent interactive confirmation in non-TTY environments
        if args.keep_one and not args.force:
            if not sys.stdin.isatty() or not sys.stdout.isatty():
                self.error_exit(
                    "Cannot request interactive confirmation in non-interactive session.\n"
                    "Use --force flag to proceed without confirmation when piping output or running in scripts."
                )

        root_path = Path(args.input).resolve()
        if not root_path.exists():
            self.error_exit(f"Directory not found: {args.input}")
        if not root_path.is_dir():
            self.error_exit(f"Path is not a directory: {args.input}")

        # Validate size formats
        try:
            min_size = ConvertUtils.human_to_bytes(args.min_size)
            max_size = ConvertUtils.human_to_bytes(args.max_size)
            if min_size < 0:
                self.error_exit("Minimum size cannot be negative")
            if max_size < min_size:
                self.error_exit("Maximum size cannot be less than minimum size")
        except ValueError as e:
            self.error_exit(f"Invalid size format: {e}")

        # Validate Priority directories
        for fav_dir in args.priority_dirs:
            fav_path = Path(fav_dir).resolve()
            if not fav_path.exists():
                self.warning(f"Priority directory not found: {fav_dir}")
            elif not fav_path.is_dir():
                self.warning(f"Priority path is not a directory: {fav_dir}")

        # Validate excluded directories
        for excl_dir in args.excluded_dirs:
            excl_path = Path(excl_dir).resolve()
            if not excl_path.exists():
                self.warning(f"Excluded directory not found: {excl_dir}")
            elif not excl_path.is_dir():
                self.warning(f"Excluded path is not a directory: {excl_dir}")

        # Validate deduplication mode
        if args.mode not in DEDUP_MODE_ALIASES:
            self.error_exit(
                f"Invalid deduplication mode: '{args.mode}'.\n"
                f"Valid options: {', '.join({'fast', 'normal', 'full'})}"
            )

    def create_params(self, args: argparse.Namespace) -> DeduplicationParams:
        """Create DeduplicationParams from CLI arguments."""
        try:
            min_size_bytes = ConvertUtils.human_to_bytes(args.min_size)
            max_size_bytes = ConvertUtils.human_to_bytes(args.max_size)

            # Parse extensions
            extensions = []
            if args.extensions:
                for ext in args.extensions:
                    ext = ext.strip().lower()
                    if ext:
                        extensions.append(ext if ext.startswith(".") else f".{ext}")

            # Parse priority directories from CLI: comma-separated
            # convert it to internal favourite_dirs format for core engine
            favourite_dirs = []
            for item in args.priority_dirs:
                favourite_dirs.append(str(Path(item.strip()).resolve()))

            # Parse excluded directories: normalize paths for consistency with core engine
            excluded_dirs = []
            for item in args.excluded_dirs:
                excluded_dirs.append(str(Path(item.strip()).resolve()))

            # Map CLI sort option directly to core SortOrder enum values
            sort_order = SortOrder(args.sort)

            mode = DEDUP_MODE_ALIASES.get(args.mode, DeduplicationMode.NORMAL)
            boost_mode = BOOST_ALIASES.get(args.boost, BoostMode.SAME_SIZE)

            return DeduplicationParams(
                root_dir=str(Path(args.input).resolve()),
                min_size_bytes=min_size_bytes,
                max_size_bytes=max_size_bytes,
                extensions=extensions,
                favourite_dirs=favourite_dirs,
                excluded_dirs=excluded_dirs,
                sort_order=sort_order,
                boost=boost_mode,
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
        command = DeduplicationCommand()
        if self.verbose:
            mode_display = params.mode.value.capitalize()
            print(f"Finding duplicates (mode: {mode_display})...")

        try:
            groups, stats = command.execute(
                params,
                progress_callback=self.progress_callback if self.verbose else None,
                stopped_flag=self.stopped_flag
            )

            if self.verbose:
                sys.stderr.write("\n")
                print("\nDeduplication Statistics:")
                print(stats.print_summary())

            return groups
        except Exception as e:
            self.error_exit(f"Deduplication failed: {e}")

    def output_results(self, groups: List[DuplicateGroup]) -> None:
        """Output duplicate groups as plain text without additional sorting."""
        if self.quiet:
            return

        if not groups:
            print("No duplicate groups found.")
            return

        total_files = sum(len(g.files) for g in groups)
        print(f"\nFound {len(groups)} duplicate groups ({total_files} files)")

        for idx, group in enumerate(groups, 1):
            size_str = ConvertUtils.bytes_to_human(group.size)
            print(f"\n📁 Group {idx} | Size: {size_str} | Files: {len(group.files)}")

            # Use order from core (already sorted by favourite dirs + sort_order)
            for file in group.files:
                fav_marker = " ✅" if file.is_from_fav_dir else ""
                print(f"   {file.path} [{ConvertUtils.bytes_to_human(file.size)}]{fav_marker}")

    def execute_keep_one(self, groups: List[DuplicateGroup], params: DeduplicationParams, force: bool = False) -> None:
        """Keep one file per group, delete the rest. Always shows preview before deletion."""
        if not groups:
            if not self.quiet:
                print("No duplicate groups found.")
            return

        files_to_delete, _ = DuplicateService.keep_only_one_file_per_group(groups)

        if not files_to_delete:
            if not self.quiet:
                print("No files to delete (all groups already have only one file).")
            return

        # Calculate space savings
        space_saved = self.calculate_space_savings(groups, files_to_delete)
        space_saved_str = ConvertUtils.bytes_to_human(space_saved)

        # Always show deletion preview before action (safety first)
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
                print(f"          Reason: from favourite directory")
            else:
                # Show human-readable sort reason based on actual enum value
                sort_reason = "shortest path" if params.sort_order == SortOrder.SHORTEST_PATH else "shortest filename"
                print(f"          Reason: {sort_reason}")

            # Files that would be deleted
            for file in group.files[1:]:
                fav_marker = " ⭐" if file.is_from_fav_dir else ""
                print(f"   [DEL]  {file.path}")
                print(f"          Size: {ConvertUtils.bytes_to_human(file.size)}{fav_marker}")
            print()

        print("=" * 60)
        print(f"Summary: Keep 1 file per group ({preserved} files preserved, {len(files_to_delete)} files deleted)")
        print(f"Total space saved: {space_saved_str}")
        print()

        # Skip confirmation if --force is used
        if force:
            print("⚠️  WARNING: --force flag skips confirmation. Proceeding with deletion...")
        else:
            # Safety check: confirm we're still in interactive mode
            if not sys.stdin.isatty() or not sys.stdout.isatty():
                self.error_exit(
                    "Lost interactive terminal during operation. "
                    "Use --force to proceed in non-interactive environments."
                )

            # Ask for confirmation before actual deletion
            response = input(f"Are you sure you want to move {len(files_to_delete)} files to trash? [y/N]: ")
            if response.strip().lower() not in ("y", "yes"):
                print("Deletion cancelled by user.")
                return

        # Execute deletion with error resilience (continue on individual file errors)
        print(f"\nMoving {len(files_to_delete)} files to trash...")
        deleted_count = 0
        failed_files = []

        try:
            for i, path in enumerate(files_to_delete, 1):
                if self.verbose:
                    print(f"  [{i}/{len(files_to_delete)}] {os.path.basename(path)}")

                try:
                    FileService.move_to_trash(path)
                    deleted_count += 1
                except Exception as e:
                    failed_files.append((path, str(e)))
                    self.warning(f"Failed to delete {path}: {e}")
                    continue  # Continue with next file

            # Report results
            if failed_files:
                print(f"\n⚠️  Partial success: {deleted_count}/{len(files_to_delete)} files moved to trash.")
                print(f"Failed to delete {len(failed_files)} file(s):")
                for path, error in failed_files[:5]:  # Show first 5 errors
                    print(f"  • {os.path.basename(path)}: {error.split(':')[-1].strip()}")
                if len(failed_files) > 5:
                    print(f"  ...and {len(failed_files) - 5} more files")
            else:
                print(f"✅ Successfully moved {deleted_count} files to trash.")
                print(f"Total space saved: {space_saved_str}")

        except KeyboardInterrupt:
            print("\n⚠️  Operation cancelled by user (Ctrl+C)")
            sys.exit(130)
        except Exception as e:
            self.error_exit(f"Failed during deletion process: {e}")

    def warning(self, message: str) -> None:
        """Print a warning message to stderr."""
        if not self.quiet:
            print(f"⚠️  {message}", file=sys.stderr)

    @staticmethod
    def error_exit(message: str, code: int = 1) -> NoReturn:
        """Print error and exit."""
        print(f"❌ Error: {message}", file=sys.stderr)
        sys.exit(code)

    def run(self) -> None:
        """Main entry point with conditional output behavior."""
        args = self.parse_args()
        self.verbose = args.verbose
        self.quiet = args.quiet

        self.validate_args(args)
        params = self.create_params(args)

        if not self.quiet:
            print(f"Scanning directory: {params.root_dir}")

        groups = self.run_deduplication(params)

        # Conditional output based on flags
        if args.keep_one:
            # Always show preview before deletion (safety first)
            self.execute_keep_one(groups, params=params, force=args.force)
        else:
            # Show standard duplicate groups list
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