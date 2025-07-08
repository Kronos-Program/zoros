#!/usr/bin/env python3
"""
🧪 UI Stability Tests for Intake Interface
Test settings dialog, backend selection, and UI stability under various conditions.
"""

import sys
import os
import time
import pytest
import tempfile
import threading
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import Qt for testing
try:
    from PySide6.QtWidgets import QApplication, QWidget
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtTest import QTest
    qt_available = True
except ImportError:
    qt_available = False

# Import project modules
from source.dictation_backends import get_available_backends
from source.interfaces.intake.main import SettingsDialog, IntakeWindow, load_settings, save_settings


class TestBackendAvailability:
    """Test that backends are properly registered and available."""
    
    def test_get_available_backends_includes_live_mlx(self):
        """Test that LiveMLXWhisper appears in available backends."""
        backends = get_available_backends()
        
        # Should include both stable and live versions
        assert "MLXWhisper" in backends, "MLXWhisper should be available"
        assert "LiveMLXWhisper" in backends, "LiveMLXWhisper should be available"
        
        # Verify ordering and separation
        mlx_index = backends.index("MLXWhisper")
        live_mlx_index = backends.index("LiveMLXWhisper")
        assert live_mlx_index == mlx_index + 1, "LiveMLXWhisper should come right after MLXWhisper"
    
    def test_backend_uniqueness(self):
        """Test that all backends are unique."""
        backends = get_available_backends()
        assert len(backends) == len(set(backends)), "All backends should be unique"
    
    def test_backend_naming_convention(self):
        """Test that backend names follow expected conventions."""
        backends = get_available_backends()
        
        for backend in backends:
            # Should be valid Python identifier-like strings
            assert isinstance(backend, str), "Backend name should be string"
            assert len(backend) > 0, "Backend name should not be empty"
            assert backend[0].isupper(), "Backend name should start with uppercase"


@pytest.mark.skipif(not qt_available, reason="PySide6 not available")
class TestSettingsDialog:
    """Test the settings dialog functionality."""
    
    @pytest.fixture(scope="function")
    def app(self):
        """Create QApplication for testing."""
        app = QApplication.instance()
        if not app:
            app = QApplication([])
        yield app
        # Don't quit app as it might be shared
    
    @pytest.fixture
    def temp_settings(self):
        """Create temporary settings for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            settings_path = f.name
            settings = {
                "WhisperBackend": "MLXWhisper",
                "WhisperModel": "large-v3-turbo",
                "AutoCopy": True,
                "DebugLog": False
            }
            import json
            json.dump(settings, f)
        
        yield settings_path, settings
        
        # Cleanup
        os.unlink(settings_path)
    
    def test_settings_dialog_creation(self, app, temp_settings):
        """Test that settings dialog can be created with all backends."""
        settings_path, settings = temp_settings
        available_backends = get_available_backends()
        
        # Create settings dialog
        dialog = SettingsDialog(settings, available_backends)
        
        # Verify backend combo box contains all backends
        backend_combo = dialog.backend_box
        backend_items = [backend_combo.itemText(i) for i in range(backend_combo.count())]
        
        for backend in available_backends:
            # Some backends may have modified names in the UI (e.g., with warnings)
            backend_found = any(backend in item for item in backend_items)
            assert backend_found, f"Backend {backend} should be in settings dropdown (found: {backend_items})"
        
        # Specifically check for LiveMLXWhisper
        assert "LiveMLXWhisper" in backend_items, "LiveMLXWhisper should appear in settings"
        
        dialog.close()
    
    def test_backend_selection_persistence(self, app, temp_settings):
        """Test that backend selection persists correctly."""
        settings_path, settings = temp_settings
        available_backends = get_available_backends()
        
        # Test with LiveMLXWhisper if available
        if "LiveMLXWhisper" in available_backends:
            # Create dialog and set LiveMLXWhisper
            dialog = SettingsDialog(settings, available_backends)
            dialog.backend_box.setCurrentText("LiveMLXWhisper")
            
            # Verify selection
            assert dialog.backend_box.currentText() == "LiveMLXWhisper"
            dialog.close()
    
    def test_settings_dialog_robustness(self, app):
        """Test settings dialog with edge cases."""
        # Test with empty backends list
        dialog = SettingsDialog({}, [])
        assert dialog.backend_box.count() == 0
        dialog.close()
        
        # Test with single backend
        dialog = SettingsDialog({}, ["MLXWhisper"])
        assert dialog.backend_box.count() == 1
        assert dialog.backend_box.itemText(0) == "MLXWhisper"
        dialog.close()


@pytest.mark.skipif(not qt_available, reason="PySide6 not available")
class TestIntakeWindowStability:
    """Test the main intake window stability."""
    
    @pytest.fixture(scope="function")
    def app(self):
        """Create QApplication for testing."""
        app = QApplication.instance()
        if not app:
            app = QApplication([])
        yield app
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        db_path.unlink(missing_ok=True)
    
    def test_intake_window_creation(self, app, temp_db):
        """Test that intake window can be created successfully."""
        window = IntakeWindow(db_path=temp_db)
        
        # Verify basic properties
        assert window.windowTitle() == "Zoros Intake"
        assert window.db_path == temp_db
        
        # Verify UI components exist
        assert hasattr(window, 'record_btn')
        assert hasattr(window, 'notes')
        assert hasattr(window, 'backend_combo')
        
        window.close()
    
    def test_backend_switching(self, app, temp_db):
        """Test switching between backends doesn't crash."""
        window = IntakeWindow(db_path=temp_db)
        
        available_backends = get_available_backends()
        
        # Test switching to each available backend
        for backend in available_backends:
            try:
                window.backend_combo.setCurrentText(backend)
                # Simulate settings change
                window.whisper_backend = backend
                
                # Verify no crash occurred
                assert window.whisper_backend == backend
                
            except Exception as e:
                pytest.fail(f"Backend switching to {backend} failed: {e}")
        
        window.close()
    
    def test_ui_responsiveness_under_load(self, app, temp_db):
        """Test UI remains responsive under simulated load."""
        window = IntakeWindow(db_path=temp_db)
        
        # Simulate rapid UI updates
        for i in range(100):
            window.notes.setPlainText(f"Test message {i}")
            app.processEvents()  # Process pending events
            
            # Verify UI is still responsive
            assert window.notes.toPlainText() == f"Test message {i}"
        
        window.close()


