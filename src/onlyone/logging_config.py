#!/usr/bin/env python3
"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License
logging_config.py
Unified logging configuration for CLI, GUI, and test modes.
"""
import logging
import sys
import os
from pathlib import Path
from typing import Literal
from logging.handlers import RotatingFileHandler

# Constants
DEFAULT_LOG_LEVEL = logging.INFO
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)-25s - %(levelname)-8s - %(message)s"
CLI_LOG_FORMAT = "%(levelname)-8s | %(name)-25s | %(message)s"
LOG_DIR = Path.home() / ".onlyone" / "logs"
LOG_FILE = LOG_DIR / "app.log"
MAX_LOG_SIZE = 10 * 1024 * 1024
BACKUP_COUNT = 5  # Number of backup log files

# --- Filter to hide verbose deletion logs from console ---
class DeletionLogFilter(logging.Filter):
    """Filters out verbose deletion logs from console output to keep it clean."""
    def filter(self, record):
        # Block messages containing the specific deletion marker
        return "DELETED |" not in record.getMessage()
# -----------------------------------------------------------

# --- Test mode detection (STRICT - no sys.argv checks) ---
def _is_test_mode() -> bool:
    """
    Detect if running in test mode.
    Checks for:
    - ONLYONE_TEST_MODE environment variable
    - pytest in sys.modules
    - unittest in sys.modules
    """
    if os.environ.get("ONLYONE_TEST_MODE", "").lower() in ("1", "true", "yes"):
        return True
    if "pytest" in sys.modules:
        return True
    if "unittest" in sys.modules:
        return True
    return False
# -----------------------------------------------------------

def ensure_log_directory() -> Path:
    """Create the log directory if it does not exist."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR

def setup_logging(
    mode: Literal["cli", "gui", "library", "test"] = "library",
    level: int = DEFAULT_LOG_LEVEL,
    verbose: bool = False,
    disable_file_logging: bool = False,
) -> logging.Logger:
    """
    Configure logging for the specified operation mode.
    Args:
        mode: Operation mode:
            - "cli": Output to stdout (console) + file
            - "gui": Output to file only
            - "library": Output to file only (for library usage)
            - "test": Output to stdout only, no file logging
        level: Logging level (logging.INFO, logging.DEBUG, etc.)
        verbose: If True, set level to DEBUG regardless of mode
        disable_file_logging: If True, skip file handler creation (useful for tests)
    Returns:
        Configured logger for the application
    """
    # Override level if verbose mode is enabled
    if verbose:
        level = logging.DEBUG

    # Auto-detect test mode (strict check - no sys.argv)
    test_mode = _is_test_mode() or mode == "test" or disable_file_logging

    # Create log directory (skip in test mode)
    if not test_mode:
        ensure_log_directory()

    # Get root application logger
    logger = logging.getLogger("onlyone")
    logger.setLevel(level)

    # Clear existing handlers (to avoid duplication)
    if logger.handlers:
        logger.handlers.clear()

    # Create formatters
    file_formatter = logging.Formatter(DEFAULT_LOG_FORMAT)
    console_formatter = logging.Formatter(CLI_LOG_FORMAT)

    # === File Handler (skip in test mode) ===
    if not test_mode:
        try:
            file_handler = RotatingFileHandler(
                LOG_FILE,
                maxBytes=MAX_LOG_SIZE,
                backupCount=BACKUP_COUNT,
                encoding="utf-8",
                delay=True  # Delay file creation until first write
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        except (PermissionError, OSError) as e:
            # If log file cannot be created, warn but do not crash
            print(f"Warning: Could not create log file at {LOG_FILE}: {e}", file=sys.stderr)

    # === Console Handler (CLI and test modes) ===
    if mode == "cli" or test_mode:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(console_formatter)
        # Apply filter to console handler (hide deletion logs from console)
        # Only apply in CLI mode (tests can show everything for debugging)
        if mode == "cli":
            console_handler.addFilter(DeletionLogFilter())
        logger.addHandler(console_handler)

    # === Exception Handling ===
    # For GUI and library modes, log exceptions to file
    if mode in ("gui", "library") and not test_mode:
        logging.captureWarnings(True)
        logger.info(f"Logging initialized | Mode: {mode} | Level: {logging.getLevelName(level)}")

    # For test mode, log initialization to console for debugging
    if test_mode:
        logger.debug(f"Logging initialized | Mode: TEST | File logging: DISABLED")

    return logger

def get_logger(name: str = "onlyone") -> logging.Logger:
    """
    Get a logger with the specified name.
    Args:
        name: Logger name (default "onlyone")
    Returns:
        Logger instance
    """
    return logging.getLogger(name)

def cleanup_logging() -> None:
    """
    Clean up all logging handlers.
    Call this upon application exit to release file descriptors.
    """
    logger = logging.getLogger("onlyone")
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
    logger.handlers.clear()