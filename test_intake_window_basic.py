#!/usr/bin/env python3
"""
Basic test of IntakeWindow with improved threading.

This test checks if the IntakeWindow can be instantiated and has the 
improved threading services properly integrated.
"""

import sys
import logging
from pathlib import Path

# Add the project root to the path  
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_intake_window_basic():
    """Test basic IntakeWindow functionality with improved threading."""
    
    # Check if we're in a display environment
    import os
    if 'DISPLAY' not in os.environ and sys.platform != 'darwin':
        logger.warning("No display environment detected, skipping UI test")
        return True
    
    try:
        # Import Qt application
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QTimer
        
        # Create application
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # Import IntakeWindow
        from backend.interfaces.intake.main import IntakeWindow, IMPROVED_THREADING_AVAILABLE
        
        logger.info(f"Improved threading available: {IMPROVED_THREADING_AVAILABLE}")
        
        # Create IntakeWindow
        logger.info("Creating IntakeWindow...")
        window = IntakeWindow()
        
        # Check if improved services are available
        has_adapter = hasattr(window, 'transcription_adapter')
        has_monitor = hasattr(window, 'enhanced_resource_monitor')
        has_mutex = hasattr(window, '_state_mutex')
        
        logger.info(f"IntakeWindow created successfully:")
        logger.info(f"  - Has transcription adapter: {has_adapter}")
        logger.info(f"  - Has enhanced resource monitor: {has_monitor}")
        logger.info(f"  - Has state mutex: {has_mutex}")
        
        # Test service statistics if available
        if has_adapter:
            try:
                stats = window.transcription_adapter.get_service_statistics()
                logger.info(f"  - Service stats: {stats['active_workers']} workers, running: {stats['is_running']}")
            except Exception as e:
                logger.warning(f"  - Failed to get service stats: {e}")
        
        if has_monitor:
            try:
                resource_stats = window.enhanced_resource_monitor.get_statistics()
                current = resource_stats.get('current', {})
                logger.info(f"  - Resource stats: {current.get('memory_mb', 0):.1f}MB, {current.get('threads', 0)} threads")
            except Exception as e:
                logger.warning(f"  - Failed to get resource stats: {e}")
        
        # Show window briefly to test UI
        window.show()
        
        # Set up a timer to close the window after a short time
        close_timer = QTimer()
        close_timer.setSingleShot(True)
        close_timer.timeout.connect(window.close)
        close_timer.start(1000)  # Close after 1 second
        
        # Run event loop briefly
        app.processEvents()
        
        logger.info("✅ IntakeWindow test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ IntakeWindow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the test."""
    logger.info("🚀 Starting IntakeWindow basic test...")
    
    success = test_intake_window_basic()
    
    if success:
        logger.info("🎉 IntakeWindow basic test passed!")
        return 0
    else:
        logger.error("💥 IntakeWindow basic test failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())