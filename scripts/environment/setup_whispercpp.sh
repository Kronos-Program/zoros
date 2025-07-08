#!/usr/bin/env bash
"""
Whisper.cpp Setup and Build Script

This script sets up and builds the whisper.cpp library for speech recognition
functionality in the Zoros project. It handles cloning, building, and Python
wrapper installation with cross-platform support.

Features:
- Git repository cloning and updating
- Cross-platform CPU core detection
- Parallel build optimization
- Python wrapper installation
- Error handling and logging
- Environment variable support

Usage:
    ./scripts/environment/setup_whispercpp.sh

Dependencies:
    - git
    - make
    - python3 (optional, for wrapper installation)
    - bash shell

Environment Variables:
    - WHISPER_CPP_DIR: Custom whisper.cpp directory path (optional)

See architecture: docs/zoros_architecture.md#component-overview
"""

set -euo pipefail
set -x
trap 'echo "[setup_whispercpp] Error on line $LINENO" >&2' ERR

SCRIPT_DIR=$(dirname "$0")
ROOT_DIR=$(cd "$SCRIPT_DIR/../.." && pwd)

if [ -n "${WHISPER_CPP_DIR:-}" ]; then
    echo "[setup_whispercpp] Using existing whisper.cpp directory: $WHISPER_CPP_DIR"
    WHISPER_DIR="$WHISPER_CPP_DIR"
else
    WHISPER_DIR="$ROOT_DIR/whisper.cpp"
fi

if ! command -v git >/dev/null; then
    echo "git is required to clone whisper.cpp" >&2
    exit 1
fi

if [ ! -d "$WHISPER_DIR" ]; then
    echo "[setup_whispercpp] Cloning whisper.cpp"
    git clone https://github.com/ggerganov/whisper.cpp "$WHISPER_DIR"
else
    echo "[setup_whispercpp] Updating existing whisper.cpp clone"
    (cd "$WHISPER_DIR" && git pull --ff-only)
fi

cd "$WHISPER_DIR"

# Get number of CPU cores in a cross-platform way
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    CORES=$(sysctl -n hw.ncpu)
else
    # Linux
    CORES=$(nproc)
fi

make -j "$CORES"

echo "[setup_whispercpp] Build complete"

# Install Python wrapper if bindings are available
if command -v python3 >/dev/null; then
    echo "[setup_whispercpp] Installing Python wrapper"
    python3 -m pip install --upgrade pip setuptools wheel --break-system-packages
    python3 -m pip install git+https://github.com/AIWintermuteAI/whispercpp.git --break-system-packages
else
    echo "[setup_whispercpp] python3 not found; skipping Python wrapper installation" >&2
fi 