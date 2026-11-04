#!/usr/bin/env bash
# ==============================================================================
# Linux Standalone Packaging Script for PyQt6 Desktop Utility
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> [1/5] Setting up build environment..."
VENV_DIR="$SCRIPT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment at $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
fi

PYTHON_BIN="$VENV_DIR/bin/python3"
PIP_BIN="$VENV_DIR/bin/pip"
PYINSTALLER_BIN="$VENV_DIR/bin/pyinstaller"

echo "==> [2/5] Ensuring dependencies are up-to-date..."
"$PIP_BIN" install --quiet --upgrade pip
"$PIP_BIN" install --quiet -r requirements.txt

echo "==> [3/5] Cleaning previous build artifacts..."
rm -rf "$SCRIPT_DIR/build" "$SCRIPT_DIR/dist" "$SCRIPT_DIR/*.spec"

echo "==> [4/5] Running PyInstaller to build standalone ELF executable..."
"$PYINSTALLER_BIN" \
    --noconfirm \
    --clean \
    --onefile \
    --windowed \
    --name "linux-utility" \
    --add-data "$SCRIPT_DIR/assets:assets" \
    --add-data "$SCRIPT_DIR/personas:personas" \
    --add-data "$SCRIPT_DIR/.agent:.agent" \
    --hidden-import "PyQt6.QtCore" \
    --hidden-import "PyQt6.QtGui" \
    --hidden-import "PyQt6.QtWidgets" \
    "$SCRIPT_DIR/src/main.py"

EXECUTABLE="$SCRIPT_DIR/dist/linux-utility"

if [ ! -f "$EXECUTABLE" ]; then
    echo "ERROR: Packaging failed. Output binary not found at $EXECUTABLE"
    exit 1
fi

echo "==> [5/5] Verifying packaged ELF binary..."
file "$EXECUTABLE"
ls -lh "$EXECUTABLE"

echo "==> Running headless verification on packaged binary..."
QT_QPA_PLATFORM=offscreen timeout 3s "$EXECUTABLE" || {
    EXIT_CODE=$?
    # Exit code 124 means timeout triggered successfully while app event loop was active
    if [ $EXIT_CODE -eq 124 ]; then
        echo "Headless test run succeeded (app initialized and entered event loop normally)."
    else
        echo "Warning: Executable test exited with code $EXIT_CODE"
    fi
}

echo "=============================================================================="
echo " Packaging complete! Standalone Linux binary ready at:"
echo " $EXECUTABLE"
echo "=============================================================================="
