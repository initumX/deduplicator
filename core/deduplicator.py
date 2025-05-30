"""
deduplicator.py
Implements a pipeline-based deduplication system using File objects.
Supports three modes:
    - fast: size → front
    - normal: size → front → middle → end
    - full: size → front → middle → full_hash
"""
import time
from typing import List, Tuple, Protocol, Optional, Callable
from core.models import File, DuplicateGroup, DeduplicationStats, DeduplicationMode
from core.grouper import DefaultFileGrouper
from collections import defaultdict


# =============================
# Stage Interface
# =============================
class DeduplicationStage(Protocol):
    def process(self, groups: List[DuplicateGroup]) -> List[DuplicateGroup]:
        ...


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
    EARLY_CONFIRMATION_SIZE_LIMIT = 256 * 1024  # Files ≤ this size can be confirmed after front hash

    @staticmethod
    def get_chunk_size(file_size: int) -> int:
        limit = DeduplicationConfig.EARLY_CONFIRMATION_SIZE_LIMIT
        if file_size <= limit:
            return file_size
        elif file_size <= limit * 2:
            return limit    # First elif should return limit, don't change it
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

    def __init__(self, grouper: DefaultFileGrouper):
        self.grouper = grouper

    def compute_hash(self, file: File) -> bytes:
        """
        Computes the specific hash for this stage.
        Must be implemented by subclasses.
        """
        raise NotImplementedError

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

    def process(
        self,
        groups: List[DuplicateGroup],
        confirmed_duplicates: List[DuplicateGroup],
        stopped_flag: Optional[Callable[[], bool]] = None
    ) -> List[DuplicateGroup]:
        """
        Processes duplicate groups through this hash stage.
        Groups are split into small/large files based on threshold.
        Small files may be confirmed as duplicates, large files continue processing.
        """
        if stopped_flag and stopped_flag():
            return []

        new_potential_groups = []
        for group in groups:
            if stopped_flag and stopped_flag():
                return []

            # Assign chunk sizes before hashing
            HashStageBase.assign_chunk_sizes(group.files)

            # Compute hash groups
            hash_groups = defaultdict(list)
            for file in group.files:
                if stopped_flag and stopped_flag():
                    return []
                try:
                    key = self.compute_hash(file)
                    hash_groups[key].append(file)
                except Exception as e:
                    print(f"⚠️ Error computing hash for {file.path}: {e}")

            # Process each hash group
            threshold = self.get_threshold()
            for hkey, files_in_group in hash_groups.items():
                if len(files_in_group) < 2:
                    continue

                small_files = [f for f in files_in_group if f.size <= threshold]
                large_files = [f for f in files_in_group if f.size > threshold]

                if len(small_files) >= 2:
                    confirmed_duplicates.append(DuplicateGroup(size=group.size, files=small_files))

                if len(large_files) >= 2:
                    new_potential_groups.append(DuplicateGroup(size=group.size, files=large_files))

        return new_potential_groups


# =============================
# Individual Stages
# =============================
class SizeStage:
    def __init__(self, grouper: DefaultFileGrouper):
        self.grouper = grouper

    def process(self, files: List[File],
                stopped_flag: Optional[Callable[[], bool]] = None) -> List[DuplicateGroup]:
        """
        Group by file size.
        Returns list of DuplicateGroups with 2+ files of same size.
        """
        if stopped_flag and stopped_flag():
            return []
        size_groups = self.grouper.group_by_size(files)
        return [
            DuplicateGroup(size=size, files=files_list)
            for size, files_list in size_groups.items()
            if len(files_list) >= 2
        ]


class FrontHashStage(PartialHashStageBase):
    def compute_hash(self, file: File) -> bytes:
        return self.grouper.hasher.compute_front_hash(file)

    def get_threshold(self) -> int:
        return DeduplicationConfig.EARLY_CONFIRMATION_SIZE_LIMIT

    def get_stage_name(self) -> str:
        return "front"


class MiddleHashStage(PartialHashStageBase):
    def compute_hash(self, file: File) -> bytes:
        return self.grouper.hasher.compute_middle_hash(file)

    def get_threshold(self) -> int:
        return int(DeduplicationConfig.EARLY_CONFIRMATION_SIZE_LIMIT * 1.5)

    def get_stage_name(self) -> str:
        return "middle"


class EndHashStage(PartialHashStageBase):
    def compute_hash(self, file: File) -> bytes:
        return self.grouper.hasher.compute_end_hash(file)

    def get_threshold(self) -> int:
        return int(DeduplicationConfig.EARLY_CONFIRMATION_SIZE_LIMIT * 2)

    def get_stage_name(self) -> str:
        return "end"


