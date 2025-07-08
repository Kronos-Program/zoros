#!/usr/bin/env python3
"""
🧪 Test Backend Registration and Settings Integration
Verify that LiveMLXWhisper appears in settings and works correctly.
"""

import sys
import os
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, os.getcwd())

def test_backend_availability():
    """Test that LiveMLXWhisper is available."""
    print("🔍 Testing backend availability...")
    
    from source.dictation_backends import get_available_backends
    
    backends = get_available_backends()
    print(f"📋 Available backends: {backends}")
    
    # Check for both MLX backends
    assert "MLXWhisper" in backends, "MLXWhisper should be available"
    assert "LiveMLXWhisper" in backends, "LiveMLXWhisper should be available"
    
    print("✅ Both MLXWhisper and LiveMLXWhisper are available")
    return True

def test_backend_imports():
    """Test that all backends can be imported."""
    print("📦 Testing backend imports...")
    
    try:
        from source.dictation_backends import MLXWhisperBackend, LiveMLXWhisperBackend
        print("✅ MLXWhisper backends imported successfully")
        
        # Test creating instances
        stable_backend = MLXWhisperBackend("large-v3-turbo")
        live_backend = LiveMLXWhisperBackend("large-v3-turbo")
        
        print("✅ Backend instances created successfully")
        return True
        
    except Exception as e:
        print(f"❌ Backend import failed: {e}")
        return False

def test_settings_dialog_integration():
    """Test that LiveMLXWhisper appears in settings dialog."""
    print("⚙️ Testing settings dialog integration...")
    
    try:
        # Import Qt components
        from PySide6.QtWidgets import QApplication
        from source.interfaces.intake.main import SettingsDialog
        from source.dictation_backends import get_available_backends
        
        # Create minimal app
        app = QApplication.instance()
        if not app:
            app = QApplication([])
        
        # Get backends and create dialog
        backends = get_available_backends()
        settings = {"WhisperBackend": "MLXWhisper", "WhisperModel": "large-v3-turbo"}
        
        dialog = SettingsDialog(settings, backends)
        
        # Check that LiveMLXWhisper is in the dropdown
        backend_combo = dialog.backend_box
        backend_items = [backend_combo.itemText(i) for i in range(backend_combo.count())]
        
        print(f"📋 Backends in settings dialog: {backend_items}")
        
        assert "LiveMLXWhisper" in backend_items, "LiveMLXWhisper should appear in settings dialog"
        assert "MLXWhisper" in backend_items, "MLXWhisper should appear in settings dialog"
        
        # Test selection
        dialog.backend_box.setCurrentText("LiveMLXWhisper")
        assert dialog.backend_box.currentText() == "LiveMLXWhisper", "Should be able to select LiveMLXWhisper"
        
        dialog.close()
        print("✅ Settings dialog integration working correctly")
        return True
        
    except Exception as e:
        print(f"❌ Settings dialog test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_backend_map_registration():
    """Test that LiveMLXWhisper is in the backend map."""
    print("🗺️ Testing backend map registration...")
    
    try:
        from source.interfaces.intake.main import BACKEND_MAP
        
        print(f"📋 Backends in BACKEND_MAP: {list(BACKEND_MAP.keys())}")
        
        assert "MLXWhisper" in BACKEND_MAP, "MLXWhisper should be in BACKEND_MAP"
        assert "LiveMLXWhisper" in BACKEND_MAP, "LiveMLXWhisper should be in BACKEND_MAP"
        
        # Test that backend classes can be instantiated
        MLXClass = BACKEND_MAP["MLXWhisper"]
        LiveMLXClass = BACKEND_MAP["LiveMLXWhisper"]
        
        mlx_instance = MLXClass("large-v3-turbo")
        live_mlx_instance = LiveMLXClass("large-v3-turbo")
        
        print("✅ Backend map registration working correctly")
        return True
        
    except Exception as e:
        print(f"❌ Backend map test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_live_backend_functionality():
    """Test basic LiveMLXWhisper functionality."""
    print("🚀 Testing LiveMLXWhisper functionality...")
    
    try:
        from source.dictation_backends import LiveMLXWhisperBackend
        
        # Create instance
        backend = LiveMLXWhisperBackend("large-v3-turbo")
        
        # Test live processing methods
        assert hasattr(backend, 'start_live_processing'), "Should have start_live_processing method"
        assert hasattr(backend, 'stop_live_processing'), "Should have stop_live_processing method"
        assert hasattr(backend, 'add_live_audio'), "Should have add_live_audio method"
        assert hasattr(backend, 'get_live_transcript'), "Should have get_live_transcript method"
        
        # Test initial state
        assert not backend.is_live_mode, "Should not be in live mode initially"
        assert backend.live_processor is None, "Live processor should be None initially"
        
        print("✅ LiveMLXWhisper functionality test passed")
        return True
        
    except Exception as e:
        print(f"❌ LiveMLXWhisper functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all registration tests."""
    print("🧪 TESTING BACKEND REGISTRATION AND INTEGRATION")
    print("=" * 60)
    
    tests = [
        ("Backend Availability", test_backend_availability),
        ("Backend Imports", test_backend_imports),
        ("Backend Map Registration", test_backend_map_registration),
        ("Live Backend Functionality", test_live_backend_functionality),
        ("Settings Dialog Integration", test_settings_dialog_integration),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running {test_name}...")
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("🧪 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {test_name}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ LiveMLXWhisper is properly registered and available in settings")
        print("✅ Users can now select LiveMLXWhisper from the settings dialog")
        print("✅ Backend switching should work correctly")
    else:
        print("\n⚠️ Some tests failed. Check the details above.")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)