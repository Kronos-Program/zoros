#!/usr/bin/env python3
"""
Test script for threading integration.

This script tests the improved threading services integration
without running the full UI, to verify the services work correctly.
"""

import sys
import logging
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_services_import():
    """Test that the improved threading services can be imported."""
    try:
        from backend.services.improved_transcription_service import get_transcription_service
        from backend.services.enhanced_resource_monitor import get_resource_monitor
        from backend.services.intake_transcription_adapter import create_intake_adapter
        
        logger.info("✅ All improved threading services imported successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to import improved threading services: {e}")
        return False

def test_transcription_service():
    """Test the improved transcription service."""
    try:
        from backend.services.improved_transcription_service import get_transcription_service
        
        service = get_transcription_service()
        stats = service.get_service_stats()
        
        logger.info(f"✅ Transcription service initialized: {stats['active_workers']} workers")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to initialize transcription service: {e}")
        return False

def test_resource_monitor():
    """Test the enhanced resource monitor."""
    try:
        from backend.services.enhanced_resource_monitor import get_resource_monitor
        
        monitor = get_resource_monitor()
        snapshot = monitor.get_current_snapshot()
        
        logger.info(f"✅ Resource monitor initialized: {snapshot.memory_usage_mb:.1f}MB memory, {snapshot.thread_count} threads")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to initialize resource monitor: {e}")
        return False

def test_intake_adapter():
    """Test the intake transcription adapter."""
    try:
        from backend.services.intake_transcription_adapter import create_intake_adapter
        
        adapter = create_intake_adapter(timeout_seconds=30)
        stats = adapter.get_service_statistics()
        
        logger.info(f"✅ Intake adapter initialized: {stats['active_workers']} workers, {stats['is_running']} running")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to initialize intake adapter: {e}")
        return False

def test_intake_window_integration():
    """Test that IntakeWindow can be imported with improved threading."""
    try:
        # We need to mock PySide6 for this test
        import unittest.mock
        
        # Mock PySide6 components
        mock_qt = unittest.mock.MagicMock()
        mock_qt.WindowType.WindowStaysOnTopHint = 1
        
        with unittest.mock.patch.dict('sys.modules', {
            'PySide6': mock_qt,
            'PySide6.QtCore': mock_qt,
            'PySide6.QtGui': mock_qt,
            'PySide6.QtWidgets': mock_qt
        }):
            from backend.interfaces.intake.main import IntakeWindow
            logger.info("✅ IntakeWindow imported successfully with improved threading")
            return True
            
    except Exception as e:
        logger.error(f"❌ Failed to import IntakeWindow: {e}")
        logger.error(f"Details: {str(e)}")
        return False

def main():
    """Run all tests."""
    logger.info("🚀 Starting threading integration tests...")
    
    tests = [
        ("Services Import", test_services_import),
        ("Transcription Service", test_transcription_service), 
        ("Resource Monitor", test_resource_monitor),
        ("Intake Adapter", test_intake_adapter),
        ("IntakeWindow Integration", test_intake_window_integration)
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\n📋 Running test: {test_name}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ Test {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "="*50)
    logger.info("📊 TEST RESULTS SUMMARY")
    logger.info("="*50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
        if result:
            passed += 1
    
    logger.info(f"\n🎯 {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        logger.info("🎉 All tests passed! Threading integration is ready.")
        return 0
    else:
        logger.error("💥 Some tests failed. Check the logs above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())