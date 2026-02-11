from typing import List, Tuple
from deduplicator.core.models import DuplicateGroup, File

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