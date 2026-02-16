#!/bin/bash
set -e
unset PYTHONPATH PYTHONHOME

# Build status flags
BUILD_SUCCESS="false"
KEEP_DIRTY="false"

# ANSI color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Define project root immediately (to avoid cd dependency)
PROJECT_ROOT="$(pwd)"
APPDIR="${PROJECT_ROOT}/AppDir"
DIST_DIR="${PROJECT_ROOT}/dist-appimage"
VENV_PATH="${APPDIR}/usr/python"
BIN_PATH="${APPDIR}/usr/bin"

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dirty)
            KEEP_DIRTY="true"
            shift
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}" >&2
            echo "Usage: $0 [--dirty]" >&2
            echo "  --dirty    Keep temporary files (AppDir/, AppImageBuilder.yml) after successful build" >&2
            exit 1
            ;;
    esac
done

# Cleanup function: runs on ANY exit (success, error, Ctrl+C)
cleanup() {
    # Deactivate any active virtual environment
    if [ -n "${VIRTUAL_ENV}" ]; then
        deactivate 2>/dev/null || true
    fi

    # Handle cleanup based on build status and --dirty flag
    if [ "${BUILD_SUCCESS}" != "true" ]; then
        # Build failed: remove EVERYTHING
        rm -rf "${APPDIR}" "${PROJECT_ROOT}/AppImageBuilder.yml" "${DIST_DIR}" 2>/dev/null || true
        echo -e "${YELLOW}🧹 Cleanup completed (build failed)${NC}" >&2
    else
        # Build succeeded
        if [ "${KEEP_DIRTY}" = "true" ]; then
            echo -e "${YELLOW}⚠️  Build successful with --dirty: temporary files preserved${NC}" >&2
            echo -e "${YELLOW}   Inspect: AppDir/ and AppImageBuilder.yml${NC}" >&2
        else
            # Normal cleanup: remove only temporary files
            rm -rf "${APPDIR}" "${PROJECT_ROOT}/AppImageBuilder.yml" 2>/dev/null || true
            echo -e "${YELLOW}🧹 Cleanup completed (temporary files removed)${NC}" >&2
        fi
    fi
}
trap cleanup EXIT INT TERM

echo -e "${GREEN}🚀 Starting AppImage build for onlyone${NC}"
[ "${KEEP_DIRTY}" = "true" ] && echo -e "${YELLOW}⚠️  --dirty mode: temporary files will be preserved on success${NC}"

# === 1. Check required dependencies ===
echo -e "${YELLOW}🔍 Checking dependencies...${NC}"
command -v appimage-builder >/dev/null 2>&1 || { echo -e "${RED}❌ appimage-builder not found. Install via: pip install git+https://github.com/AppImageCrafters/appimage-builder.git${NC}"; exit 1; }
command -v patchelf >/dev/null 2>&1 || { echo -e "${RED}❌ patchelf not found. Install via: sudo apt install patchelf${NC}"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo -e "${RED}❌ python3 not found${NC}"; exit 1; }

# === 2. Detect version from pyproject.toml ===
echo -e "${YELLOW}📦 Detecting version from pyproject.toml...${NC}"
if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" 2>/dev/null; then
    VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])" 2>/dev/null || true)
else
    pip install tomli -q 2>/dev/null
    VERSION=$(python3 -c "import tomli; print(tomli.load(open('pyproject.toml', 'rb'))['project']['version'])" 2>/dev/null || true)
fi

if [ -z "${VERSION}" ]; then
    VERSION="2.4.3"
    echo -e "${YELLOW}⚠️  Could not parse version, using fallback: ${VERSION}${NC}"
else
    echo -e "${GREEN}✅ Version detected: ${VERSION}${NC}"
fi

# === 3. Clean previous build artifacts ===
echo -e "${YELLOW}🧹 Cleaning previous builds...${NC}"
rm -rf "${APPDIR}" "${DIST_DIR}"
mkdir -p "${DIST_DIR}"

# === 4. Build AppDir structure ===
echo -e "${YELLOW}🏗️  Building AppDir structure...${NC}"
mkdir -p "${BIN_PATH}"
mkdir -p "${APPDIR}/usr/share/applications"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"

# Create isolated Python environment inside AppDir
echo -e "${YELLOW}🐍 Creating embedded Python environment...${NC}"
python3 -m venv "${VENV_PATH}"

# Activate environment to install packages
source "${VENV_PATH}/bin/activate"
pip install --upgrade pip -q
# Install current project in development mode inside venv
pip install "${PROJECT_ROOT}[gui]" -q

# Detect the actual Python version in venv (e.g., python3.13, python3.11, etc.)
PYTHON_VERSION=$(ls "${VENV_PATH}/bin/" | grep -E '^python3\.[0-9]+$' | head -n1)
if [ -z "${PYTHON_VERSION}" ]; then
    PYTHON_VERSION="python3"
fi
echo -e "${GREEN}✅ Python version in venv: ${PYTHON_VERSION}${NC}"

deactivate

# === 4. continued: Setup executables ===
echo -e "${YELLOW}🔧 Setting up Python interpreter...${NC}"

# Check if interpreter exists inside venv
if [ ! -f "${VENV_PATH}/bin/${PYTHON_VERSION}" ]; then
    echo -e "${RED}❌ Critical error: ${PYTHON_VERSION} not found in ${VENV_PATH}/bin/${NC}" >&2
    exit 1
fi

# Create symbolic links in AppDir/usr/bin
echo -e "${YELLOW}🔗 Creating symlinks in AppDir/usr/bin...${NC}"

# Remove old symlinks if they exist
rm -f "${BIN_PATH}/python" "${BIN_PATH}/python3" "${BIN_PATH}/${PYTHON_VERSION}" 2>/dev/null || true

