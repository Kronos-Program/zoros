"""Tests for the robust backend registry system."""

import pytest
from unittest.mock import patch, MagicMock
from source.dictation_backends.registry import BackendRegistry, get_backend_registry, reset_registry


class TestBackendRegistry:
    """Test cases for the BackendRegistry class."""
    
    def setup_method(self):
        """Reset the registry before each test."""
        reset_registry()
    
    def test_registry_initialization(self):
        """Test that registry initializes correctly."""
        registry = BackendRegistry()
        assert registry._initialized == False
        assert len(registry._registered_backends) == 0
        assert len(registry._failed_backends) == 0
        
    def test_list_available_backends_initializes_registry(self):
        """Test that listing backends initializes the registry."""
        registry = BackendRegistry()
        backends = registry.list_available_backends()
        assert registry._initialized == True
        assert isinstance(backends, list)
        
    def test_get_backend_class_success(self):
        """Test getting a backend class that exists."""
        registry = BackendRegistry()
        # Mock backend should always be available
        backend_class = registry.get_backend_class("Mock")
        assert backend_class is not None
        
    def test_get_backend_class_missing_backend(self):
        """Test getting a backend class that doesn't exist."""
        registry = BackendRegistry()
        with pytest.raises(ValueError, match="Unknown backend"):
            registry.get_backend_class("NonExistentBackend")
            
    def test_get_backend_class_failed_import(self):
        """Test getting a backend class that failed to import."""
        registry = BackendRegistry()
        # Force a backend to fail by simulating a missing dependency
        with patch('source.dictation_backends.registry.importlib.import_module') as mock_import:
            mock_import.side_effect = ImportError("Module not found")
            registry._initialized = False  # Reset to trigger re-initialization
            
            with pytest.raises(ImportError, match="Backend .* is not available"):
                registry.get_backend_class("MLXWhisper")
                
    def test_is_backend_available(self):
        """Test checking backend availability."""
        registry = BackendRegistry()
        assert registry.is_backend_available("Mock") == True
        assert registry.is_backend_available("NonExistentBackend") == False
        
    def test_get_backend_info(self):
        """Test getting backend information."""
        registry = BackendRegistry()
        info = registry.get_backend_info("Mock")
        assert info is not None
        assert info.name == "Mock"
        assert info.description == "Mock backend for testing and development"
        assert info.dependencies == []
        
    def test_get_failed_backends(self):
        """Test getting failed backends information."""
        registry = BackendRegistry()
        
        # Force a backend to fail
        with patch('source.dictation_backends.registry.importlib.import_module') as mock_import:
            mock_import.side_effect = ImportError("Test error")
            registry._initialized = False
            
            # This should trigger initialization and catch the error
            registry.list_available_backends()
            
            failed = registry.get_failed_backends()
            assert isinstance(failed, dict)
            
    def test_get_backend_status(self):
        """Test getting comprehensive backend status."""
        registry = BackendRegistry()
        status = registry.get_backend_status()
        
        assert "available" in status
        assert "failed" in status
        assert "total_defined" in status
        assert "total_available" in status
        assert "total_failed" in status
        
        assert isinstance(status["available"], list)
        assert isinstance(status["failed"], list)
        assert status["total_defined"] > 0
        assert status["total_available"] >= 0
        assert status["total_failed"] >= 0
        
    def test_backend_loading_with_missing_dependencies(self):
        """Test that backends with missing dependencies are handled gracefully."""
        registry = BackendRegistry()
        
        # Mock a backend that has missing dependencies
        with patch('source.dictation_backends.registry.importlib.import_module') as mock_import:
            def side_effect(module_name):
                if "mlx_whisper" in module_name:
                    raise ImportError("No module named 'mlx_whisper'")
                # Let other modules import normally
                return MagicMock()
            
            mock_import.side_effect = side_effect
            registry._initialized = False
            
            available = registry.list_available_backends()
            failed = registry.get_failed_backends()
            
            # MLX backends should have failed
            mlx_backends = [name for name in failed.keys() if "MLX" in name]
            assert len(mlx_backends) > 0
            
            # But other backends should still be available
            assert len(available) > 0
            
    def test_global_registry_singleton(self):
        """Test that the global registry is a singleton."""
        registry1 = get_backend_registry()
        registry2 = get_backend_registry()
        assert registry1 is registry2
        
    def test_registry_reset(self):
        """Test that registry can be reset."""
        registry1 = get_backend_registry()
        registry1.list_available_backends()  # Initialize
        
        reset_registry()
        
        registry2 = get_backend_registry()
        assert registry1 is not registry2
        assert registry2._initialized == False
        
    def test_openai_api_backend_requires_api_key(self):
        """Test that OpenAI API backend requires API key."""
        registry = BackendRegistry()
        
        # Test without API key
        with patch.dict('os.environ', {}, clear=True):
            with patch('source.dictation_backends.registry.importlib.import_module') as mock_import:
                mock_import.return_value = MagicMock()
                registry._initialized = False
                
                registry.list_available_backends()
                
                # OpenAI API should fail due to missing API key
                assert not registry.is_backend_available("OpenAIAPI")
                
        # Test with API key
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}, clear=True):
            with patch('source.dictation_backends.registry.importlib.import_module') as mock_import:
                mock_import.return_value = MagicMock()
                registry._initialized = False
                
                registry.list_available_backends()
                
                # OpenAI API should be available with API key
                assert registry.is_backend_available("OpenAIAPI")
                
    def test_backend_definitions_complete(self):
        """Test that all expected backends are defined."""
        registry = BackendRegistry()
        backend_definitions = registry._get_backend_definitions()
        
        expected_backends = [
            "WhisperCPP",
            "FasterWhisper",
            "StandardOpenAIWhisper",
            "OpenAIAPI",
            "MLXWhisper",
            "LiveMLXWhisper",
            "ParallelMLXWhisper",
            "QueueBasedStreamingMLXWhisper", 
            "RealtimeStreamingMLXWhisper",
            "Mock"
        ]
        
        defined_names = [backend.name for backend in backend_definitions]
        for expected in expected_backends:
            assert expected in defined_names, f"Backend {expected} is not defined"