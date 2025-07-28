from __future__ import annotations

import importlib
import importlib.util
import shutil
import sys
import os
from pathlib import Path
from typing import List

# Import the new registry system
from .registry import get_backend_registry


def is_macos() -> bool:
    """Return True if running on macOS."""
    return sys.platform == "darwin"


def _has_module(name: str) -> bool:
    spec = importlib.util.find_spec(name)
    return spec is not None


def get_available_backends() -> List[str]:
    """Detect available whisper backends for the current platform.
    
    This function now uses the robust backend registry system that handles
    missing dependencies gracefully.
    """
    registry = get_backend_registry()
    return registry.list_available_backends()


def check_backend(name: str) -> bool:
    """Return True if the backend can be initialized.
    
    This function now uses the robust backend registry system that handles
    missing dependencies gracefully.
    """
    registry = get_backend_registry()
    return registry.is_backend_available(name)
