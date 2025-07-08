"""Demo Plugin for ZorOS

A simple example plugin to demonstrate the plugin architecture.
"""

from typing import Dict, Any, List
from source.plugins.base import ZorosPlugin
import logging

logger = logging.getLogger(__name__)


class DemoPlugin(ZorosPlugin):
    """A demonstration plugin showing basic plugin functionality."""
    
    @property
    def name(self) -> str:
        return "Demo Plugin"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "A demonstration plugin for testing the ZorOS plugin system"
    
    def initialize(self, plugin_manager: Any) -> None:
        """Initialize the demo plugin."""
        logger.info(f"Initializing {self.name}")
        
        # Register a simple language backend for demonstration
        plugin_manager.register_language_backend("demo_llm", DemoLanguageBackend)
        
        # Register UI components
        self._register_ui_components(plugin_manager)
    
    def _register_ui_components(self, plugin_manager: Any) -> None:
        """Register UI components for this plugin."""
        # This would register UI panels, CLI commands, etc.
        logger.info("Demo plugin UI components registered")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the demo plugin."""
        return {
            "name": self.name,
            "version": self.version,
            "status": "healthy",
            "details": {
                "demo_backend_available": True,
                "last_check": "2025-01-05T00:00:00Z"
            }
        }


class DemoLanguageBackend:
    """A demo language backend for testing."""
    
    def __init__(self):
        self.name = "demo_llm"
        self.description = "Demo LLM backend for testing"
    
    def complete_turn(self, prompt: str, context: Dict[str, Any]) -> str:
        """Complete a turn with a simple demo response."""
        return f"Demo response to: {prompt[:50]}..."
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Return available demo models."""
        return [
            {
                "name": "demo-model-1",
                "description": "Demo model for testing",
                "context_length": 4096,
                "capabilities": ["text-completion"]
            }
        ]