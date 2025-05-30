# utils/services.py
import os
import sys
from typing import List, Optional
from send2trash import send2trash
from PIL import Image


class FileService:
    @staticmethod
    def open_file(file_path: str):
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
        folder = os.path.dirname(file_path)
        filename = os.path.basename(file_path)
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
        try:
            send2trash(file_path)
        except Exception as e:
            raise RuntimeError(f"Failed to move to trash: {e}")

    @classmethod
    def move_multiple_to_trash(cls, file_paths: List[str]):
        for path in file_paths:
            cls.move_to_trash(path)

    @staticmethod
    def is_valid_image(file_path: str) -> bool:
        try:
            ext = os.path.splitext(file_path)[1].lower()
            if ext not in [".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"]:
                return False

            with Image.open(file_path) as img:
                img.verify()  # Verify that it's a real image
            return True
        except Exception:
            return False

    @staticmethod
    def get_file_size(file_path: str) -> Optional[int]:
        """
        Get file size in bytes.
        Returns None if file doesn't exist or inaccessible.
        """
        try:
            return os.path.getsize(file_path)
        except (OSError, FileNotFoundError):
            return None
