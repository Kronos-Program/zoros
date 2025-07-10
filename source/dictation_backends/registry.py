"""
Robust Backend Registry for Dictation Backends

This module provides a dynamic backend registry that gracefully handles missing dependencies
and only loads backends that are actually available on the current system.

The registry uses try/except loading to ensure that:
1. Missing dependencies don't crash the system
2. Only available backends are registered
3. Clear error messages are provided when requested backends are unavailable
4. The system degrades gracefully when no backends are available

Usage:
    from source.dictation_backends.registry import get_backend_registry
    
    registry = get_backend_registry()
    available_backends = registry.list_available_backends()
    backend_class = registry.get_backend_class("MLXWhisper")
"""

from __future__ import annotations

import importlib
import logging
from typing import Dict, List, Optional, Type, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class BackendInfo:
    """Information about a dictation backend."""
    name: str
    class_name: str
    module_path: str
    dependencies: List[str]
    description: str
    platform_requirements: Optional[List[str]] = None


class BackendRegistry:
    """Dynamic registry for dictation backends with graceful dependency handling."""
    
    def __init__(self):
        self._registered_backends: Dict[str, Type[Any]] = {}
        self._backend_info: Dict[str, BackendInfo] = {}
        self._failed_backends: Dict[str, str] = {}
        self._initialized = False
    
    def _get_backend_definitions(self) -> List[BackendInfo]:
        """Define all known backends with their dependencies."""
        return [
            BackendInfo(
                name="WhisperCPP",
                class_name="WhisperCPPBackend",
                module_path="source.dictation_backends.whisper_cpp_backend",
                dependencies=["whispercpp"],
                description="Whisper.cpp backend with C++ optimization",
                platform_requirements=["whisper-cli executable or whispercpp module"]
            ),
            BackendInfo(
                name="FasterWhisper",
                class_name="FasterWhisperBackend", 
                module_path="source.dictation_backends.faster_whisper_backend",
                dependencies=["faster_whisper", "torch"],
                description="Faster Whisper backend with MPS acceleration",
                platform_requirements=["macOS with MPS support"]
            ),
            BackendInfo(
                name="StandardOpenAIWhisper",
                class_name="StandardOpenAIWhisperBackend",
                module_path="source.dictation_backends.standard_whisper_backend",
                dependencies=["whisper"],
                description="Standard OpenAI Whisper backend"
            ),
            BackendInfo(
                name="OpenAIAPI",
                class_name="OpenAIAPIBackend",
                module_path="source.dictation_backends.openai_api_backend",
                dependencies=["openai"],
                description="OpenAI API backend for cloud transcription",
                platform_requirements=["OPENAI_API_KEY environment variable"]
            ),
            BackendInfo(
                name="MLXWhisper",
                class_name="MLXWhisperBackend",
                module_path="source.dictation_backends.mlx_whisper_backend",
                dependencies=["mlx_whisper"],
                description="MLX Whisper backend for Apple Silicon",
                platform_requirements=["macOS with Apple Silicon"]
            ),
            BackendInfo(
                name="LiveMLXWhisper",
                class_name="LiveMLXWhisperBackend",
                module_path="source.dictation_backends.live_mlx_whisper_backend",
                dependencies=["mlx_whisper"],
                description="Live MLX Whisper backend for real-time transcription",
                platform_requirements=["macOS with Apple Silicon"]
            ),
            BackendInfo(
                name="ParallelMLXWhisper",
                class_name="ParallelMLXWhisperBackend",
                module_path="source.dictation_backends.parallel_mlx_whisper_backend",
                dependencies=["mlx_whisper"],
                description="Parallel MLX Whisper backend for concurrent processing",
                platform_requirements=["macOS with Apple Silicon"]
            ),
            BackendInfo(
                name="QueueBasedStreamingMLXWhisper",
                class_name="QueueBasedStreamingBackend",
                module_path="source.dictation_backends.queue_based_streaming_backend",
                dependencies=["mlx_whisper"],
                description="Queue-based streaming MLX Whisper backend",
                platform_requirements=["macOS with Apple Silicon"]
            ),
            BackendInfo(
                name="RealtimeStreamingMLXWhisper",
                class_name="RealtimeStreamingBackend",
                module_path="source.dictation_backends.realtime_streaming_backend",
                dependencies=["mlx_whisper"],
                description="Real-time streaming MLX Whisper backend",
                platform_requirements=["macOS with Apple Silicon"]
            ),
            BackendInfo(
                name="Mock",
                class_name="MockBackend",
                module_path="source.dictation_backends.mock_backend",
                dependencies=[],
                description="Mock backend for testing and development"
            ),
        ]
    
    def _try_load_backend(self, backend_info: BackendInfo) -> Optional[Type[Any]]:
        """Try to load a backend class, returning None if it fails."""
        try:
            # Import the module
            module = importlib.import_module(backend_info.module_path)
            backend_class = getattr(module, backend_info.class_name)
            
            # For certain backends, do additional validation
            if backend_info.name == "OpenAIAPI":
                import os
                if not os.getenv("OPENAI_API_KEY"):
                    raise ImportError("OPENAI_API_KEY environment variable not set")
            
            # Test that the backend can be instantiated (basic validation)
            # This is a minimal check - the actual backend validation happens in check_backend
            logger.info(f"Successfully loaded backend: {backend_info.name}")
            return backend_class
            
        except Exception as e:
            error_msg = f"Failed to load {backend_info.name}: {str(e)}"
            logger.debug(error_msg)
            self._failed_backends[backend_info.name] = error_msg
            return None
    
    def _initialize_registry(self) -> None:
        """Initialize the registry by attempting to load all backends."""
        if self._initialized:
            return
        
        logger.info("Initializing backend registry...")
        backend_definitions = self._get_backend_definitions()
        
        for backend_info in backend_definitions:
            self._backend_info[backend_info.name] = backend_info
            backend_class = self._try_load_backend(backend_info)
            
            if backend_class is not None:
                self._registered_backends[backend_info.name] = backend_class
        
        available_count = len(self._registered_backends)
        failed_count = len(self._failed_backends)
        
        if available_count == 0:
            logger.warning("No dictation backends are available! This may indicate missing dependencies.")
        else:
            logger.info(f"Backend registry initialized: {available_count} available, {failed_count} failed")
        
        self._initialized = True
    
    def list_available_backends(self) -> List[str]:
        """Return a list of backend names that are available on this system."""
        self._initialize_registry()
        return list(self._registered_backends.keys())
    
    def get_backend_class(self, backend_name: str) -> Type[Any]:
        """Get a backend class by name, raising an error if not available."""
        self._initialize_registry()
        
        if backend_name not in self._registered_backends:
            if backend_name in self._failed_backends:
                error_msg = f"Backend '{backend_name}' is not available: {self._failed_backends[backend_name]}"
                raise ImportError(error_msg)
            else:
                available = ", ".join(self._registered_backends.keys())
                raise ValueError(f"Unknown backend '{backend_name}'. Available backends: {available}")
        
        return self._registered_backends[backend_name]
    
    def get_backend_info(self, backend_name: str) -> Optional[BackendInfo]:
        """Get information about a backend, whether it's available or not."""
        self._initialize_registry()
        return self._backend_info.get(backend_name)
    
    def is_backend_available(self, backend_name: str) -> bool:
        """Check if a backend is available."""
        self._initialize_registry()
        return backend_name in self._registered_backends
    
    def get_failed_backends(self) -> Dict[str, str]:
        """Get a dictionary of failed backends and their error messages."""
        self._initialize_registry()
        return self._failed_backends.copy()
    
    def get_backend_status(self) -> Dict[str, Any]:
        """Get a comprehensive status report of all backends."""
        self._initialize_registry()
        
        status = {
            "available": [],
            "failed": [],
            "total_defined": len(self._backend_info),
            "total_available": len(self._registered_backends),
            "total_failed": len(self._failed_backends)
        }
        
        for name, info in self._backend_info.items():
            if name in self._registered_backends:
                status["available"].append({
                    "name": name,
                    "description": info.description,
                    "dependencies": info.dependencies,
                    "platform_requirements": info.platform_requirements
                })
            else:
                status["failed"].append({
                    "name": name,
                    "description": info.description,
                    "dependencies": info.dependencies,
                    "platform_requirements": info.platform_requirements,
                    "error": self._failed_backends.get(name, "Unknown error")
                })
        
        return status


# Global registry instance
_registry_instance: Optional[BackendRegistry] = None


def get_backend_registry() -> BackendRegistry:
    """Get the global backend registry instance."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = BackendRegistry()
    return _registry_instance


def reset_registry() -> None:
    """Reset the global registry instance (primarily for testing)."""
    global _registry_instance
    _registry_instance = None


# Convenience functions for backward compatibility
def list_available_backends() -> List[str]:
    """Return a list of backend names that are available on this system."""
    return get_backend_registry().list_available_backends()


def get_backend_class(backend_name: str) -> Type[Any]:
    """Get a backend class by name, raising an error if not available."""
    return get_backend_registry().get_backend_class(backend_name)


def is_backend_available(backend_name: str) -> bool:
    """Check if a backend is available."""
    return get_backend_registry().is_backend_available(backend_name)