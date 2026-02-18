
### Implement Boost Mode Logic

*   **`same_size`**: Files are grouped solely by size. Generates larger candidate groups that require more time for hashing.
*   **`same_size_plus_ext`**: Files are grouped by both size and file extension (e.g., `.jpg`). This prevents comparing files of different types that happen to have the same size (e.g., an image vs. a text file).
*   **`same_size_plus_filename_ext`**: Files are grouped by size and full filename. This is the ideal mode for finding backups or files moved to different folders while retaining their name. Files with different names will not be compared, which significantly speeds up the process.