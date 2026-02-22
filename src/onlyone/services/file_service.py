"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License

services/file_service.py
Cross-platform file operations for frozen PyInstaller applications.
Provides universal methods to open, reveal, and trash files on Windows, macOS, and Linux.
"""
import os
import sys
import subprocess
from pathlib import Path
from typing import List
from send2trash import send2trash

# Optional import Pillow
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    Image = None


class FileService:
    """
    Cross-platform file operations for frozen applications.
    Uses universal system tools with proper error handling.
    """

    @staticmethod
    def open_file(file_path: str):
        """Opens a file with the system default application."""
        path = Path(file_path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        try:
            if sys.platform == 'win32':
                os.startfile(str(path))
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', str(path)])
            else:
                FileService._open_linux(path)
        except Exception as e:
            # Переводим любую ошибку в понятное исключение
            raise RuntimeError(f"Failed to open file: {e}") from e

    @staticmethod
    def _open_linux(path: Path):
        """Linux: Tries gio, falls back to xdg-open."""
        env = FileService._get_clean_env()

        # Try gio first
        try:
            subprocess.run(['gio', 'open', str(path)], env=env, timeout=5)
            return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass  # Fallback to xdg-open

        # Fallback to xdg-open
        try:
            subprocess.run(['xdg-open', str(path)], env=env, timeout=5)
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            raise RuntimeError(f"Cannot open file: no suitable application found") from e

    @staticmethod
    def reveal_in_explorer(file_path: str):
        """Reveals a file in the system file manager."""
        path = Path(file_path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        try:
            if sys.platform == 'win32':
                subprocess.Popen(['explorer', '/select,', str(path)])
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', '-R', str(path)])
            else:
                FileService._reveal_linux(path)
        except Exception as e:
            raise RuntimeError(f"Failed to reveal file: {e}") from e

    @staticmethod
    def _reveal_linux(path: Path):
        """Linux: Opens the containing folder."""
        env = FileService._get_clean_env()
        folder = str(path.parent)

        # Try gio first
        try:
            subprocess.run(['gio', 'open', folder], env=env, timeout=5)
            return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Fallback to xdg-open
        try:
            subprocess.run(['xdg-open', folder], env=env, timeout=5)
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            raise RuntimeError(f"Cannot reveal file: no file manager found") from e

    @staticmethod
    def move_to_trash(file_path: str):
        """Moves a file to the system trash."""
        path = Path(file_path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        try:
            send2trash(str(path))
        except Exception as e:
            raise RuntimeError(f"Failed to move to trash: {e}") from e

    @classmethod
    def move_multiple_to_trash(cls, file_paths: List[str]):
        """Moves multiple files to trash with error aggregation."""
        errors = []
        for path in file_paths:
            try:
                cls.move_to_trash(path)
            except Exception as e:
                errors.append((path, str(e)))

        if errors:
            error_summary = "\n".join(
                f"  • {Path(p).name}: {msg.split(':')[-1].strip()}"
                for p, msg in errors[:5]
            )
            if len(errors) > 5:
                error_summary += f"\n  • ...and {len(errors) - 5} more files"
            raise RuntimeError(
                f"Failed to move {len(errors)} file(s) to trash:\n{error_summary}"
            )

    @staticmethod
    def _get_clean_env():
        """
        Returns a clean environment for spawning system applications.
        Removes PyInstaller's temporary library paths to prevent Qt conflicts.
        """
        env = os.environ.copy()

        if getattr(sys, 'frozen', False) and sys.platform.startswith('linux'):
            ld_path = env.get('LD_LIBRARY_PATH', '')
            if ld_path:
                paths = ld_path.split(':')
                clean_paths = [
                    p for p in paths
                    if not p.startswith('/tmp/_MEI')
                       and not p.startswith(os.path.dirname(sys.executable))
                ]
                env['LD_LIBRARY_PATH'] = ':'.join(clean_paths)

        env.setdefault('DISPLAY', ':0')

        return env

    @staticmethod
    def is_valid_image(file_path: str) -> bool:
        """Checks if the file is a valid image."""
        ext = Path(file_path).suffix.lower()
        valid_exts = [".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"]

        if ext not in valid_exts:
            return False

        if HAS_PIL and Image is not None:
            try:
                with Image.open(file_path) as img:
                    img.verify()
                return True
            except (OSError, IOError):
                # File system errors
                return False
            except (AttributeError, TypeError, ValueError):
                # PIL validation errors (corrupt/invalid image)
                return False
        else:
            return True