# Create symlinks pointing to venv bin directory (relative path)
ln -sf "../python/bin/${PYTHON_VERSION}" "${BIN_PATH}/${PYTHON_VERSION}"
ln -sf "../python/bin/python3" "${BIN_PATH}/python3"
ln -sf "../python/bin/python" "${BIN_PATH}/python"

# Verify symlinks
echo -e "${YELLOW}🔍 Verifying symlinks...${NC}"
for bin_name in "${PYTHON_VERSION}" python3 python; do
    if [ ! -L "${BIN_PATH}/${bin_name}" ]; then
        echo -e "${RED}❌ Symlink creation failed: ${BIN_PATH}/${bin_name}${NC}" >&2
        exit 1
    fi
    # Check if symlink points to existing file
    if [ ! -f "${BIN_PATH}/${bin_name}" ]; then
        echo -e "${RED}❌ Broken symlink: ${BIN_PATH}/${bin_name}${NC}" >&2
        echo -e "${RED}   Target: $(readlink "${BIN_PATH}/${bin_name}")${NC}" >&2
        exit 1
    fi
    target=$(readlink "${BIN_PATH}/${bin_name}")
    echo "  Verified: ${BIN_PATH}/${bin_name} -> ${target}"
done

# === Create .desktop file ===
echo -e "${YELLOW}📄 Creating desktop entry...${NC}"
cat > "${APPDIR}/usr/share/applications/onlyone.desktop" << EOF
[Desktop Entry]
Type=Application
Name=onlyone
Comment=Find and remove duplicate files
Exec=usr/bin/python3 -m onlyone.gui.launcher
Icon=onlyone
Categories=Utility;FileTools;
Terminal=false
EOF

# Copy application icon if available
ICON_PATH="${PROJECT_ROOT}/assets/icon.png"
if [ -f "${ICON_PATH}" ]; then
    echo -e "${YELLOW}🖼️  Copying application icon...${NC}"
    cp "${ICON_PATH}" "${APPDIR}/usr/share/icons/hicolor/256x256/apps/onlyone.png"
    # Also copy to AppDir root for appimage-builder
    cp "${ICON_PATH}" "${APPDIR}/onlyone.png"
else
    echo -e "${YELLOW}⚠️  Icon not found at ${ICON_PATH}${NC}"
fi

# === 5. Generate AppImageBuilder recipe ===
echo -e "${YELLOW}⚙️  Generating AppImageBuilder.yml...${NC}"
cat > "${PROJECT_ROOT}/AppImageBuilder.yml" << EOF
version: 1
AppDir:
  path: ./AppDir
  app_info:
    id: onlyone
    name: onlyone
    icon: onlyone
    version: ${VERSION}
    exec: usr/bin/python3
    exec_args: -m onlyone.gui.launcher
  runtime:
    env:
      PYTHONHOME: '\${APPDIR}/usr/python'
      PATH: '\${APPDIR}/usr/bin:\${PATH}'
  files:
    include:
      - usr/bin/python3
      - usr/bin/python
      - usr/bin/${PYTHON_VERSION}
      - usr/python/bin/*
AppImage:
  arch: x86_64
EOF

# === 6. Build AppImage ===
echo -e "${YELLOW}🔨 Building AppImage...${NC}"
# Run from project root so paths in recipe work correctly
cd "${PROJECT_ROOT}"

# Double-check symlinks exist before running appimage-builder
if [ ! -f "${BIN_PATH}/python3" ]; then
    echo -e "${RED}❌ Critical: ${BIN_PATH}/python3 does not exist before build${NC}" >&2
    ls -la "${BIN_PATH}/" >&2
    exit 1
fi

appimage-builder --recipe AppImageBuilder.yml --skip-tests

# Find and move the generated AppImage
EXPECTED_NAME="onlyone-${VERSION}-x86_64.AppImage"
if [ -f "${PROJECT_ROOT}/${EXPECTED_NAME}" ]; then
    mv "${PROJECT_ROOT}/${EXPECTED_NAME}" "${DIST_DIR}/"
elif [ -f "${PROJECT_ROOT}/onlyone-x86_64.AppImage" ]; then
    mv "${PROJECT_ROOT}/onlyone-x86_64.AppImage" "${DIST_DIR}/${EXPECTED_NAME}"
else
    FOUND=$(ls "${PROJECT_ROOT}"/*.AppImage 2>/dev/null | head -n1)
    if [ -n "${FOUND}" ]; then
        mv "${FOUND}" "${DIST_DIR}/${EXPECTED_NAME}"
    else
        echo -e "${RED}❌ AppImage not found after build${NC}"
        exit 1
    fi
fi
chmod +x "${DIST_DIR}/${EXPECTED_NAME}"

# === 7. Finalize ===
BUILD_SUCCESS="true"

SIZE=$(du -h "${DIST_DIR}/${EXPECTED_NAME}" | cut -f1)
echo -e "${GREEN}✅ Build successful!${NC}"
echo -e "${GREEN}📦 Output: ${DIST_DIR}/${EXPECTED_NAME}${NC}"
echo -e "${GREEN}📏 Size: ${SIZE}${NC}"
if [ "${KEEP_DIRTY}" = "true" ]; then
    echo -e "${YELLOW}🔍 Temporary files preserved for inspection:${NC}"
    echo -e "${YELLOW}   - AppDir/ (embedded Python environment)${NC}"
    echo -e "${YELLOW}   - AppImageBuilder.yml (build recipe)${NC}"
fi
echo -e "${GREEN}🚀 Test with: ./dist-appimage/${EXPECTED_NAME}${NC}"
echo -e "${YELLOW}💡 Tip: Add to .gitignore: dist-appimage/ AppDir/ AppImageBuilder.yml${NC}"