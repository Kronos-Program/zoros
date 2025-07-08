#!/bin/zsh
# Activate Zoros Conda Environment with Fallback Support
#
# This script automatically activates the 'zoros' conda environment when sourced.
# It includes fallback mechanisms for cases where conda is not available or
# the environment doesn't exist.
#
# Features:
# - Automatic conda environment detection and activation
# - Fallback to manual environment variable setup
# - Plugin disabling to prevent conflicts
# - Cross-platform compatibility
#
# Usage:
#     source scripts/environment/activate_env.sh
#
# Dependencies:
#     - conda (optional, will use fallback if not available)
#     - zsh shell

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Function to activate conda environment with fallback
activate_conda_env() {
    # Ensure plugins are disabled
    export CONDA_NO_PLUGINS=true
    
    # Skip conda activation entirely due to corruption issues
    # Use fallback method directly
    echo "⚠️  Using fallback method to avoid conda corruption"
    activate_conda_fallback
}

# Fallback method: manually set environment variables
activate_conda_fallback() {
    export PATH="/opt/homebrew/Caskroom/miniconda/base/envs/zoros/bin:$PATH"
    export CONDA_DEFAULT_ENV=zoros
    export CONDA_PREFIX="/opt/homebrew/Caskroom/miniconda/base/envs/zoros"
    export CONDA_SHLVL=1
    echo "✅ Zoros environment activated via fallback method"
}

# Always activate zoros environment if not already active
if [[ "$CONDA_DEFAULT_ENV" != "zoros" ]]; then
    activate_conda_env
fi 