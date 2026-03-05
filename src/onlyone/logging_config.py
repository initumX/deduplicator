"""
Copyright (c) 202 initumX (initum.x@gmail.com)
Licensed under the MIT License
logging_config.py
Unified logging configuration for CLI, GUI, and test modes.
ALL logging goes to FILE ONLY. Console is kept clean for progress bar and summary.
"""
import logging
import sys
import os
from pathlib import Path
from typing import Literal, Optional
from logging.handlers import RotatingFileHandler

# Constants
DEFAULT_LOG_LEVEL = logging.INFO
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)-25s - %(levelname)-8s - %(message)s"
LOG_DIR = Path.home() / ".onlyone" / "logs"
LOG_FILE = LOG_DIR / "app.log"
MAX_LOG_SIZE = 10 * 1024 * 1024
BACKUP_COUNT = 5

def _is_test_mode() -> bool:
    """Detect if running in test mode."""
    if os.environ.get("ONLYONE_TEST_MODE", "").lower() in ("1", "true", "yes"):
        return True
    if "pytest" in sys.modules:
        return True
    if "unittest" in sys.modules:
        return True
    return False

def ensure_log_directory() -> Path:
    """Create the log directory if it does not exist."""
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    except (FileExistsError, NotADirectoryError) as e:
        if not LOG_DIR.is_dir():
            raise FileExistsError(f"Log directory path exists as a file: {LOG_DIR}") from e
    return LOG_DIR

def setup_logging(
    mode: Literal["cli", "gui", "library", "test"] = "library",
    level: int = DEFAULT_LOG_LEVEL,
    verbose: bool = False,
    disable_file_logging: bool = False,
    force_test_mode: Optional[bool] = None,
) -> logging.Logger:
    """
    Configure logging for the specified operation mode.

    IMPORTANT: Console handler is DISABLED for CLI mode to keep output clean.
    All logging goes to FILE ONLY.

    Args:
        mode: Operation mode ("cli", "gui", "library", "test")
        level: Logging level (logging.INFO, logging.DEBUG, etc.)
        verbose: If True, set level to DEBUG (all messages to file)
        disable_file_logging: If True, skip file handler creation
        force_test_mode: Explicitly override test mode detection

    Returns:
        Configured logger for the application
    """
    # Override level if verbose mode is enabled
    if verbose:
        level = logging.DEBUG

    # Determine test mode
    if force_test_mode is not None:
        test_mode = force_test_mode
    else:
        test_mode = _is_test_mode() or mode == "test"

    # In test mode, force DEBUG level
    if test_mode:
        level = logging.DEBUG

    # Create log directory (skip in test mode or when file logging disabled)
    if not test_mode and not disable_file_logging:
        try:
            ensure_log_directory()
        except (FileExistsError, PermissionError, OSError) as e:
            print(f"Warning: Could not create log directory at {LOG_DIR}: {e}", file=sys.stderr)

    # Get root application logger
    logger = logging.getLogger("onlyone")
    logger.setLevel(level)

    # Clear existing handlers (to avoid duplication)
    if logger.handlers:
        logger.handlers.clear()

    # Create formatter
    file_formatter = logging.Formatter(DEFAULT_LOG_FORMAT)

    # === File Handler (ALL modes except test) ===
    if not test_mode and not disable_file_logging:
        try:
            file_handler = RotatingFileHandler(
                LOG_FILE,
                maxBytes=MAX_LOG_SIZE,
                backupCount=BACKUP_COUNT,
                encoding="utf-8",
                delay=True
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        except (PermissionError, OSError, FileExistsError) as e:
            print(f"Warning: Could not create log file at {LOG_FILE}: {e}", file=sys.stderr)

    # === Console Handler: DISABLED for CLI mode ===
    # Console output is handled directly by CLI (progress bar + summary)
    # This prevents logging messages from interfering with progress bar
    # Only test mode gets console output for debugging
    if mode == "test":
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(file_formatter)
        logger.addHandler(console_handler)

    # === Log Initialization Message (file only) ===
    if mode in ("gui", "library", "cli") and not test_mode and not disable_file_logging:
        logging.captureWarnings(True)
        logger.info(f"Logging initialized | Mode: {mode} | Level: {logging.getLevelName(level)} | Verbose: {verbose}")

    if test_mode or mode == "test":
        logger.debug(f"Logging initialized | Mode: TEST | File logging: DISABLED")

    return logger

def get_logger(name: str = "onlyone") -> logging.Logger:
    """Get a logger with the specified name."""
    return logging.getLogger(name)

def cleanup_logging() -> None:
    """Clean up all logging handlers."""
    logger = logging.getLogger("onlyone")
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
    logger.handlers.clear()