#!/bin/zsh
"""
Zoros Environment Setup and Testing Script

This script sets up the complete Zoros development environment by making
activation scripts executable and testing the environment functionality.
It provides comprehensive validation of key packages and clear feedback
on the setup status.

Features:
- Script permission management
- Environment activation testing
- Package availability verification
- User-friendly feedback and instructions
- Integration with activation scripts

Usage:
    ./scripts/environment/setup_environment.sh

Dependencies:
    - activate_env.sh
    - activate_zoros.sh
    - zsh shell
    - Python with required packages
"""

# Setup script for zoros environment
# This script makes activation scripts executable and tests the environment

echo "Setting up zoros environment..."

# Make scripts executable
chmod +x scripts/environment/activate_env.sh
chmod +x scripts/environment/activate_zoros.sh
chmod +x scripts/environment/setup_environment.sh

echo "✅ Made scripts executable"

# Test the environment activation
echo "Testing environment activation..."

# Source the activation script
source scripts/environment/activate_zoros.sh

# Test if key packages are available
echo "Testing key packages..."

if python -c "import streamlit; print('✅ Streamlit available')" 2>/dev/null; then
    echo "✅ Streamlit is working"
else
    echo "❌ Streamlit not found"
fi

if python -c "import torch; print('✅ PyTorch available')" 2>/dev/null; then
    echo "✅ PyTorch is working"
else
    echo "❌ PyTorch not found"
fi

if python -c "import openai; print('✅ OpenAI available')" 2>/dev/null; then
    echo "✅ OpenAI is working"
else
    echo "❌ OpenAI not found"
fi

echo "Setup complete! You can now:"
echo "1. Open Cursor in this project directory"
echo "2. The zoros environment should activate automatically"
echo "3. Or manually run: source scripts/environment/activate_zoros.sh" 