"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License

utils/services.py
"""
import os
import sys
from typing import List, Tuple
from send2trash import send2trash
from PIL import Image
from core.models import DuplicateGroup, File

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

    # @staticmethod
    # def get_file_size(file_path: str) -> Optional[int]:
    #     """
    #     Get file size in bytes.
    #     Returns None if file doesn't exist or inaccessible.
    #     """
    #     try:
    #         return os.path.getsize(file_path)
    #     except (OSError, FileNotFoundError):
    #         return None

class DuplicateService:
    @staticmethod
    def remove_files_from_groups(groups: list[DuplicateGroup], file_paths: list[str]) -> list[DuplicateGroup]:
        """
        Removes the specified files from the list of duplicate groups.
        Returns the updated list of groups.
        """
        updated_groups = []
        for group in groups:
            filtered_files = [f for f in group.files if f.path not in file_paths]
            if len(filtered_files) >= 2:
                updated_groups.append(DuplicateGroup(size=group.size, files=filtered_files))
        return updated_groups

    @staticmethod
    def remove_files_from_file_list(files: list[File], file_paths: list[str]) -> list[File]:
        """
        Removes the specified files from the main file list.
        """
        return [f for f in files if f.path not in file_paths]

    @staticmethod
    def keep_only_one_file_per_group(groups: List[DuplicateGroup]) -> Tuple[List[str], List[DuplicateGroup]]:
        """
        Keeps one file per group and marks the rest for deletion.
        Returns:
            - List of file paths to be deleted
            - Updated list of duplicate groups
        """
        files_to_delete = []

        # Collect file paths that need to be deleted
        for group in groups:
            if len(group.files) > 1:
                for file in group.files[1:]:
                    files_to_delete.append(file.path)

        # Remove them from all groups
        updated_groups = DuplicateService.remove_files_from_groups(groups, files_to_delete)

        return files_to_delete, updated_groups