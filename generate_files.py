#!/usr/bin/env python3
"""
Test File Generator with Similarity Support.
Creates files that are similar (e.g., 90% identical) but not exact duplicates.
"""

import time
import os
import random
import shutil
from pathlib import Path

# ==============================================================================
# CONFIGURATION
# ==============================================================================
OUTPUT_DIRECTORY = 'similar_files/average/'
FILE_COUNT = 3000  # Total number of files to create

# --- MODES ---
# 1. UNIQUE_ONLY: All files are completely different.
# 2. EXACT_DUPLICATES: Some files are exact copies (bit-for-bit).
# 3. SIMILAR_FILES: Files share most content (e.g., 90%) but differ slightly.
GENERATION_MODE = 'SIMILAR_FILES'

# Settings for SIMILAR_FILES mode
SIMILARITY_PERCENT = 90  # How much of the content should be identical (0-100)
BASE_TEMPLATES_COUNT = 50  # How many unique "Base" files to create before mutating
# (More bases = less correlation between different groups)

# Settings for Sizing
MIN_FILE_SIZE = 32 * 1024
MAX_FILE_SIZE = 512 * 1024
# In SIMILAR mode, derived files will match the size of their Base Template.

# Content Settings
USE_RANDOM_DATA = True  # True = Random bytes (Good for hash/compression tests)
# False = Zeros (Fast, bad for compression tests)

WRITE_BUFFER_SIZE = 32 * 1024 * 1024


# ==============================================================================

def format_size(bytes_: int) -> str:
    if bytes_ >= 1024 * 1024 * 1024:
        return f"{bytes_ / 1024 / 1024 / 1024:.2f} GB"
    elif bytes_ >= 1024 * 1024:
        return f"{bytes_ / 1024 / 1024:.2f} MB"
    elif bytes_ >= 1024:
        return f"{bytes_ / 1024:.2f} KB"
    return f"{bytes_} B"


def create_file_fresh(path: str, size: int, use_random: bool) -> None:
    """Creates a new file from scratch (zeros or random)."""
    with open(path, 'wb') as f:
        remaining = size
        while remaining > 0:
            write_size = min(WRITE_BUFFER_SIZE, remaining)
            if use_random:
                f.write(os.urandom(write_size))
            else:
                f.write(b'\x00' * write_size)
            remaining -= write_size


def create_similar_file(source_path: str, dest_path: str, similarity_ratio: float) -> None:
    """
    Creates a new file based on a source file, modifying (1 - ratio) of its content.

    Args:
        source_path: Path to the base file.
        dest_path: Path for the new similar file.
        similarity_ratio: Float between 0.0 and 1.0 (e.g., 0.9 for 90%).
    """
    # Read entire source into memory (bytearray is mutable)
    # 15MB fits easily in RAM. If files are GBs, this needs chunking logic.
    with open(source_path, 'rb') as f:
        data = bytearray(f.read())

    total_size = len(data)
    if total_size == 0:
        # Handle empty file edge case
        with open(dest_path, 'wb') as f:
            pass
        return

    # Calculate how many bytes to change
    change_count = int(total_size * (1.0 - similarity_ratio))

    if change_count > 0:
        # Strategy: Replace a contiguous block of bytes at a random offset.
        # This is faster than scattering single bytes and still breaks checksums.
        # To make it more realistic (scattered), we could split change_count into chunks.
        # Here we do one block for speed and simplicity.

        max_offset = total_size - change_count
        if max_offset < 0: max_offset = 0  # Safety

        start_index = random.randint(0, max_offset)
        end_index = start_index + change_count

        # Overwrite with random data
        data[start_index:end_index] = os.urandom(change_count)

        # Optional: Scatter small changes instead of one big block?
        # Uncomment below for scattered noise (slower):
        # for _ in range(change_count):
        #     idx = random.randint(0, total_size - 1)
        #     data[idx] = random.randint(0, 255)

    # Write modified data to new file
    with open(dest_path, 'wb') as f:
        f.write(data)


