"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License

core/sorter.py
Pure sorting logic for duplicate groups — zero dependencies outside core.
Respects absolute priority of favourite files while providing flexible tie-breaking strategies.
"""
from typing import List
from deduplicator.core.models import DuplicateGroup, SortOrder


class Sorter:
    """
    Sorts files inside duplicate groups according to specified order.
    Modifies groups in-place.
    Sorting priority (applied lexicographically):
    1. Favourite files ALWAYS first (absolute priority: never mixed with non-favourites)
    2. Secondary criterion depends on sort_order:
       - TIME-FIRST modes (NEWEST/OLDEST): time → path depth
       - DEPTH-FIRST modes (SHALLOW_*): path depth → time
    3. Tertiary criterion resolves remaining ties
    """

    @staticmethod
    def sort_files_inside_groups(groups: List[DuplicateGroup], sort_order: SortOrder = None) -> None:
        if not groups:
            return

        if sort_order is None:
            sort_order = SortOrder.NEWEST_FIRST

        for group in groups:
            if sort_order in (SortOrder.SHALLOW_THEN_NEWEST, SortOrder.SHALLOW_THEN_OLDEST):
                key_func = lambda f: (
                    not f.is_from_fav_dir,
                    f.path_depth,
                    -(f.creation_time or 0) if sort_order == SortOrder.SHALLOW_THEN_NEWEST
                    else (f.creation_time or 0)
                )
            else:
                key_func = lambda f: (
                    not f.is_from_fav_dir,
                    -(f.creation_time or 0) if sort_order == SortOrder.NEWEST_FIRST
                    else (f.creation_time or 0),
                    f.path_depth
                )
            group.files.sort(key=key_func)