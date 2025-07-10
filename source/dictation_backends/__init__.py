"""
Dictation Backends Module

This module provides a robust backend system for dictation/transcription with graceful
handling of missing dependencies. Instead of importing all backends directly, it uses
a registry system that only loads backends that are actually available.

Usage:
    from source.dictation_backends import get_backend_class, get_available_backends
    
    # Get available backends
    available = get_available_backends()
    
    # Get a specific backend class
    backend_class = get_backend_class("MLXWhisper")
    backend = backend_class()
"""

# Import the registry system and utilities
from .registry import (
    get_backend_registry,
    get_backend_class,
    list_available_backends,
    is_backend_available,
    reset_registry,
)
from .utils import get_available_backends, is_macos, check_backend

# For backward compatibility, provide the old function names
def get_available_backends():
    """Get available backends (backward compatibility)."""
    return list_available_backends()

# Expose the registry for advanced usage
def get_registry():
    """Get the backend registry instance."""
    return get_backend_registry()

__all__ = [
    # New registry-based functions
    "get_backend_class",
    "list_available_backends", 
    "is_backend_available",
    "get_backend_registry",
    "reset_registry",
    
    # Backward compatibility functions
    "get_available_backends",
    "check_backend",
    "is_macos",
    
    # Advanced usage
    "get_registry",
]
