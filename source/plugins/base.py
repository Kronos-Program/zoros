"""Base Plugin Classes for ZorOS

Provides base classes and utilities for creating ZorOS plugins.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ZorosPlugin(ABC):
    """Base class for all ZorOS plugins.
    
    Plugins should inherit from this class and implement the required methods.
    The plugin system will automatically discover and load plugins that
    follow this interface.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name (human-readable)."""
        pass
    
    @property
    @abstractmethod
    def version(self) -> str:
        """Plugin version."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Plugin description."""
        pass
    
    @property
    def dependencies(self) -> List[str]:
        """List of required Python packages.
        
        Returns:
            List of package names that should be installed
        """
        return []
    
    @property
    def optional_dependencies(self) -> List[str]:
        """List of optional Python packages.
        
        Returns:
            List of package names that enhance functionality
        """
        return []
    
    def initialize(self, plugin_manager: Any) -> None:
        """Initialize the plugin.
        
        Called when the plugin is loaded. Override to perform
        any setup required by your plugin.
        
        Args:
            plugin_manager: The plugin manager instance
        """
        pass
    
    def cleanup(self) -> None:
        """Clean up plugin resources.
        
        Called when the plugin is unloaded or the system shuts down.
        Override to perform any cleanup required by your plugin.
        """
        pass
    
    def get_config_schema(self) -> Dict[str, Any]:
        """Get the configuration schema for this plugin.
        
        Returns:
            JSON schema describing plugin configuration options
        """
        return {}
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate plugin configuration.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            True if configuration is valid, False otherwise
        """
        return True
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get plugin health status.
        
        Returns:
            Dictionary with health information
        """
        return {
            "name": self.name,
            "version": self.version,
            "status": "healthy",
            "details": {}
        }


class LanguageBackendPlugin(ZorosPlugin):
    """Base class for language model backend plugins."""
    
    @abstractmethod
    def complete_turn(self, prompt: str, context: Dict[str, Any]) -> str:
        """Complete a language model turn.
        
        Args:
            prompt: Input prompt
            context: Additional context and parameters
            
        Returns:
            Model response
        """
        pass
    
    @abstractmethod
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models.
        
        Returns:
            List of model metadata
        """
        pass


class TranscriptionBackendPlugin(ZorosPlugin):
    """Base class for audio transcription backend plugins."""
    
    @abstractmethod
    def transcribe_audio(self, audio_path: Path, options: Dict[str, Any]) -> str:
        """Transcribe audio to text.
        
        Args:
            audio_path: Path to audio file
            options: Transcription options
            
        Returns:
            Transcribed text
        """
        pass
    
    @abstractmethod
    def get_supported_formats(self) -> List[str]:
        """Get list of supported audio formats.
        
        Returns:
            List of file extensions (e.g., ['wav', 'mp3'])
        """
        pass


class TTSBackendPlugin(ZorosPlugin):
    """Base class for text-to-speech backend plugins."""
    
    @abstractmethod
    def synthesize_speech(self, text: str, options: Dict[str, Any]) -> Path:
        """Convert text to speech.
        
        Args:
            text: Text to synthesize
            options: TTS options (voice, speed, etc.)
            
        Returns:
            Path to generated audio file
        """
        pass
    
    @abstractmethod
    def get_available_voices(self) -> List[Dict[str, Any]]:
        """Get list of available voices.
        
        Returns:
            List of voice metadata
        """
        pass


class DocumentProcessorPlugin(ZorosPlugin):
    """Base class for document processing plugins."""
    
    @abstractmethod
    def process_document(self, doc_path: Path, options: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process a document into structured data.
        
        Args:
            doc_path: Path to document
            options: Processing options
            
        Returns:
            List of processed document sections
        """
        pass
    
    @abstractmethod
    def get_supported_formats(self) -> List[str]:
        """Get list of supported document formats.
        
        Returns:
            List of file extensions
        """
        pass


class AgentPlugin(ZorosPlugin):
    """Base class for autonomous agent plugins."""
    
    @abstractmethod
    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task.
        
        Args:
            task: Task description and parameters
            
        Returns:
            Task execution result
        """
        pass
    
    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """Get list of agent capabilities.
        
        Returns:
            List of capability descriptions
        """
        pass


class SearchBackendPlugin(ZorosPlugin):
    """Base class for semantic search backend plugins."""
    
    @abstractmethod
    def semantic_search(self, query: str, options: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Perform semantic search.
        
        Args:
            query: Search query
            options: Search options
            
        Returns:
            List of search results
        """
        pass
    
    @abstractmethod
    def index_documents(self, documents: List[Dict[str, Any]]) -> bool:
        """Index documents for search.
        
        Args:
            documents: List of documents to index
            
        Returns:
            True if indexing succeeded
        """
        pass