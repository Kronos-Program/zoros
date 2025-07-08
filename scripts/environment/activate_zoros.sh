#!/bin/zsh
"""
Simple Zoros Environment Activation Script

This script provides a straightforward way to activate the zoros conda environment
by directly setting the necessary environment variables. It's designed to be
simple and reliable, bypassing potential conda initialization issues.

Features:
- Direct environment variable manipulation
- No dependency on conda initialization
- Clear feedback on activation status
- Python path and version verification

Usage:
    source scripts/environment/activate_zoros.sh

Dependencies:
    - zsh shell
    - Python installation in the zoros environment
"""

echo "Activating zoros environment..."

# Disable problematic plugins
export CONDA_NO_PLUGINS=true

# Set environment variables directly
export PATH="/opt/homebrew/Caskroom/miniconda/base/envs/zoros/bin:$PATH"
export CONDA_DEFAULT_ENV=zoros
export CONDA_PREFIX="/opt/homebrew/Caskroom/miniconda/base/envs/zoros"
export CONDA_SHLVL=1

echo "✅ Zoros environment activated!"
echo "Python path: $(which python)"
echo "Python version: $(python --version)" 