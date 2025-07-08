#!/usr/bin/env bash
"""
Backend Environment Setup Script

This script sets up the complete backend development environment for the Zoros project.
It handles Python virtual environment creation, dependency installation, and
environment activation for backend development work.

Features:
- Virtual environment setup and activation
- Python dependency installation
- Error handling with detailed logging
- Integration with coder environment setup
- Breadcrumb file creation for agent detection

Usage:
    ./scripts/environment/setup_backend_env.sh

Dependencies:
    - setup_coder_env.sh
    - requirements.txt
    - bash shell

See architecture: docs/zoros_architecture.md#component-overview
"""

# Exit early on failure and emit the executed commands for traceability.
set -euo pipefail
set -x
trap 'echo "[setup_backend_env] Error on line $LINENO" >&2' ERR

SCRIPT_DIR=$(dirname "$0")
ROOT_DIR=$(cd "$SCRIPT_DIR/../.." && pwd)

echo "[setup_backend_env] Running setup_coder_env.sh"
"$SCRIPT_DIR/setup_coder_env.sh"

echo "[setup_backend_env] Activating backend virtual environment"
. "$ROOT_DIR/coder-env/bin/activate"

echo "[setup_backend_env] Installing system dependencies"
if command -v apt-get >/dev/null; then
    sudo apt-get update -y
    # For sounddevice / PortAudio and PySide WebEngine
    sudo apt-get install -y portaudio19-dev libasound2-dev libegl1 libgl1-mesa-dev
else
    echo "[setup_backend_env] apt-get not found; please install PortAudio and Qt dependencies manually" >&2
fi

echo "[setup_backend_env] Installing backend requirements from $ROOT_DIR/requirements.txt"
pip install -r "$ROOT_DIR/requirements.txt"

echo "[setup_backend_env] Backend environment ready" 