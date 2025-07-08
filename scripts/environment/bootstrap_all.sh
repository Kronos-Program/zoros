#!/usr/bin/env bash
"""
Bootstrap Complete Zoros Development Environment

This script orchestrates the setup of both backend and frontend environments
for the Zoros project. It runs the necessary setup scripts in the correct order
and provides comprehensive error handling and debugging output.

Features:
- Complete environment setup (backend + frontend)
- Debug output for troubleshooting
- Error handling with line number reporting
- Breadcrumb file creation for agent detection
- Sequential execution of setup scripts

Usage:
    ./scripts/environment/bootstrap_all.sh

Dependencies:
    - setup_backend_env.sh
    - setup_frontend_env.sh
    - bash shell

See architecture: docs/zoros_architecture.md#component-overview
"""

# Run both backend and frontend setup steps with debug output.
set -euo pipefail
set -x
trap 'echo "[bootstrap_all] Error on line $LINENO" >&2' ERR

SCRIPT_DIR=$(dirname "$0")
ROOT_DIR=$(cd "$SCRIPT_DIR/../.." && pwd)

# Write breadcrumb so agents detect that the full stack is ready
mkdir -p "$ROOT_DIR/env"
touch "$ROOT_DIR/env/FULLSTACK_READY"

echo "[bootstrap_all] Running backend setup via $SCRIPT_DIR/setup_backend_env.sh"
"$SCRIPT_DIR/setup_backend_env.sh"

echo "[bootstrap_all] Running frontend setup via $SCRIPT_DIR/setup_frontend_env.sh"
"$SCRIPT_DIR/setup_frontend_env.sh"

echo "[bootstrap_all] Bootstrap complete" 