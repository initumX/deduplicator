"""
Copyright (c) 2025 initumX (initum.x@gmail.com)
Licensed under the MIT License

core/sorter.py
Pure sorting logic for duplicate groups.
Respects absolute priority of favourite files while providing flexible tie-breaking strategies.
"""
from typing import List
from highlander.core.models import DuplicateGroup, SortOrder


class Sorter:
    """
    Sorts files inside duplicate groups according to specified order.
    Modifies groups in-place.
    Sorting priority (applied lexicographically):
    1. Favourite files ALWAYS first (absolute priority: never mixed with non-favourites)
    2. Secondary criterion depends on sort_order:
       - SHORTEST_PATH mode: file with shortest path (closer to Root Folder) goes first (DEFAULT)
       - SHORTEST_FILENAME mode: file with shortest filename goes first
    """

    @staticmethod
    def sort_files_inside_groups(groups: List[DuplicateGroup], sort_order: SortOrder = None) -> None:
        if not groups:
            return

        if sort_order is None:
            sort_order = SortOrder.SHORTEST_PATH

        for group in groups:
            if sort_order == SortOrder.SHORTEST_FILENAME:
                key_func = lambda f: (
                    not f.is_from_fav_dir,
                    len(f.name),
                    f.path_depth
                )
            else:
                key_func = lambda f: (
                    not f.is_from_fav_dir,
                    f.path_depth,
                    len(f.name)
                )
            group.files.sort(key=key_func)