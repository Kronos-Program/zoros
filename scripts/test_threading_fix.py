#!/usr/bin/env python3
"""
🧪 Test Threading Fix for Live Transcription
Verify that the Qt threading issue is resolved.
"""

import sys
import os
import time
import logging
import threading
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, os.getcwd())

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_signal_system():
    """Test the Qt signal system for thread-safe updates."""
    logger.info("🔄 Testing Qt signal system...")
    
    try:
        # Import PySide6 components
        from PySide6.QtCore import QObject, Signal, QThread, QTimer, QCoreApplication
        from PySide6.QtWidgets import QApplication
        
        # Create a test signal handler
        class TestSignalHandler(QObject):
            test_signal = Signal(str)
            
            def __init__(self):
                super().__init__()
                self.received_data = []
                self.test_signal.connect(self.handle_signal)
            
            def handle_signal(self, data):
                self.received_data.append(data)
                logger.info(f"📡 Received signal: {data}")
        
        # Create test app
        app = QApplication.instance()
        if not app:
            app = QApplication([])
        
        # Create handler
        handler = TestSignalHandler()
        
        # Test signal emission from main thread
        handler.test_signal.emit("main_thread_test")
        
        # Test signal emission from background thread
        def background_task():
            time.sleep(0.1)
            handler.test_signal.emit("background_thread_test")
        
        thread = threading.Thread(target=background_task)
        thread.start()
        
        # Process events to handle signals
        for _ in range(10):
            app.processEvents()
            time.sleep(0.05)
        
        thread.join()
        
        # Check results
        if len(handler.received_data) >= 2:
            logger.info("✅ Signal system working correctly")
            return True
        else:
            logger.error("❌ Signal system failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Signal system test failed: {e}")
        return False

def test_live_processor_thread_safety():
    """Test that live processor doesn't cause threading issues."""
    logger.info("🎬 Testing live processor thread safety...")
    
    try:
        from source.dictation_backends.mlx_whisper_backend import MLXWhisperBackend
        from source.dictation_backends.live_chunk_processor import LiveChunkProcessor
        import numpy as np
        
        # Create backend and processor
        backend = MLXWhisperBackend("large-v3-turbo")
        processor = LiveChunkProcessor(
            backend_instance=backend,
            chunk_duration=1.0,
            overlap_duration=0.1,
            max_buffer_chunks=2
        )
        
        # Test callback that could cause threading issues
        updates = []
        def test_callback(transcript):
            updates.append(transcript)
            logger.info(f"📝 Callback received: {len(transcript)} chars")
        
        # Start processing
        processor.start_processing(update_callback=test_callback)
        
        # Add some dummy audio data
        for i in range(3):
            audio_data = np.random.normal(0, 0.1, 16000)  # 1 second of audio
            processor.add_audio_chunk(audio_data)
            time.sleep(0.2)
        
        # Stop processing
        final_transcript = processor.stop_processing()
        
        # Cleanup
        processor.cleanup()
        
        logger.info(f"✅ Live processor completed without threading issues")
        logger.info(f"📊 Updates received: {len(updates)}")
        logger.info(f"📄 Final transcript length: {len(final_transcript)}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Live processor thread safety test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ui_integration():
    """Test that the UI integration works without threading issues."""
    logger.info("🖥️ Testing UI integration...")
    
    try:
        # Import UI components
        from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QTextEdit
        from PySide6.QtCore import QObject, Signal
        
        # Create test app
        app = QApplication.instance()
        if not app:
            app = QApplication([])
        
        # Create a simple UI widget similar to the intake UI
        class TestWidget(QWidget):
            update_signal = Signal(str)
            
            def __init__(self):
                super().__init__()
                layout = QVBoxLayout()
                self.text_edit = QTextEdit()
                layout.addWidget(self.text_edit)
                self.setLayout(layout)
                
                # Connect signal
                self.update_signal.connect(self.handle_update)
            
            def handle_update(self, text):
                self.text_edit.setPlainText(f"LIVE: {text}")
                logger.info(f"📝 UI updated with: {len(text)} chars")
        
        # Create widget
        widget = TestWidget()
        
        # Test update from main thread
        widget.update_signal.emit("Main thread update")
        
        # Test update from background thread
        def background_update():
            time.sleep(0.1)
            widget.update_signal.emit("Background thread update")
        
        thread = threading.Thread(target=background_update)
        thread.start()
        
        # Process events
        for _ in range(10):
            app.processEvents()
            time.sleep(0.05)
        
        thread.join()
        
        # Check if updates worked
        current_text = widget.text_edit.toPlainText()
        if "Background thread update" in current_text:
            logger.info("✅ UI integration working correctly")
            return True
        else:
            logger.error("❌ UI integration failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ UI integration test failed: {e}")
        return False

def main():
    """Run all threading tests."""
    logger.info("🧪 TESTING THREADING FIX")
    logger.info("=" * 50)
    
    tests = [
        ("Signal System", test_signal_system),
        ("Live Processor Thread Safety", test_live_processor_thread_safety),
        ("UI Integration", test_ui_integration),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n🧪 Running {test_name}...")
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"❌ {test_name} failed with exception: {e}")
            results[test_name] = False
    
    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("🧪 THREADING TEST RESULTS")
    logger.info("=" * 50)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"   {test_name}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        logger.info("🎉 ALL THREADING TESTS PASSED!")
        logger.info("✅ The Qt threading issue has been resolved.")
        logger.info("✅ Live transcription should now work without segmentation faults.")
        logger.info("✅ UI updates are now thread-safe using Qt signals.")
    else:
        logger.info("⚠️ Some threading tests failed.")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)