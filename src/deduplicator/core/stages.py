from typing import List, Dict, Optional, Callable
from deduplicator.core.models import File, DuplicateGroup
from deduplicator.core.grouper import FileGrouperImpl
from deduplicator.core.interfaces import SizeStage, PartialHashStage

#=============================
# Base Class and Config
#=============================
class HashStageBase:
    """
    Base class for all stages that use partial hashes.
    Handles assigning chunk size based on file size.
    """
    @staticmethod
    def assign_chunk_sizes(files: List[File]) -> None:
        """
        Assigns appropriate chunk size to each file before hashing.
        """
        for file in files:
            file.chunk_size = DeduplicationConfig.get_chunk_size(file.size)


class DeduplicationConfig:
    EARLY_CONFIRMATION_SIZE_LIMIT = 128 * 1024  # Files ≤ this size can be confirmed after front hash

    @staticmethod
    def get_chunk_size(file_size: int) -> int:
        limit = DeduplicationConfig.EARLY_CONFIRMATION_SIZE_LIMIT
        if file_size <= limit:
            return file_size
        elif file_size <= limit * 3:
            return limit
        elif file_size <= 10 * 1024 * 1024:
            return 64 * 1024
        elif file_size <= 30 * 1024 * 1024:
            return 128 * 1024
        elif file_size <= 60 * 1024 * 1024:
            return 256 * 1024
        elif file_size <= 120 * 1024 * 1024:
            return 512 * 1024
        elif file_size <= 360 * 1024 * 1024:
            return 1 * 1024 * 1024
        else:
            return 2 * 1024 * 1024


# =============================
# Partial Hashing Base Class
# =============================
class PartialHashStageBase(HashStageBase, PartialHashStage):
    """
    Abstract base class for stages that perform partial hashing.
    Encapsulates common logic for front/middle/end hash stages.
    """

    def __init__(self, grouper: FileGrouperImpl):
        self.grouper = grouper

    def get_threshold(self) -> int:
        """
        Returns the file size threshold for early confirmation.
        Must be implemented by subclasses.
        """
        raise NotImplementedError

    def get_stage_name(self) -> str:
        """
        Returns the name of the current stage.
        Used for statistics and logging.
        """
        raise NotImplementedError

    def _group_files(self, files: List[File]) -> Dict[bytes, List[File]]:
        """
        Groups files by their hash values.

        This method must be implemented by subclasses to define how files are grouped,
        typically using a specific hash (e.g., front, middle, or end hash).

        Args:
            files (List[File]): A list of files to group.

        Returns:
            Dict[bytes, List[File]]: A dictionary mapping hash values to lists of files
                                     that match that hash.
        """
        raise NotImplementedError

    def process(
        self,
        groups: List[DuplicateGroup],
        confirmed_duplicates: List[DuplicateGroup],
        stopped_flag: Optional[Callable[[], bool]] = None,
        progress_callback: Optional[Callable[[str, int, object], None]] = None
    ) -> List[DuplicateGroup]:
        """
        Processes duplicate groups through this hash stage.
        Groups are split into small/large files based on threshold.
        Small files may be confirmed as duplicates, large files continue processing.
        """
        if stopped_flag and stopped_flag():
            return []

        new_potential_groups = []
        total_files = sum(len(group.files) for group in groups)
        processed_files = 0

        for group in groups:
            if stopped_flag and stopped_flag():
                return []

            # Assign chunk sizes before hashing
            HashStageBase.assign_chunk_sizes(group.files)

            hash_groups = self._group_files(group.files)
            threshold = self.get_threshold()

            for hkey, files_in_group in hash_groups.items():

                small_files = [f for f in files_in_group if f.size <= threshold]
                large_files = [f for f in files_in_group if f.size > threshold]

                if small_files:
                    confirmed_duplicates.append(DuplicateGroup(size=group.size, files=small_files))

                if large_files:
                    new_potential_groups.append(DuplicateGroup(size=group.size, files=large_files))

            processed_files += len(group.files)
            if progress_callback:
                progress_callback(self.get_stage_name(), processed_files, total_files)

        return new_potential_groups


# =============================
# Individual Stages
# =============================
class SizeStageImpl(SizeStage):
    def __init__(self, grouper: FileGrouperImpl):
        self.grouper = grouper

    def process(
            self,
            files: List[File],
            stopped_flag: Optional[Callable[[], bool]] = None,
            progress_callback: Optional[Callable[[str, int, object], None]] = None
    ) -> List[DuplicateGroup]:
        """
        Group by file size.
        Returns list of DuplicateGroups with 2+ files of same size.
        """
        if stopped_flag and stopped_flag():
            return []
        size_groups = self.grouper.group_by_size(files)

        if progress_callback:
            total_files = len(files)
            progress_callback("Size grouping", total_files, total_files)  # Fake instant progress

        return [DuplicateGroup(size=size, files=files_list) for size, files_list in size_groups.items()]


class FrontHashStage(PartialHashStageBase):
    def get_threshold(self) -> int:
        return DeduplicationConfig.EARLY_CONFIRMATION_SIZE_LIMIT

    def get_stage_name(self) -> str:
        return "Front-chunk Hash"

    def _group_files(self, files: List[File]) -> Dict[bytes, List[File]]:
        return self.grouper.group_by_front_hash(files)


class MiddleHashStage(PartialHashStageBase):
    def get_threshold(self) -> int:
        return int(DeduplicationConfig.EARLY_CONFIRMATION_SIZE_LIMIT * 2)

    def get_stage_name(self) -> str:
        return "Middle-chunk Hash"

    def _group_files(self, files: List[File]) -> Dict[bytes, List[File]]:
        return self.grouper.group_by_middle_hash(files)


class EndHashStage(PartialHashStageBase):
    def get_threshold(self) -> int:
        return int(DeduplicationConfig.EARLY_CONFIRMATION_SIZE_LIMIT * 3)

    def get_stage_name(self) -> str:
        return "End-chunk Hash"

    def _group_files(self, files: List[File]) -> Dict[bytes, List[File]]:
        return self.grouper.group_by_end_hash(files)


class FullHashStage:
    def __init__(self, grouper: FileGrouperImpl):
        self.grouper = grouper

    def process(
            self,
            groups: List[DuplicateGroup],
            confirmed_duplicates: List[DuplicateGroup],
            stopped_flag: Optional[Callable[[], bool]] = None,
            progress_callback: Optional[Callable[[str, int, object], None]] = None
    ) -> List[DuplicateGroup]:
        if stopped_flag and stopped_flag():
            return []

        total_files = sum(len(g.files) for g in groups)
        processed_files = 0

        for group in groups:
            if stopped_flag and stopped_flag():
                return []

            hash_groups = self.grouper.group_by_full_hash(group.files)
            for hkey, files in hash_groups.items():
                if stopped_flag and stopped_flag():
                    return []
                if len(files) >= 2:
                    confirmed_duplicates.append(DuplicateGroup(size=group.size, files=files))

            processed_files += len(group.files)
            if progress_callback:
                progress_callback("Full Hash", processed_files, total_files)

        return []
