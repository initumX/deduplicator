"""
similar_image_finder.py

Implements a class to find visually similar images using perceptual hashing.
"""

from typing import List, Optional, Callable
from core.models import File, DuplicateGroup
from utils.services import FileService
from PIL import Image
import imagehash


class SimilarImageFinder:
    """
    Class for finding visually similar images.

    Uses perceptual hashing (phash) to detect similarities between images.
    Returns results as list of DuplicateGroup objects for compatibility with UI.
    """

    def __init__(self, threshold: int = 5):
        """
        Initialize with a similarity threshold.

        Args:
            threshold (int): Maximum allowed phash difference (lower = more similar).
        """
        self.threshold = int(threshold)  # Max bit differences between hashes

    def compute_phash(
            self, file: File,
            stopped_flag: Optional[Callable[[], bool]] = None
    ) -> Optional[imagehash.ImageHash]:
        """
        Compute perceptual hash of an image file.

        Args:
            file (File): File object containing path and size.
            stopped_flag (Optional[Callable[[], bool]]): Function that returns True if operation should be cancelled.

        Returns:
            imagehash.ImageHash or None if file is invalid or operation was stopped.
        """
        if stopped_flag and stopped_flag():
            return None

        if file.phash is not None:
            try:
                return imagehash.hex_to_hash(file.phash.decode('utf-8'))
            except Exception as e:
                print(f"⚠️ Failed to decode cached phash for {file.path}: {e}")

        if not FileService.is_valid_image(file.path):
            return None

        try:
            with Image.open(file.path) as img:
                # Resize large images for faster processing
                if img.size[0] > 1024 or img.size[1] > 1024:
                    img.thumbnail((1024, 1024))
                phash = imagehash.phash(img, hash_size=8)
                # Cache it back into the File object
                file.phash = str(phash).encode('utf-8')
                return phash
        except Exception as e:
            print(f"⚠️ Failed to compute phash for {file.path}: {e}")
            return None

    def find_similar_images(
            self,
            files: List[File],
            stopped_flag: Optional[Callable[[], bool]] = None
    ) -> List[DuplicateGroup]:
        """
        Find groups of visually similar images.

        Args:
            files (List[File]): List of scanned files.
            stopped_flag (Optional[Callable[[], bool]]): Function that returns True if operation should be cancelled.

        Returns:
            List of DuplicateGroup objects, each containing ≥2 similar images.
        """
        # Filter only valid image files
        image_files = [f for f in files if FileService.is_valid_image(f.path)]
        if len(image_files) < 2:
            return []

        hash_map = {}  # Hash → list of similar files
        similar_groups = []

        for file in image_files:
            if stopped_flag and stopped_flag():
                return []

            phash = self.compute_phash(file, stopped_flag=stopped_flag)
            if phash is None:
                continue

            matched = False
            # Compare with existing hashes
            for existing_hash in list(hash_map.keys()):
                if stopped_flag and stopped_flag():
                    return []

                if abs(existing_hash - phash) <= self.threshold:
                    hash_map[existing_hash].append(file)
                    matched = True
                    break

            if not matched:
                hash_map[phash] = [file]

        # Create DuplicateGroups from matching hashes
        for key, files_in_group in hash_map.items():
            if len(files_in_group) >= 2:
                similar_groups.append(DuplicateGroup(size=0, files=files_in_group))

        return similar_groups

    def find_similar_to_image(
            self,
            target_file: File,
            all_files: List[File],
            stopped_flag: Optional[Callable[[], bool]] = None
    ) -> List[DuplicateGroup]:
        """
        Find images similar to the specified target image.

        Args:
            target_file (File): The reference image.
            all_files (List[File]): All scanned files to compare against.
            stopped_flag (Optional[Callable[[], bool]]): Function that returns True if operation should be cancelled.

        Returns:
            List of DuplicateGroup objects containing similar images.
        """
        if not FileService.is_valid_image(target_file.path):
            raise ValueError(f"Target file {target_file.path} is not a valid image")

        target_hash = self.compute_phash(target_file, stopped_flag=stopped_flag)
        if target_hash is None:
            return []

        # Filter all_files to include only other images, excluding the target itself
        candidates = [
            f for f in all_files
            if f.path != target_file.path and FileService.is_valid_image(f.path)
        ]

        similar_files = [target_file]
        for file in candidates:
            if stopped_flag and stopped_flag():
                return []
            current_hash = self.compute_phash(file, stopped_flag=stopped_flag)
            if current_hash is None:
                continue
            if abs(target_hash - current_hash) <= self.threshold:
                similar_files.append(file)

        if len(similar_files) >= 2:
            return [DuplicateGroup(size=0, files=similar_files)]
        else:
            return []