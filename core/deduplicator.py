"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License

deduplicator.py
Implements a pipeline-based deduplication system using File objects.
Supports three modes:
    - fast: size → front
    - normal: size → front → middle → end
    - full: size → front → middle → full_hash
"""
import time
from typing import List, Tuple, Dict, Optional, Callable
from core.models import File, DuplicateGroup, DeduplicationStats, DeduplicationMode
from core.grouper import FileGrouperImpl
from core.interfaces import PartialHashStage, Deduplicator
from core.stages import SizeStageImpl, FrontHashStage, MiddleHashStage, EndHashStage, FullHashStage

# =============================
# Main Deduplicator Class
# =============================
class DeduplicatorImpl(Deduplicator):
    """
    Implements multi-stage duplicate detection using a pipeline architecture.
    Respects the DeduplicationMode enum and collects detailed statistics.
    """
    def __init__(self, grouper=None):
        self.grouper = grouper or FileGrouperImpl()

    def find_duplicates(
        self,
        files: List[File],
        mode: DeduplicationMode,
        stopped_flag: Optional[Callable[[], bool]] = None,
        progress_callback: Optional[Callable[[str, int, object], None]] = None
    ) -> Tuple[List[DuplicateGroup], DeduplicationStats]:
        """
                Main deduplication pipeline using File objects.
        Args:
            files: List of scanned file objects
            mode: Deduplication strategy ('fast', 'normal', or 'full')
            stopped_flag (Optional[Callable[[], bool]]): Function that returns True if operation should be stopped.
            progress_callback (Optional[Callable[[str, int, int], None]]): Reports progress per stage.
        Returns:
            Tuple[List[DuplicateGroup], DeduplicationStats]
        """
        stats = DeduplicationStats()
        total_start_time = time.time()

        # Initial stage: group by size
        size_stage = SizeStageImpl(self.grouper)
        start_time = time.time()
        groups = size_stage.process(
            files,
            stopped_flag=stopped_flag,
            progress_callback=progress_callback
        )
        duration = time.time() - start_time
        DeduplicatorImpl._update_stats(stats, "size", duration, groups, [])

        confirmed_duplicates = []

        # Build pipeline
        pipeline = self._build_pipeline(mode)

        # Run all stages in sequence
        for stage_name, stage in pipeline:
            start_time = time.time()
            groups = stage.process(
                groups,
                confirmed_duplicates,
                stopped_flag=stopped_flag,
                progress_callback=progress_callback
            )
            duration = time.time() - start_time
            DeduplicatorImpl._update_stats(stats, stage_name, duration, groups, confirmed_duplicates)

        # Combine confirmed duplicates and unprocessed groups
        all_duplicates = confirmed_duplicates + groups

        # Sort by descending size
        all_duplicates.sort(key=lambda g: -g.files[0].size if g.files else 0)

        # Finalize stats
        stats.total_time = time.time() - total_start_time

        return all_duplicates, stats

    def _build_pipeline(self, mode: DeduplicationMode) -> List[Tuple[str, PartialHashStage]]:
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