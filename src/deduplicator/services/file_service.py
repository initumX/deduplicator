# src/file_deduplicator/services/file_service.py
import os
import sys
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
    @staticmethod
    def open_file(file_path: str):
        """Open file with system default application (works in CLI and GUI)."""
        try:
            if sys.platform == 'win32':
                os.startfile(file_path)
            elif sys.platform == 'darwin':
                os.system(f'open "{file_path}"')
            else:
                os.system(f'xdg-open "{file_path}"')
        except Exception as e:
            raise RuntimeError(f"Failed to open file: {e}")

    @staticmethod
    def reveal_in_explorer(file_path: str):
        """Reveal file in system file manager (works in CLI and GUI)."""
        folder = os.path.dirname(file_path)
        try:
            if sys.platform == 'win32':
                os.system(f'explorer /select,"{file_path}"')
            elif sys.platform == 'darwin':
                os.system(f'open -R "{file_path}"')
            else:
                os.system(f'xdg-open "{folder}"')
        except Exception as e:
            raise RuntimeError(f"Failed to reveal file: {e}")

    @staticmethod
    def move_to_trash(file_path: str):
        """Move file to system trash (safe deletion). Requires send2trash."""
        try:
            send2trash(file_path)
        except Exception as e:
            raise RuntimeError(f"Failed to move to trash: {e}")

    @classmethod
    def move_multiple_to_trash(cls, file_paths: List[str]):
        """Move multiple files to trash with error aggregation."""
        errors = []
        for path in file_paths:
            try:
                cls.move_to_trash(path)
            except Exception as e:
                errors.append((path, str(e)))
        if errors:
            raise RuntimeError(f"Failed to delete {len(errors)} file(s): {errors}")

    @staticmethod
    def is_valid_image(file_path: str) -> bool:
        """
        Check if file is a valid image.
        With Pillow installed: full validation via PIL.
        Without Pillow: basic extension check only.
        """
        ext = os.path.splitext(file_path)[1].lower()
        valid_exts = [".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"]

        if ext not in valid_exts:
            return False

        # Full validation only if Pillow is available
        if HAS_PIL and Image is not None:
            try:
                with Image.open(file_path) as img:
                    img.verify()
                return True
            except Exception:
                return False
        else:
            # Without Pillow: trust the extension
            return True