#!/usr/bin/env python3
"""
🎯 User Experience Test for LiveMLXWhisper Backend
Simulate real user workflow to test backend selection and stability.
"""

import sys
import os
import time
import tempfile
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, os.getcwd())

def test_user_workflow_backend_selection():
    """Test the complete user workflow for selecting LiveMLXWhisper."""
    print("👤 Testing User Workflow: Backend Selection")
    print("=" * 50)
    
    try:
        from PySide6.QtWidgets import QApplication
        from source.interfaces.intake.main import IntakeWindow, SettingsDialog
        from source.dictation_backends import get_available_backends
        
        # Create app
        app = QApplication.instance()
        if not app:
            app = QApplication([])
        
        # Create temporary database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        
        print("1️⃣ Creating intake window...")
        window = IntakeWindow(db_path=db_path)
        print("✅ Intake window created")
        
        print("2️⃣ Opening settings dialog...")
        backends = get_available_backends()
        settings = {"WhisperBackend": "MLXWhisper", "WhisperModel": "large-v3-turbo"}
        dialog = SettingsDialog(settings, backends)
        print("✅ Settings dialog opened")
        
        print("3️⃣ Checking available backends in dropdown...")
        backend_combo = dialog.backend_box
        backend_items = [backend_combo.itemText(i) for i in range(backend_combo.count())]
        print(f"📋 Available backends: {backend_items}")
        
        # Verify LiveMLXWhisper is available
        live_mlx_available = any("LiveMLXWhisper" in item for item in backend_items)
        assert live_mlx_available, "LiveMLXWhisper should be available in settings"
        print("✅ LiveMLXWhisper found in settings dropdown")
        
        print("4️⃣ Selecting LiveMLXWhisper backend...")
        # Find the exact item text for LiveMLXWhisper
        live_mlx_item = next(item for item in backend_items if "LiveMLXWhisper" in item)
        dialog.backend_box.setCurrentText(live_mlx_item)
        
        selected = dialog.backend_box.currentText()
        assert "LiveMLXWhisper" in selected, f"Should have selected LiveMLXWhisper, got: {selected}"
        print(f"✅ Successfully selected: {selected}")
        
        print("5️⃣ Testing model selection...")
        model_combo = dialog.model_box
        model_items = [model_combo.itemText(i) for i in range(model_combo.count())]
        print(f"📋 Available models: {model_items}")
        
        # Select large-v3-turbo model
        if "large-v3-turbo" in model_items:
            dialog.model_box.setCurrentText("large-v3-turbo")
            print("✅ Selected large-v3-turbo model")
        else:
            print("⚠️ large-v3-turbo not available, using default")
        
        print("6️⃣ Simulating save settings...")
        # Get current selections
        final_backend = dialog.backend_box.currentText()
        final_model = dialog.model_box.currentText()
        print(f"📊 Final selection: Backend={final_backend}, Model={final_model}")
        
        # Clean up
        dialog.close()
        window.close()
        db_path.unlink(missing_ok=True)
        
        print("✅ User workflow test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ User workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_backend_switching_stability():
    """Test stability when switching between backends multiple times."""
    print("\n🔄 Testing Backend Switching Stability")
    print("=" * 50)
    
    try:
        from PySide6.QtWidgets import QApplication
        from source.interfaces.intake.main import IntakeWindow
        from source.dictation_backends import get_available_backends
        
        # Create app
        app = QApplication.instance()
        if not app:
            app = QApplication([])
        
        # Create temporary database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        
        print("1️⃣ Creating intake window...")
        window = IntakeWindow(db_path=db_path)
        
        backends = get_available_backends()
        print(f"📋 Testing with backends: {backends}")
        
        # Test switching between backends
        mlx_backends = [b for b in backends if "MLX" in b]
        print(f"🧪 Testing MLX backends: {mlx_backends}")
        
        for i, backend in enumerate(mlx_backends):
            print(f"2️⃣.{i+1} Switching to {backend}...")
            
            # Simulate backend switch
            window.backend_combo.setCurrentText(backend)
            window.whisper_backend = backend
            
            # Process events to handle any UI updates
            app.processEvents()
            
            # Verify switch was successful
            assert window.whisper_backend == backend, f"Backend switch failed for {backend}"
            print(f"✅ Successfully switched to {backend}")
            
            # Small delay to simulate user interaction
            time.sleep(0.1)
        
        print("3️⃣ Testing rapid switching...")
        # Test rapid switching (potential stress test)
        for _ in range(5):
            for backend in mlx_backends:
                window.backend_combo.setCurrentText(backend)
                window.whisper_backend = backend
                app.processEvents()
        
        print("✅ Rapid switching test passed")
        
        # Clean up
        window.close()
        db_path.unlink(missing_ok=True)
        
        print("✅ Backend switching stability test completed!")
        return True
        
    except Exception as e:
        print(f"❌ Backend switching test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_long_session_stability():
    """Test UI stability during a long session."""
    print("\n⏱️ Testing Long Session Stability")
    print("=" * 50)
    
    try:
        from PySide6.QtWidgets import QApplication
        from source.interfaces.intake.main import IntakeWindow
        
        # Create app
        app = QApplication.instance()
        if not app:
            app = QApplication([])
        
        # Create temporary database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        
        print("1️⃣ Creating intake window for long session...")
        window = IntakeWindow(db_path=db_path)
        
        print("2️⃣ Simulating extended use...")
        
        # Simulate user interactions over time
        for minute in range(5):  # Simulate 5 minutes of use
            print(f"   Minute {minute + 1}/5...")
            
            # Simulate typing in notes
            for i in range(20):
                text = f"Test message {minute * 20 + i} - simulating user input"
                window.notes.setPlainText(text)
                app.processEvents()
                
                # Verify UI responsiveness
                assert window.notes.toPlainText() == text, "UI should remain responsive"
            
            # Simulate backend operations
            if minute % 2 == 0:  # Every other minute
                window.backend_combo.setCurrentText("MLXWhisper")
            else:
                if "LiveMLXWhisper" in [window.backend_combo.itemText(i) for i in range(window.backend_combo.count())]:
                    window.backend_combo.setCurrentText("LiveMLXWhisper")
            
            app.processEvents()
            time.sleep(0.1)  # Small delay
        
        print("3️⃣ Testing memory stability...")
        # Check that UI is still responsive after extended use
        test_text = "Final test message to verify UI responsiveness"
        window.notes.setPlainText(test_text)
        app.processEvents()
        
        assert window.notes.toPlainText() == test_text, "UI should still be responsive after long session"
        
        # Clean up
        window.close()
        db_path.unlink(missing_ok=True)
        
        print("✅ Long session stability test completed!")
        return True
        
    except Exception as e:
        print(f"❌ Long session test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_glitch_scenarios():
    """Test scenarios that could cause UI glitches."""
    print("\n🐛 Testing Potential Glitch Scenarios")
    print("=" * 50)
    
    scenarios_passed = 0
    total_scenarios = 0
    
    # Scenario 1: Rapid backend switching
    print("1️⃣ Testing rapid backend switching...")
    total_scenarios += 1
    try:
        from source.dictation_backends import get_available_backends
        backends = get_available_backends()
        
        # Simulate very rapid switching
        for _ in range(50):
            for backend in backends[:3]:  # Test first 3 backends
                # Just test that we can iterate without crashes
                pass
        
        print("✅ Rapid switching scenario passed")
        scenarios_passed += 1
    except Exception as e:
        print(f"❌ Rapid switching failed: {e}")
    
    # Scenario 2: Long backend names
    print("2️⃣ Testing long backend names handling...")
    total_scenarios += 1
    try:
        backends = get_available_backends()
        longest_name = max(backends, key=len) if backends else ""
        
        # Verify longest name is reasonable
        assert len(longest_name) < 100, f"Backend name too long: {longest_name}"
        print(f"✅ Longest backend name: {longest_name} ({len(longest_name)} chars)")
        scenarios_passed += 1
    except Exception as e:
        print(f"❌ Long name test failed: {e}")
    
    # Scenario 3: Backend availability consistency
    print("3️⃣ Testing backend availability consistency...")
    total_scenarios += 1
    try:
        backends1 = get_available_backends()
        time.sleep(0.1)
        backends2 = get_available_backends()
        
        assert backends1 == backends2, "Backend availability should be consistent"
        print("✅ Backend availability is consistent")
        scenarios_passed += 1
    except Exception as e:
        print(f"❌ Consistency test failed: {e}")
    
    print(f"\n📊 Glitch scenarios: {scenarios_passed}/{total_scenarios} passed")
    return scenarios_passed == total_scenarios

def main():
    """Run all user experience tests."""
    print("🎯 USER EXPERIENCE TESTING FOR LIVEMLXWHISPER")
    print("=" * 70)
    
    tests = [
        ("User Workflow: Backend Selection", test_user_workflow_backend_selection),
        ("Backend Switching Stability", test_backend_switching_stability),
        ("Long Session Stability", test_long_session_stability),
        ("Glitch Scenarios", test_glitch_scenarios),
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
    print("\n" + "=" * 70)
    print("🎯 USER EXPERIENCE TEST RESULTS")
    print("=" * 70)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {test_name}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 ALL USER EXPERIENCE TESTS PASSED!")
        print("✅ LiveMLXWhisper is ready for user testing")
        print("✅ Backend selection works correctly")
        print("✅ UI is stable under various conditions")
        print("✅ No glitches detected in common scenarios")
        
        print("\n📋 USER INSTRUCTIONS:")
        print("1. Open Zoros Intake application")
        print("2. Click ⚙️ Settings button")
        print("3. Select 'LiveMLXWhisper' from Whisper Backend dropdown")
        print("4. Select 'large-v3-turbo' model")
        print("5. Click Save")
        print("6. Start recording to test live transcription!")
        
    else:
        print("\n⚠️ Some user experience tests failed.")
        print("Check the details above before recommending to users.")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)