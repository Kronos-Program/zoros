#!/usr/bin/env bash
"""
Coder Environment Setup Script

This script creates and configures the Python virtual environment used by Coder
for development work. It handles environment creation, dependency installation,
and validation of key packages.

Features:
- Virtual environment creation and management
- Smart dependency installation (only if missing)
- Package validation and verification
- Detailed logging and error handling
- Breadcrumb file creation for agent detection
- Cross-platform compatibility

Usage:
    ./scripts/environment/setup_coder_env.sh

Dependencies:
    - Python 3.x
    - pip
    - bash shell

See architecture: docs/zoros_architecture.md#component-overview
"""

# Fail fast and show commands as they are executed.
set -euo pipefail
set -x
trap 'echo "[setup_coder_env] Error on line $LINENO" >&2' ERR

SCRIPT_DIR=$(dirname "$0")
ROOT_DIR=$(cd "$SCRIPT_DIR/../.." && pwd)
VENV="$ROOT_DIR/coder-env"

# Print helpful context for debugging
echo "[setup_coder_env] SCRIPT_DIR=$SCRIPT_DIR"
echo "[setup_coder_env] ROOT_DIR=$ROOT_DIR"
echo "[setup_coder_env] VENV path=$VENV"

if [ ! -f "$VENV/bin/activate" ]; then
    echo "[setup_coder_env] Creating virtual environment at $VENV"
    python3 -m venv "$VENV"
else
    echo "[setup_coder_env] Reusing existing virtual environment"
fi

echo "[setup_coder_env] Activating $VENV"
. "$VENV/bin/activate"

# Only install packages if they're missing to avoid unnecessary
# network access when the repo already contains a pre-built venv.
if ! python3 - <<'PY'
import importlib.util, sys
missing = [pkg for pkg in ("openai", "fastapi", "pydantic")
           if importlib.util.find_spec(pkg) is None]
sys.exit(1 if missing else 0)
PY
then
    echo "[setup_coder_env] Installing dependencies"
    pip install -r "$VENV/requirements.txt"
else
    echo "[setup_coder_env] Dependencies already satisfied"
fi

python3 - <<'PY'
import importlib
for pkg in ("openai", "fastapi"):
    importlib.import_module(pkg)
PY
echo "[setup_coder_env] Coder environment ready"

# Write breadcrumb so agents can detect that the backend environment is ready
mkdir -p "$ROOT_DIR/env"
touch "$ROOT_DIR/env/BACKEND_READY" 