#!/usr/bin/env bash
"""
Frontend Environment Setup Script

This script sets up the frontend development environment for the Zoros project
by installing npm dependencies in the zoros-frontend directory. It provides
comprehensive error handling and logging for troubleshooting.

Features:
- npm dependency installation
- Directory existence validation
- Error handling with line number reporting
- Breadcrumb file creation for agent detection
- Cross-platform compatibility

Usage:
    ./scripts/environment/setup_frontend_env.sh

Dependencies:
    - npm
    - bash shell
    - zoros-frontend directory (optional)

See architecture: docs/zoros_architecture.md#component-overview
"""

# Provide verbose output for troubleshooting.
set -euo pipefail
set -x
trap 'echo "[setup_frontend_env] Error on line $LINENO" >&2' ERR

SCRIPT_DIR=$(dirname "$0")
ROOT_DIR=$(cd "$SCRIPT_DIR/../.." && pwd)

if [ -d "$ROOT_DIR/zoros-frontend" ]; then
    echo "[setup_frontend_env] Installing npm packages in $ROOT_DIR/zoros-frontend"
    cd "$ROOT_DIR/zoros-frontend"
    npm install
    echo "[setup_frontend_env] Frontend environment ready"
else
    echo "[setup_frontend_env] No zoros-frontend directory found." >&2
fi

# Write breadcrumb so agents detect that the frontend environment is ready
mkdir -p "$ROOT_DIR/env"
touch "$ROOT_DIR/env/FRONTEND_READY" 