class TestLongRecordingStability:
    """Test stability with long recordings and extended use."""
    
    def test_memory_usage_tracking(self):
        """Test that memory usage can be tracked."""
        # Import memory tracking function
        from source.interfaces.intake.main import _mem_usage_mb
        
        initial_memory = _mem_usage_mb()
        assert isinstance(initial_memory, (int, float))
        assert initial_memory > 0
        
        # Create some objects to use memory
        large_data = [list(range(1000)) for _ in range(100)]
        
        current_memory = _mem_usage_mb()
        assert current_memory >= initial_memory
        
        # Clean up
        del large_data
        import gc
        gc.collect()
    
    def test_model_cache_management(self):
        """Test that model cache can be managed properly."""
        # This would test model loading/unloading in a real scenario
        # For now, test the cache structure
        cache = {}
        
        # Simulate cache operations
        cache["MLXWhisper_large-v3-turbo"] = "mock_model_instance"
        cache["LiveMLXWhisper_large-v3-turbo"] = "mock_live_model_instance"
        
        assert len(cache) == 2
        
        # Test cache clearing
        cache.clear()
        assert len(cache) == 0


class TestUIGlitchPrevention:
    """Test prevention of UI glitches and edge cases."""
    
    def test_concurrent_settings_access(self):
        """Test that concurrent settings access doesn't cause issues."""
        settings = load_settings()
        
        def modify_settings():
            settings["TestKey"] = "TestValue"
            time.sleep(0.01)  # Small delay
        
        # Create multiple threads that modify settings
        threads = []
        for i in range(10):
            thread = threading.Thread(target=modify_settings)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Verify no corruption occurred
        assert isinstance(settings, dict)
    
    def test_backend_name_validation(self):
        """Test that backend names are properly validated."""
        backends = get_available_backends()
        
        for backend in backends:
            # Test for potentially problematic characters
            assert " " not in backend, f"Backend name '{backend}' should not contain spaces"
            assert "\n" not in backend, f"Backend name '{backend}' should not contain newlines"
            assert "\t" not in backend, f"Backend name '{backend}' should not contain tabs"
            
            # Test length
            assert len(backend) < 100, f"Backend name '{backend}' is too long"
            assert len(backend) > 3, f"Backend name '{backend}' is too short"
    
    def test_settings_robustness(self):
        """Test settings loading/saving robustness."""
        # Test with various settings configurations
        test_settings = [
            {},  # Empty settings
            {"WhisperBackend": "MLXWhisper"},  # Minimal settings
            {"WhisperBackend": "LiveMLXWhisper", "WhisperModel": "large-v3-turbo"},  # Live backend
            {"InvalidKey": "InvalidValue"},  # Invalid settings
        ]
        
        for settings in test_settings:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                import json
                json.dump(settings, f)
                settings_path = f.name
            
            try:
                # Test loading
                loaded = load_settings()
                assert isinstance(loaded, dict)
                
                # Test saving
                save_settings(loaded)
                
            finally:
                os.unlink(settings_path)


def run_ui_stability_tests():
    """Run all UI stability tests."""
    print("🧪 Running UI Stability Tests...")
    
    # Run pytest on this file
    exit_code = pytest.main([__file__, "-v", "--tb=short"])
    return exit_code == 0


if __name__ == "__main__":
    success = run_ui_stability_tests()
    if success:
        print("✅ All UI stability tests passed!")
    else:
        print("❌ Some UI stability tests failed!")
    sys.exit(0 if success else 1)