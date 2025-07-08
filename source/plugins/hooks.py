"""Plugin Hook Specifications for ZorOS

Defines the plugin interfaces using Pluggy hookspecs.
These specifications define what methods plugins can implement
to extend ZorOS functionality.
"""

import pluggy
from typing import Dict, List, Any, Optional
from pathlib import Path

hookspec = pluggy.HookspecMarker("zoros")


class LanguageServiceHooks:
    """Hooks for language model and LLM backend plugins."""
    
    @hookspec
    def register_language_backend(self, backend_name: str, backend_class: Any) -> None:
        """Register a new language model backend.
        
        Args:
            backend_name: Unique identifier for the backend
            backend_class: Class implementing the language backend interface
        """
    
    @hookspec
    def complete_turn(self, prompt: str, context: Dict[str, Any]) -> Optional[str]:
        """Process a language completion request.
        
        Args:
            prompt: The input prompt
            context: Additional context and parameters
            
        Returns:
            Completion response or None if not handled
        """
    
    @hookspec
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Return list of available models from this backend.
        
        Returns:
            List of model metadata dictionaries
        """


class AudioProcessingHooks:
    """Hooks for audio processing, transcription, and synthesis."""
    
    @hookspec
    def register_transcription_backend(self, backend_name: str, backend_class: Any) -> None:
        """Register a new transcription backend.
        
        Args:
            backend_name: Unique identifier for the backend
            backend_class: Class implementing transcription interface
        """
    
    @hookspec
    def transcribe_audio(self, audio_path: Path, options: Dict[str, Any]) -> Optional[str]:
        """Transcribe audio to text.
        
        Args:
            audio_path: Path to audio file
            options: Transcription options (model, language, etc.)
            
        Returns:
            Transcribed text or None if not handled
        """
    
    @hookspec
    def register_tts_backend(self, backend_name: str, backend_class: Any) -> None:
        """Register a text-to-speech backend.
        
        Args:
            backend_name: Unique identifier for the TTS backend
            backend_class: Class implementing TTS interface
        """
    
    @hookspec
    def synthesize_speech(self, text: str, options: Dict[str, Any]) -> Optional[Path]:
        """Convert text to speech audio.
        
        Args:
            text: Text to synthesize
            options: TTS options (voice, speed, etc.)
            
        Returns:
            Path to generated audio file or None if not handled
        """


class DocumentProcessingHooks:
    """Hooks for document processing and fiberization."""
    
    @hookspec
    def register_document_processor(self, processor_name: str, processor_class: Any) -> None:
        """Register a document processing backend.
        
        Args:
            processor_name: Unique identifier for the processor
            processor_class: Class implementing document processing interface
        """
    
    @hookspec
    def process_document(self, doc_path: Path, options: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Process a document into structured data.
        
        Args:
            doc_path: Path to document file
            options: Processing options
            
        Returns:
            List of processed document sections or None if not handled
        """
    
    @hookspec
    def register_fiberizer(self, fiberizer_name: str, fiberizer_class: Any) -> None:
        """Register a custom fiberizer.
        
        Args:
            fiberizer_name: Unique identifier for the fiberizer
            fiberizer_class: Class implementing fiberizer interface
        """


class AgenticHooks:
    """Hooks for agentic frameworks and orchestration."""
    
    @hookspec
    def register_agent(self, agent_name: str, agent_class: Any) -> None:
        """Register an autonomous agent.
        
        Args:
            agent_name: Unique identifier for the agent
            agent_class: Class implementing agent interface
        """
    
    @hookspec
    def execute_task(self, task: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute a task using an agent.
        
        Args:
            task: Task description and parameters
            
        Returns:
            Task result or None if not handled
        """
    
    @hookspec
    def register_orchestrator(self, orchestrator_name: str, orchestrator_class: Any) -> None:
        """Register a workflow orchestrator.
        
        Args:
            orchestrator_name: Unique identifier for the orchestrator
            orchestrator_class: Class implementing orchestration interface
        """


class SearchAndResearchHooks:
    """Hooks for semantic search and research tools."""
    
    @hookspec
    def register_search_backend(self, backend_name: str, backend_class: Any) -> None:
        """Register a semantic search backend.
        
        Args:
            backend_name: Unique identifier for the search backend
            backend_class: Class implementing search interface
        """
    
    @hookspec
    def semantic_search(self, query: str, options: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Perform semantic search.
        
        Args:
            query: Search query
            options: Search options (index, filters, etc.)
            
        Returns:
            List of search results or None if not handled
        """
    
    @hookspec
    def register_research_tool(self, tool_name: str, tool_class: Any) -> None:
        """Register a research tool.
        
        Args:
            tool_name: Unique identifier for the research tool
            tool_class: Class implementing research tool interface
        """


class UIHooks:
    """Hooks for UI extensions and integrations."""
    
    @hookspec
    def register_ui_component(self, component_name: str, component_info: Dict[str, Any]) -> None:
        """Register a UI component or panel.
        
        Args:
            component_name: Unique identifier for the component
            component_info: Component metadata and configuration
        """
    
    @hookspec
    def get_ui_panels(self) -> List[Dict[str, Any]]:
        """Return UI panels provided by this plugin.
        
        Returns:
            List of UI panel configurations
        """
    
    @hookspec
    def register_cli_command(self, command_name: str, command_func: Any) -> None:
        """Register a CLI command.
        
        Args:
            command_name: Name of the CLI command
            command_func: Function implementing the command
        """


# Combine all hook classes into a single specification
class ZorosHookSpec(
    LanguageServiceHooks,
    AudioProcessingHooks, 
    DocumentProcessingHooks,
    AgenticHooks,
    SearchAndResearchHooks,
    UIHooks
):
    """Combined hook specification for all ZorOS plugin interfaces."""
    pass