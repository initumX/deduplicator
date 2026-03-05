#!/usr/bin/env python3
"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License

core/stages.py
Deduplication pipeline stages implementation for OnlyOne's multi-stage duplicate detection engine.
"""
from typing import List, Dict, Optional, Callable
from onlyone.core.models import File, DuplicateGroup, BoostMode
from onlyone.core.grouper import FileGrouper

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
        """Assigns appropriate chunk size to each file before hashing."""
        for file in files:
            file.chunk_size = DeduplicationConfig.get_chunk_size(file.size)


class DeduplicationConfig:
    EARLY_CONFIRMATION_SIZE_LIMIT = 128 * 1024  # Files ≤ this size can be confirmed after front hash

    @staticmethod
    def get_chunk_size(file_size: int) -> int:
        limit = DeduplicationConfig.EARLY_CONFIRMATION_SIZE_LIMIT
        if file_size <= limit:
            return file_size
        elif file_size <= limit * 2:
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
class PartialHashStageBase(HashStageBase):
    """
    Abstract base class for stages that perform partial hashing.
    Encapsulates common logic for front/middle/end hash stages.
    """
    def __init__(self, grouper: FileGrouper):
        self.grouper = grouper

    def get_threshold(self) -> int:
        """Returns the file size threshold for early confirmation."""
        raise NotImplementedError

    def get_stage_name(self) -> str:
        """Returns the name of the current stage."""
        raise NotImplementedError

    def _group_files(self, files: List[File]) -> Dict[bytes, List[File]]:
        """Groups files by their hash values."""
        raise NotImplementedError

    def _should_confirm_early(self, file: File) -> bool:
        """Determines if a file should be confirmed as duplicate at this stage."""
        return file.size <= self.get_threshold()

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

            for hkey, files_in_group in hash_groups.items():
                small_files = [f for f in files_in_group if self._should_confirm_early(f)]
                large_files = [f for f in files_in_group if not self._should_confirm_early(f)]

                if small_files:
                    confirmed_duplicates.append(DuplicateGroup(size=group.size, files=small_files))
                if large_files:
                    new_potential_groups.append(DuplicateGroup(size=group.size, files=large_files))

            processed_files += len(group.files)
            if progress_callback:
                progress_callback(self.get_stage_name(), processed_files, total_files)

        return new_potential_groups


# ==============================
# Individual Stages
# =============================
class SizeStage:
    def __init__(self, grouper: FileGrouper, boost: BoostMode = BoostMode.SAME_SIZE):
        self.grouper = grouper
        self.boost = boost

    def process(
            self,
            files: List[File],
            stopped_flag: Optional[Callable[[], bool]] = None,
            progress_callback: Optional[Callable[[str, int, object], None]] = None
    ) -> List[DuplicateGroup]:
        """Group by file size. Returns list of DuplicateGroups with 2+ files of same size."""
        if stopped_flag and stopped_flag():
            return []

        groups = []

        # Use size+extension grouping if enabled, otherwise size only
        if self.boost == BoostMode.SAME_SIZE:
            # Only size grouping
            size_groups = self.grouper.group_by_size(files)
            groups = [
                DuplicateGroup(size=size, files=files_list)
                for size, files_list in size_groups.items()
            ]

        elif self.boost == BoostMode.SAME_SIZE_PLUS_EXT:
            # Size + extension grouping
            size_ext_groups = self.grouper.group_by_size_and_extension(files)
            groups = [
                DuplicateGroup(size=size, files=files_list)
                for (size, ext), files_list in size_ext_groups.items()
            ]

        elif self.boost == BoostMode.SAME_SIZE_PLUS_FILENAME:
            size_name_groups = self.grouper.group_by_size_and_name(files)
            groups = [
                DuplicateGroup(size=size, files=files_list)
                for (size, name), files_list in size_name_groups.items()
            ]

        elif self.boost == BoostMode.SAME_SIZE_PLUS_FUZZY_FILENAME:
            size_name_groups = self.grouper.group_by_size_and_normalized_name(files)
            groups = [
                DuplicateGroup(size=size, files=files_list)
                for (size, name), files_list in size_name_groups.items()
            ]


        if progress_callback:
            total_files = len(files)
            progress_callback("Size grouping", total_files, total_files)

        return groups


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
        return int(DeduplicationConfig.EARLY_CONFIRMATION_SIZE_LIMIT * 2)

    def get_stage_name(self) -> str:
        return "End-chunk Hash"

    def _group_files(self, files: List[File]) -> Dict[bytes, List[File]]:
        return self.grouper.group_by_end_hash(files)

    def _should_confirm_early(self, file: File) -> bool:
        # Don't use early confirmation
        return False


class FullHashStage:
    def __init__(self, grouper: FileGrouper):
        self.grouper = grouper

    def process(
        self,
        groups: List[DuplicateGroup],
        confirmed_duplicates: List[DuplicateGroup],
        stopped_flag: Optional[Callable[[], bool]] = None,
        progress_callback: Optional[Callable[[str, int, object], None]] = None
    ) -> List[DuplicateGroup]:
        """Processes duplicate groups through full hash stage (PARALLELIZED)."""
        if stopped_flag and stopped_flag():
            return []

        total_files = sum(len(g.files) for g in groups)
        processed_files = 0

        for group in groups:
            if stopped_flag and stopped_flag():
                return []

            # PARALLEL: Pass stopped_flag to grouper for cancellation support
            hash_groups = self.grouper.group_by_full_hash(
                group.files,
                stopped_flag=stopped_flag
            )

            for hkey, files in hash_groups.items():
                if stopped_flag and stopped_flag():
                    return []
                if len(files) >= 2:
                    confirmed_duplicates.append(DuplicateGroup(size=group.size, files=files))

            processed_files += len(group.files)
            if progress_callback:
                progress_callback("Full Hash", processed_files, total_files)

        return []