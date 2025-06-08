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
        Removes files with the specified paths from all duplicate groups.

        Files that match any of the provided file paths are removed from each group.
        Groups that contain fewer than 2 files after removal are discarded.

        Args:
            groups (list[DuplicateGroup]): List of duplicate groups to update.
            file_paths (list[str]): List of file paths to remove.

        Returns:
            list[DuplicateGroup]: Updated list of duplicate groups.
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
        Removes files matching the given file paths from the main file list.

        Args:
            files (list[File]): The full list of files found during scanning.
            file_paths (list[str]): Paths of files to be removed.

        Returns:
            list[File]: A new list of files excluding those marked for deletion.
        """
        return [f for f in files if f.path not in file_paths]

    @staticmethod
    def update_favorite_status(files: List[File], favorite_dirs: List[str]):
        """
        Updates the `is_from_fav_dir` flag on all files based on the current favorite directories.

        This method checks whether each file's path starts with one of the favorite directory paths,
        and sets its `is_from_fav_dir` attribute accordingly.

        Args:
            files (List[File]): List of files to update.
            favorite_dirs (List[str]): List of favorite directory paths.
        """
        if not files:
            return
        for file in files:
            file.set_favorite_status(favorite_dirs)

    @staticmethod
    def delete_files(
            file_paths: List[str],
            files: List[File],
            duplicate_groups: List[DuplicateGroup]
    ) -> Tuple[List[File], List[DuplicateGroup]]:
        """
        Simulates the deletion of files by removing them from both the main file list
        and all associated duplicate groups.

        This method does not perform actual deletion or file operations. It only updates
        internal data structures to reflect what would happen after deletion.

        Args:
            file_paths (List[str]): Paths of files to be deleted.
            files (List[File]): Current list of all scanned files.
            duplicate_groups (List[DuplicateGroup]): Current list of duplicate groups.

        Returns:
            Tuple[List[File], List[DuplicateGroup]]: Updated file list and duplicate groups.
        """
        updated_files = DuplicateService.remove_files_from_file_list(files, file_paths)
        updated_groups = DuplicateService.remove_files_from_groups(duplicate_groups, file_paths)
        return updated_files, updated_groups

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