def main():
    print("=" * 70)
    print("TEST FILE GENERATOR (SIMILARITY MODE)")
    print("=" * 70)
    print(f"Output Directory:   {OUTPUT_DIRECTORY}")
    print(f"Total Files:        {FILE_COUNT}")
    print(f"Mode:               {GENERATION_MODE}")

    if GENERATION_MODE == 'SIMILAR_FILES':
        print(f"Similarity:        {SIMILARITY_PERCENT}%")
        print(f"Base Templates:    {BASE_TEMPLATES_COUNT}")
    elif GENERATION_MODE == 'EXACT_DUPLICATES':
        print(f"Unique Files:      {BASE_TEMPLATES_COUNT}")

    print(f"Content:            {'Random Data' if USE_RANDOM_DATA else 'Zeros'}")
    print(f"Size Range:         {format_size(MIN_FILE_SIZE)} - {format_size(MAX_FILE_SIZE)}")
    print("=" * 70)

    Path(OUTPUT_DIRECTORY).mkdir(parents=True, exist_ok=True)

    print("\n⏳ Starting generation...\n")
    start_time = time.perf_counter()

    total_bytes_written = 0
    successful_files = 0
    base_templates = []  # Store paths of base files

    # Determine how many files should be base templates
    if GENERATION_MODE == 'SIMILAR_FILES':
        effective_bases = min(BASE_TEMPLATES_COUNT, FILE_COUNT)
    elif GENERATION_MODE == 'EXACT_DUPLICATES':
        effective_bases = min(BASE_TEMPLATES_COUNT, FILE_COUNT)
    else:
        effective_bases = FILE_COUNT  # All unique

    try:
        for i in range(1, FILE_COUNT + 1):
            file_name = f"test_file_{i:03d}.bin"
            file_path = os.path.join(OUTPUT_DIRECTORY, file_name)

            is_base_file = i <= effective_bases

            if is_base_file:
                # --- CREATE BASE TEMPLATE ---
                file_size = random.randint(MIN_FILE_SIZE, MAX_FILE_SIZE)
                print(f"[{i}/{FILE_COUNT}] 🆔 Base: {file_name} ({format_size(file_size)})", end=" ")

                t_start = time.perf_counter()
                create_file_fresh(file_path, file_size, USE_RANDOM_DATA)
                t_elapsed = time.perf_counter() - t_start

                base_templates.append(file_path)
                total_bytes_written += file_size

            else:
                # --- CREATE DERIVATIVE (SIMILAR OR DUPLICATE) ---
                # Pick a random base template
                source_path = random.choice(base_templates)
                file_size = os.path.getsize(source_path)  # Match base size exactly

                if GENERATION_MODE == 'SIMILAR_FILES':
                    print(f"[{i}/{FILE_COUNT}] Sim:  {file_name} ({format_size(file_size)})", end=" ")
                    t_start = time.perf_counter()
                    create_similar_file(source_path, file_path, SIMILARITY_PERCENT / 100.0)
                    t_elapsed = time.perf_counter() - t_start
                elif GENERATION_MODE == 'EXACT_DUPLICATES':
                    print(f"[{i}/{FILE_COUNT}] Dup:  {file_name} ({format_size(file_size)})", end=" ")
                    t_start = time.perf_counter()
                    shutil.copy2(source_path, file_path)
                    t_elapsed = time.perf_counter() - t_start
                else:
                    # UNIQUE_ONLY mode (should not happen given logic above, but for safety)
                    file_size = random.randint(MIN_FILE_SIZE, MAX_FILE_SIZE)
                    print(f"[{i}/{FILE_COUNT}] Unq:  {file_name} ({format_size(file_size)})", end=" ")
                    t_start = time.perf_counter()
                    create_file_fresh(file_path, file_size, USE_RANDOM_DATA)
                    t_elapsed = time.perf_counter() - t_start

                total_bytes_written += file_size

            successful_files += 1
            speed = file_size / t_elapsed / 1024 / 1024
            print(f"({speed:.0f} MB/s)")

    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user.")
        return
    except Exception as e:
        print(f"\n\nError occurred: {e}")
        raise

    total_elapsed = time.perf_counter() - start_time

    # Summary Statistics
    print("\n" + "=" * 70)
    print("GENERATION SUMMARY")
    print("=" * 70)
    print(f"Files Created:      {successful_files}/{FILE_COUNT}")
    print(f"Total Data Size:    {format_size(total_bytes_written)}")
    print(f"Total Time:         {total_elapsed:.2f} seconds")

    if total_elapsed > 0:
        avg_throughput = total_bytes_written / total_elapsed / 1024 / 1024
        print(f"Avg Throughput:    {avg_throughput:.2f} MB/s")

    print("=" * 70)
    if GENERATION_MODE == 'SIMILAR_FILES':
        print(f"Files are {SIMILARITY_PERCENT}% similar (Delta Compression Ready)")
    print("=" * 70)


if __name__ == '__main__':
    main()