class FullHashStage:
    def __init__(self, grouper: DefaultFileGrouper):
        self.grouper = grouper

    def process(
            self,
            groups: List[DuplicateGroup],
            confirmed_duplicates: List[DuplicateGroup],
            stopped_flag: Optional[Callable[[], bool]] = None
    ) -> List[DuplicateGroup]:
        if stopped_flag and stopped_flag():
            return []
        for group in groups:
            if stopped_flag and stopped_flag():
                return []
            hash_groups = self.grouper.group_by_full_hash(group.files)
            for hkey, files in hash_groups.items():
                if stopped_flag and stopped_flag():
                    return []
                if len(files) >= 2:
                    confirmed_duplicates.append(DuplicateGroup(size=group.size, files=files))
        return []



# =============================
# Main Deduplicator Class
# =============================
class Deduplicator:
    """
    Implements multi-stage duplicate detection using a pipeline architecture.
    Respects the DeduplicationMode enum and collects detailed statistics.
    """
    def __init__(self, grouper=None):
        self.grouper = grouper or DefaultFileGrouper()

    def find_duplicates(
        self,
        files: List[File],
        mode: DeduplicationMode,
        stopped_flag: Optional[Callable[[], bool]] = None
    ) -> Tuple[List[DuplicateGroup], DeduplicationStats]:
        """
        Main deduplication pipeline using File objects.
        Args:
            files: List of scanned file objects
            mode: Deduplication strategy ('fast', 'normal', or 'full')
            stopped_flag (Optional[Callable[[], bool]]): Function that returns True if operation should be stopped.
        Returns:
            Tuple[List[DuplicateGroup], DeduplicationStats]
        """
        stats = DeduplicationStats()
        total_start_time = time.time()

        # Initial stage: group by size
        size_stage = SizeStage(self.grouper)
        start_time = time.time()
        groups = size_stage.process(files, stopped_flag=stopped_flag)
        duration = time.time() - start_time
        Deduplicator._update_stats(stats, "size", duration, groups, [])

        confirmed_duplicates = []

        # Build pipeline
        pipeline = self._build_pipeline(mode)

        # Run all stages in sequence
        for stage_name, stage in pipeline:
            start_time = time.time()
            groups = stage.process(groups, confirmed_duplicates, stopped_flag=stopped_flag)
            duration = time.time() - start_time
            Deduplicator._update_stats(stats, stage_name, duration, groups, confirmed_duplicates)

        # Filter out groups with less than 2 files
        final_unconfirmed = [g for g in groups if len(g.files) >= 2]

        # Combine confirmed duplicates and unprocessed groups
        all_duplicates = confirmed_duplicates + final_unconfirmed

        # Sort by descending size
        all_duplicates.sort(key=lambda g: -g.files[0].size if g.files else 0)

        # Finalize stats
        stats.total_time = time.time() - total_start_time

        return all_duplicates, stats

    def _build_pipeline(self, mode: DeduplicationMode):
        """Builds the appropriate pipeline based on deduplication mode."""
        pipeline = []
        if mode == DeduplicationMode.FAST:
            pipeline.append(("front", FrontHashStage(self.grouper)))
        elif mode == DeduplicationMode.NORMAL:
            pipeline.append(("front", FrontHashStage(self.grouper)))
            pipeline.append(("middle", MiddleHashStage(self.grouper)))
            pipeline.append(("end", EndHashStage(self.grouper)))
        elif mode == DeduplicationMode.FULL:
            pipeline.append(("front", FrontHashStage(self.grouper)))
            pipeline.append(("middle", MiddleHashStage(self.grouper)))
            pipeline.append(("full", FullHashStage(self.grouper)))
        return pipeline

    @staticmethod
    def _update_stats(
        stats: DeduplicationStats,
        stage: str,
        duration: float,
        groups: List[DuplicateGroup],
        confirmed_duplicates: List[DuplicateGroup]
    ):
        """
        Helper to update DeduplicationStats object.
        Includes both unconfirmed and confirmed groups in stats.
        """
        # Total files in all groups (both confirmed and unconfirmed)
        total_files = sum(len(g.files) for g in groups) + sum(len(g.files) for g in confirmed_duplicates)
        # Total number of potential or confirmed duplicate groups
        total_groups = len(groups) + len(confirmed_duplicates)
        stats.update_stage(
            stage_name=stage,
            groups_found=total_groups,
            files_processed=total_files,
            duration=duration
        )