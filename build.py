"""
build.py — Build script for compiling the PySide6-based File Deduplicator GUI application into a single executable.
"""

import subprocess
import sys
import os

# Check if we're in the correct directory
if not os.path.exists("src/deduplicator/gui/main_window.py"):
    print("❌ ERROR: 'main_window.py' not found in current directory.")
    print("Make sure you're running this script from the project root folder.")
    sys.exit(1)

# Try to import nuitka or fail gracefully
try:
    import nuitka  # Just to check installation
except ImportError:
    print("❌ Nuitka is not installed. Please install it first:")
    print("pip install nuitka pyside6")
    sys.exit(1)

# Define the build command
build_command = [
    "nuitka",
    "--standalone",
    "--onefile",
    "--enable-plugin=pyside6",
    "--output-dir=dist",
    "main_window.py"
]

print("🚀 Starting build process with Nuitka...\n")

# Run the build command
try:
    subprocess.run(build_command, check=True)
    print("\n✅ Build completed successfully!")
    print("➡️ Executable located in: dist/main_window.onefile-build/")
except subprocess.CalledProcessError as e:
    print(f"\n❌ Build failed. Error code: {e.returncode}")
    sys.exit(e.returncode)
except Exception as e:
    print(f"\n❌ Unexpected error during build: {e}")
    sys.exit(1)