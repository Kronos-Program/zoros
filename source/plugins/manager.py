"""Plugin Manager for ZorOS

Handles plugin discovery, loading, and lifecycle management using Pluggy.
"""

import pluggy
import importlib
import importlib.metadata
import logging
from typing import Dict, List, Any, Optional, Type
from pathlib import Path
import traceback

from .hooks import ZorosHookSpec
from .base import ZorosPlugin

logger = logging.getLogger(__name__)


class PluginManager:
    """Manages ZorOS plugins using Pluggy framework."""
    
    def __init__(self):
        """Initialize the plugin manager."""
        # Create pluggy plugin manager
        self.pm = pluggy.PluginManager("zoros")
        self.pm.add_hookspecs(ZorosHookSpec)
        
        # Plugin registry
        self.loaded_plugins: Dict[str, ZorosPlugin] = {}
        self.plugin_configs: Dict[str, Dict[str, Any]] = {}
        
        # Backend registries
        self.language_backends: Dict[str, Any] = {}
        self.transcription_backends: Dict[str, Any] = {}
        self.tts_backends: Dict[str, Any] = {}
        self.document_processors: Dict[str, Any] = {}
        self.agents: Dict[str, Any] = {}
        self.search_backends: Dict[str, Any] = {}
        self.orchestrators: Dict[str, Any] = {}
        self.research_tools: Dict[str, Any] = {}
        
        logger.info("Plugin manager initialized")
    
    def discover_plugins(self) -> None:
        """Discover plugins via entry points and direct imports."""
        logger.info("Discovering plugins...")
        
        # Discover via entry points
        self._discover_entry_point_plugins()
        
        # Discover in plugins directory
        self._discover_directory_plugins()
        
        # Load built-in plugins
        self._load_builtin_plugins()
        
        logger.info(f"Discovered {len(self.loaded_plugins)} plugins")
    
    def _discover_entry_point_plugins(self) -> None:
        """Discover plugins via setuptools entry points."""
        try:
            # Look for zoros.plugins entry points
            entry_points = importlib.metadata.entry_points(group="zoros.plugins")
            
            for entry_point in entry_points:
                try:
                    plugin_class = entry_point.load()
                    plugin_instance = plugin_class()
                    
                    if isinstance(plugin_instance, ZorosPlugin):
                        self._register_plugin(plugin_instance)
                        logger.info(f"Loaded entry point plugin: {plugin_instance.name}")
                    else:
                        logger.warning(f"Entry point {entry_point.name} does not inherit from ZorosPlugin")
                
                except Exception as e:
                    logger.error(f"Failed to load entry point plugin {entry_point.name}: {e}")
                    logger.debug(traceback.format_exc())
        
        except Exception as e:
            logger.debug(f"No entry points found or error accessing them: {e}")
    
    def _discover_directory_plugins(self) -> None:
        """Discover plugins in the plugins directory."""
        # Look for plugins in the current project
        plugins_dir = Path(__file__).parent.parent.parent / "zoros_plugins"
        
        if not plugins_dir.exists():
            logger.debug(f"Plugins directory not found: {plugins_dir}")
            return
        
        for plugin_dir in plugins_dir.iterdir():
            if plugin_dir.is_dir() and not plugin_dir.name.startswith('.'):
                self._load_directory_plugin(plugin_dir)
    
    def _load_directory_plugin(self, plugin_dir: Path) -> None:
        """Load a plugin from a directory."""
        try:
            # Look for plugin.py or __init__.py
            plugin_file = plugin_dir / "plugin.py"
            if not plugin_file.exists():
                plugin_file = plugin_dir / "__init__.py"
                if not plugin_file.exists():
                    logger.debug(f"No plugin.py or __init__.py found in {plugin_dir}")
                    return
            
            # Import the plugin module
            import sys
            if str(plugin_dir.parent) not in sys.path:
                sys.path.insert(0, str(plugin_dir.parent))
            
            module = importlib.import_module(plugin_dir.name)
            
            # Look for plugin classes
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    issubclass(attr, ZorosPlugin) and 
                    attr != ZorosPlugin):
                    
                    plugin_instance = attr()
                    self._register_plugin(plugin_instance)
                    logger.info(f"Loaded directory plugin: {plugin_instance.name}")
                    break
        
        except Exception as e:
            logger.error(f"Failed to load directory plugin {plugin_dir}: {e}")
            logger.debug(traceback.format_exc())
    
    def _register_plugin(self, plugin: ZorosPlugin) -> None:
        """Register a plugin instance."""
        if plugin.name in self.loaded_plugins:
            logger.warning(f"Plugin {plugin.name} already loaded, skipping")
            return
        
        try:
            # Initialize the plugin
            plugin.initialize(self)
            
            # Register with pluggy
            self.pm.register(plugin)
            
            # Store in registry
            self.loaded_plugins[plugin.name] = plugin
            
            logger.info(f"Registered plugin: {plugin.name} v{plugin.version}")
            
        except Exception as e:
            logger.error(f"Failed to register plugin {plugin.name}: {e}")
            logger.debug(traceback.format_exc())
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a plugin."""
        if plugin_name not in self.loaded_plugins:
            logger.warning(f"Plugin {plugin_name} not loaded")
            return False
        
        try:
            plugin = self.loaded_plugins[plugin_name]
            
            # Cleanup
            plugin.cleanup()
            
            # Unregister from pluggy
            self.pm.unregister(plugin)
            
            # Remove from registry
            del self.loaded_plugins[plugin_name]
            
            logger.info(f"Unloaded plugin: {plugin_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unload plugin {plugin_name}: {e}")
            return False
    
    def _load_builtin_plugins(self) -> None:
        """Load built-in plugins from zoros_plugins directory."""
        try:
            # Docker plugin
            try:
                from zoros_plugins.docker_plugin import DockerPlugin
                self._register_plugin(DockerPlugin())
                logger.info("Loaded Docker plugin")
            except ImportError as e:
                logger.debug(f"Docker plugin not available: {e}")
            
            # OpenWebUI plugin
            try:
                from zoros_plugins.openwebui_plugin import OpenWebUIPlugin
                self._register_plugin(OpenWebUIPlugin())
                logger.info("Loaded OpenWebUI plugin")
            except ImportError as e:
                logger.debug(f"OpenWebUI plugin not available: {e}")
            
            # LangChain plugin
            try:
                from zoros_plugins.langchain_plugin import LangChainPlugin
                self._register_plugin(LangChainPlugin())
                logger.info("Loaded LangChain plugin")
            except ImportError as e:
                logger.debug(f"LangChain plugin not available: {e}")
            
            # Agent-Zero plugin
            try:
                from zoros_plugins.agent_zero_plugin import AgentZeroPlugin
                self._register_plugin(AgentZeroPlugin())
                logger.info("Loaded Agent-Zero plugin")
            except ImportError as e:
                logger.debug(f"Agent-Zero plugin not available: {e}")
                
        except Exception as e:
            logger.error(f"Error loading built-in plugins: {e}")
    
    def get_plugin(self, plugin_name: str) -> Optional[ZorosPlugin]:
        """Get a loaded plugin by name."""
        return self.loaded_plugins.get(plugin_name)
    
    def list_plugins(self) -> List[Dict[str, Any]]:
        """List all loaded plugins."""
        return [
            {
                "name": plugin.name,
                "version": plugin.version,
                "description": plugin.description,
                "health": plugin.get_health_status()
            }
            for plugin in self.loaded_plugins.values()
        ]
    
    def get_plugin_health(self) -> Dict[str, Dict[str, Any]]:
        """Get health status of all plugins."""
        return {
            name: plugin.get_health_status()
            for name, plugin in self.loaded_plugins.items()
        }
    
    # Backend registration methods (called by plugins)
    
    def register_language_backend(self, backend_name: str, backend_class: Any) -> None:
        """Register a language backend."""
        self.language_backends[backend_name] = backend_class
        logger.info(f"Registered language backend: {backend_name}")
    
    def register_transcription_backend(self, backend_name: str, backend_class: Any) -> None:
        """Register a transcription backend."""
        self.transcription_backends[backend_name] = backend_class
        logger.info(f"Registered transcription backend: {backend_name}")
    
    def register_tts_backend(self, backend_name: str, backend_class: Any) -> None:
        """Register a TTS backend."""
        self.tts_backends[backend_name] = backend_class
        logger.info(f"Registered TTS backend: {backend_name}")
    
    def register_document_processor(self, processor_name: str, processor_class: Any) -> None:
        """Register a document processor."""
        self.document_processors[processor_name] = processor_class
        logger.info(f"Registered document processor: {processor_name}")
    
    def register_agent(self, agent_name: str, agent_class: Any) -> None:
        """Register an agent."""
        self.agents[agent_name] = agent_class
        logger.info(f"Registered agent: {agent_name}")
    
    def register_search_backend(self, backend_name: str, backend_class: Any) -> None:
        """Register a search backend."""
        self.search_backends[backend_name] = backend_class
        logger.info(f"Registered search backend: {backend_name}")
    
    def register_orchestrator(self, orchestrator_name: str, orchestrator_class: Any) -> None:
        """Register an orchestrator."""
        self.orchestrators[orchestrator_name] = orchestrator_class
        logger.info(f"Registered orchestrator: {orchestrator_name}")
    
    def register_research_tool(self, tool_name: str, tool_class: Any) -> None:
        """Register a research tool."""
        self.research_tools[tool_name] = tool_class
        logger.info(f"Registered research tool: {tool_name}")
    
    # Hook calling methods
    
    def call_hook(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """Call a plugin hook and return all results."""
        try:
            return self.pm.hook.__getattr__(hook_name)(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error calling hook {hook_name}: {e}")
            return []
    
    def call_hook_first_result(self, hook_name: str, *args, **kwargs) -> Optional[Any]:
        """Call a plugin hook and return the first non-None result."""
        results = self.call_hook(hook_name, *args, **kwargs)
        for result in results:
            if result is not None:
                return result
        return None


# Global plugin manager instance
_plugin_manager: Optional[PluginManager] = None

def get_plugin_manager() -> PluginManager:
    """Get or create the global plugin manager."""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
        _plugin_manager.discover_plugins()
    return _plugin_manager