"""ZorOS Plugin System

This module provides the core plugin architecture using Pluggy.
Supports dynamic loading of plugins for:
- Language models and backends
- Audio processing and TTS
- Document processing and fiberization
- Agentic frameworks and orchestration
- Research and semantic search tools

Architecture:
- Hook specifications define plugin interfaces
- Plugin manager handles discovery and lifecycle
- Plugins register via entry points or direct installation
"""

from .hooks import hookspec
from .manager import PluginManager
from .base import ZorosPlugin

__all__ = ["hookspec", "PluginManager", "ZorosPlugin"]