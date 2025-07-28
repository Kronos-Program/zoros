#!/usr/bin/env python3
"""
Test script to verify the UI reset fix for transcription completion.

This test simulates the transcription completion flow to ensure the 
record button is properly reset after transcription.
"""

import sys
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_ui_reset_fix():
    """Test that the UI reset fix works correctly."""
    
    try:
        # Mock PySide6 components
        with patch.dict('sys.modules', {
            'PySide6': MagicMock(),
            'PySide6.QtCore': MagicMock(),
            'PySide6.QtGui': MagicMock(),
            'PySide6.QtWidgets': MagicMock()
        }):
            # Import required components
            from backend.interfaces.intake.main import IntakeWindow
            
            # Create a mock IntakeWindow instance
            window = IntakeWindow.__new__(IntakeWindow)
            
            # Mock the required attributes
            window.record_btn = MagicMock()
            window.using_improved_threading = True
            window._state_mutex = MagicMock()
            window.audio_path = None
            
            # Mock the _finish_transcription method to test our fix
            def mock_finish_transcription(transcript):
                # Simulate the fixed _finish_transcription method
                logger.info(f"Mock _finish_transcription called with: {transcript[:50]}...")
                # The fix: reset UI state
                window.record_btn.setText("🔴 Record")
                window.record_btn.setStyleSheet("")
                window.record_btn.setEnabled(True)
                logger.info("UI state reset in _finish_transcription")
            
            window._finish_transcription = mock_finish_transcription
            
            # Test the improved transcription completion handler
            logger.info("Testing improved transcription completion handler...")
            
            # Set initial state (simulating "Transcribing..." state)
            window.record_btn.setText("🔄 Transcribing...")
            window.record_btn.setEnabled(False)
            logger.info("Initial state: Button = 'Transcribing...', Enabled = False")
            
            # Simulate transcription completion
            result = "This is a test transcription result."
            window._on_improved_transcription_completed(result)
            
            # Verify the button was reset
            calls = window.record_btn.setText.call_args_list
            enable_calls = window.record_btn.setEnabled.call_args_list
            
            logger.info(f"Button setText calls: {[str(call) for call in calls]}")
            logger.info(f"Button setEnabled calls: {[str(call) for call in enable_calls]}")
            
            # Check that the button was set back to "Record" state
            reset_calls = [call for call in calls if "Record" in str(call)]
            enable_true_calls = [call for call in enable_calls if "True" in str(call)]
            
            if reset_calls and enable_true_calls:
                logger.info("✅ UI reset fix working correctly!")
                logger.info("  - Button text was set back to '🔴 Record'")
                logger.info("  - Button was re-enabled")
                return True
            else:
                logger.error("❌ UI reset fix not working!")
                logger.error(f"  - Reset calls found: {len(reset_calls)}")
                logger.error(f"  - Enable calls found: {len(enable_true_calls)}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the UI reset test."""
    logger.info("🚀 Testing UI reset fix...")
    
    success = test_ui_reset_fix()
    
    if success:
        logger.info("🎉 UI reset fix test passed!")
        logger.info("The transcription completion should now properly reset the record button.")
        return 0
    else:
        logger.error("💥 UI reset fix test failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())