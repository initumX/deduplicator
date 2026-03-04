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
from onlyone.logging_config import setup_logging, cleanup_logging, LOG_FILE

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
    print(" Missing required dependencies:", file=sys.stderr)
    print(f"   pip install {' '.join(_MISSING_DEPS)}", file=sys.stderr)
    print("\nOr install all dependencies:", file=sys.stderr)
    print("   pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

# === NORMAL IMPORTS (after validation) ===
from onlyone.core.models import DeduplicationMode, DeduplicationParams, DuplicateGroup, SortOrder, BoostMode
from onlyone.commands import DeduplicationCommand
from onlyone.services.file_service import FileService
from onlyone.services.duplicate_service import DuplicateService
from onlyone.core.measurer import bytes_to_human
from onlyone.aliases import (
    BOOST_ALIASES, BOOST_CHOICES, BOOST_HELP_TEXT,
    DEDUP_MODE_ALIASES, DEDUP_MODE_CHOICES, DEDUP_MODE_HELP_TEXT,
    EPILOG_TEXT
)
from onlyone.progress_bar import ProgressBar
from onlyone import __version__
from onlyone.reporter import (
    format_groups_output,
    format_deletion_preview,
    format_deletion_result
)

class CLIApplication:
    """Main CLI application controller."""

    def __init__(self):
        self.start_time: float = time.time()
        self.show_stats: bool = False
        self.logger = logging.getLogger("onlyone.cli")
        self._progress: Optional[ProgressBar] = None
        self._current_stage: str = ""
        self._args_ascii: bool = False

        # Fix encoding for Windows/Linux consoles to prevent UnicodeEncodeError
        # Use surrogateescape to handle invalid UTF-8 bytes in file paths (Linux)
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='surrogateescape')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='surrogateescape')
        if hasattr(sys.stdin, 'reconfigure'):
            sys.stdin.reconfigure(encoding='utf-8', errors='replace')

    @staticmethod
    def parse_args(args=None) -> argparse.Namespace:
        """Parse and validate command-line arguments."""
        parser = argparse.ArgumentParser(
            description="OnlyOne — Fast duplicate file finder with safe deletion",
            formatter_class=argparse.RawTextHelpFormatter,
            epilog=EPILOG_TEXT
        )

        parser.add_argument(
            '--version', '-v',
            action = 'version',
            version = f'OnlyOne {__version__}'
        )

        # Required arguments
        parser.add_argument(
            "--input", "-i",
            required=True,
            type=str,
            nargs="+",
            metavar="DIR",
            help="Input directory (or directories) to scan for duplicates"
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
            help="Files from here are prioritized to keep (go first, as 'original') in each group.\n"
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
            "--dry-run",
            action="store_true",
            help="Show which files would be deleted without actually deleting them"
        )

        parser.add_argument(
            "--stats",
            action="store_true",
            help="Show deduplication statistics (files scanned, hash operations, etc.)"
        )

        parser.add_argument(
            "--ascii",
            action="store_true",
            help="Use ASCII characters instead of emojis (for old terminals)"
        )

        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Enable debug logging (shows skipped files, hash errors, etc.)"
        )

        return parser.parse_args(args)

    def validate_args(self, args: argparse.Namespace) -> None:
        """Validate command-line arguments before execution."""
        if args.force and not args.keep_one:
            self.error_exit("--force can only be used with --keep-one")

        if (args.dry_run and args.keep_one) or (args.dry_run and args.force):
            self.error_exit("--dry-run and cannot be used together with --keep-one or --force")

        # Prevent interactive confirmation in non-TTY environments
        if args.keep_one and not args.force:
            if not sys.stdin.isatty() or not sys.stdout.isatty():
                self.error_exit(
                    "Cannot request interactive confirmation in non-interactive session.\n"
                    "Use --force flag to proceed without confirmation when piping output or running in scripts."
                )

        # Validate all input directories
        for i, input_path in enumerate(args.input):
            root_path = Path(input_path).resolve()
            if not root_path.exists():
                self.error_exit(f"Directory not found: {input_path}")
            if not root_path.is_dir():
                self.error_exit(f"Path is not a directory: {input_path}")

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
                f"Valid options: {', '.join({'normal', 'full'})}"
            )

    def create_params(self, args: argparse.Namespace) -> DeduplicationParams:
        """Create DeduplicationParams from CLI arguments."""
        try:
            extensions = args.extensions

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

            # Normalize all root directories
            root_dirs = [str(Path(p).resolve()) for p in args.input]

            return DeduplicationParams.from_human_readable(
                root_dirs=root_dirs,
                min_size_str=args.min_size,
                max_size_str=args.max_size,
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
        if stage  != self._current_stage:
            self._current_stage = stage
            if self._progress:
                self._progress.finish()  # Close previous stage cleanly

            self._progress = ProgressBar(
                prefix=f"[{stage}]",
                total=total,  # None = indeterminate (scanning phase)
                ascii_only=self._args_ascii,
                min_interval=0.1
            )
        if self._progress:
            self._progress.update(current)

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

        try:
            groups, stats = command.execute(
                params,
                progress_callback=self.progress_callback,
                stopped_flag=self.stopped_flag
            )

            if self.show_stats:
                print()
                print(stats.print_summary())

            return groups
        except Exception as e:
            if self._progress:
                self._progress.finish()
                self._progress = None
            self.error_exit(f"Deduplication failed: {e}")

    @staticmethod
    def output_results(groups: List[DuplicateGroup], ascii_only: bool = False) -> None:
        """Output duplicate groups as plain text."""
        if not groups:
            print("No duplicate groups found.")
            return

        output = format_groups_output(groups, show_fav_markers=True, ascii_only=ascii_only)
        print(output)

    def execute_keep_one(
            self,
            groups: List[DuplicateGroup],
            force: bool = False,
            ascii_only: bool = False
    ) -> None:
        """Keep one file per group, delete the rest. Always shows preview before deletion."""
        if not groups:
            print("No duplicate groups found.")
            return

        files_to_delete, _ = DuplicateService.keep_only_one_file_per_group(groups)

        if not files_to_delete:
            print("No files to delete (all groups already have only one file).")
            return

        # Calculate space savings
        space_saved = self.calculate_space_savings(groups, files_to_delete)

        # Preview via reporter (formatting only)
        preview = format_deletion_preview(groups, files_to_delete, space_saved, ascii_only=ascii_only)
        print(preview)

        # Confirmation (orchestration - stays in CLI)
        if force:
            self.logger.warning("--force flag skips confirmation. Proceeding with deletion...")
        else:
            if not sys.stdin.isatty() or not sys.stdout.isatty():
                self.error_exit(
                    "Lost interactive terminal during operation. "
                    "Use --force to proceed in non-interactive environments."
                )
            response = input(f"Are you sure you want to move {len(files_to_delete)} files to trash? [y/N]: ")
            if response.strip().lower() not in ("y", "yes"):
                print("Deletion cancelled by user.")
                return

        # Execute deletion
        print(f"\nMoving {len(files_to_delete)} files to trash...")

        deleted_count = 0
        failed_files = []

        # Create a map of paths to sizes for logging purposes
        file_sizes = {f.path: f.size for g in groups for f in g.files}

        # Initialize progress bar for deletion
        delete_bar = None
        if len(files_to_delete) > 0:
            delete_bar = ProgressBar(
                prefix='  [Deleting]',
                total=len(files_to_delete),
                ascii_only=ascii_only,
                min_interval=0.1
            )

        try:
            for i, path in enumerate(files_to_delete, 1):
                if delete_bar:
                    delete_bar.update(i)

                try:
                    FileService.move_to_trash(path)
                    deleted_count += 1

                    # Log successful deletion (matching GUI behavior)
                    # NOTE: This log goes to FILE ONLY due to DeletionLogFilter in logging_config
                    size = file_sizes.get(path, 0)
                    self.logger.info(f"DELETED | {path} | {bytes_to_human(size)}")

                except Exception as e:
                    failed_files.append((path, str(e)))
                    self.logger.warning(f"Error deleting file {path}: {e}")
                    continue  # Continue with next file

            if delete_bar:
                delete_bar.finish()

            result = format_deletion_result(
                deleted_count, len(files_to_delete), space_saved, failed_files, ascii_only=ascii_only
            )
            print(result)
            print(f"\nℹ️  Detailed deletion log saved to: {LOG_FILE}")

        except KeyboardInterrupt:
            if delete_bar:
                delete_bar.finish()  # Clean finish on interrupt
            print("\nOperation cancelled by user (Ctrl+C)")
            sys.exit(130)
        except Exception as e:
            if delete_bar:
                delete_bar.finish()
            self.error_exit(f"Failed during deletion process: {e}")

    def show_dry_run_preview(self, groups: List[DuplicateGroup]) -> None:
        """Show which files would be deleted without actually deleting them."""
        if not groups:
            print("No duplicate groups found.")
            return

        files_to_delete, _ = DuplicateService.keep_only_one_file_per_group(groups)

        if not files_to_delete:
            print("No files to delete (all groups already have only one file).")
            return

        # Calculate space savings
        space_saved = self.calculate_space_savings(groups, files_to_delete)

        # Show preview header
        print()
        print("DRY RUN — No files will be deleted")
        print("=" * 60)

        # Use the same preview formatter as execute_keep_one
        preview = format_deletion_preview(groups, files_to_delete, space_saved, ascii_only=self._args_ascii)
        print(preview)

        # Final notice
        print("ℹ️  This was a dry run. Use --keep-one to actually delete files.")

    def warning(self, message: str) -> None:
        self.logger.warning(message)

    def error_exit(self, message: str, code: int = 1) -> NoReturn:
        self.logger.critical(message)
        raise SystemExit(code)

    def run(self) -> None:
        """Main entry point with conditional output behavior."""
        args = self.parse_args()

        # === UNIFIED LOGGING SETUP ===
        log_level = logging.DEBUG if args.verbose else logging.INFO
        setup_logging(
            mode="cli",
            level=log_level,
            verbose=args.verbose
        )

        self.show_stats = args.stats
        self._args_ascii = args.ascii  # Store for progress_callback
        self.validate_args(args)
        params = self.create_params(args)

        groups = self.run_deduplication(params)

        # Conditional output based on flags
        if args.dry_run:
            self.show_dry_run_preview(groups)
        elif args.keep_one:
            # Always show preview before deletion (safety first)
            self.execute_keep_one(groups, force=args.force, ascii_only=args.ascii)
        else:
            # Show standard duplicate groups list
            self.output_results(groups, ascii_only=args.ascii)

        # Show completion time
        elapsed = time.time() - self.start_time
        if self.show_stats:
            print(f"\n✅ Completed in {elapsed:.2f} seconds")


def main() -> None:
    """Application entry point."""
    app = CLIApplication()
    try:
        app.run()
    except KeyboardInterrupt:
        print("\n️  Operation cancelled by user (Ctrl+C)")
        sys.exit(130)
    except Exception as e:
        if os.environ.get("DEBUG"):
            raise
        print(f" Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        cleanup_logging()


if __name__ == "__main__":
    main()