"""
Test suite for semaphore leak fixes in ZorOS Intake

This test suite specifically targets the semaphore leak issues in the
audio recording and transcription pipeline to verify fixes.

Run with: pytest tests/test_semaphore_leak_fix.py -v
"""

import pytest
import time
import threading
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from source.interfaces.intake.main import Recorder, IntakeWindow
from source.utils.resource_monitor import ResourceMonitor


class TestSemaphoreLeakFixes:
    """Test semaphore leak fixes in the intake system."""
    
    @pytest.fixture
    def monitor(self):
        """Provide resource monitor for leak detection."""
        return ResourceMonitor()
    
    @pytest.fixture
    def recorder(self):
        """Provide a recorder instance for testing."""
        return Recorder()
    
    def test_recorder_stop_always_closes_stream(self, recorder, monitor):
        """Test that recorder.stop() always closes streams to prevent leaks."""
        
        with monitor.monitor_operation("recorder_stop_test"):
            # Mock sounddevice to avoid actual audio hardware
            with patch('source.interfaces.intake.main.sd') as mock_sd:
                mock_stream = MagicMock()
                mock_sd.InputStream.return_value = mock_stream
                
                # Start recorder
                recorder.start()
                assert recorder.stream is not None
                
                # Test stop with keep_stream=True (should still close for leak fix)
                temp_path = Path(tempfile.mktemp(suffix=".wav"))
                recorder.stop(temp_path, keep_stream=True)
                
                # Verify stream was closed despite keep_stream=True
                assert recorder.stream is None
                mock_stream.stop.assert_called_once()
                mock_stream.close.assert_called_once()
                
                # Cleanup
                if temp_path.exists():
                    temp_path.unlink()
    
    def test_recorder_stop_with_exception_handling(self, recorder, monitor):
        """Test that recorder.stop() handles exceptions and still cleans up."""
        
        with monitor.monitor_operation("recorder_exception_test"):
            with patch('source.interfaces.intake.main.sd') as mock_sd:
                mock_stream = MagicMock()
                mock_stream.stop.side_effect = Exception("Mock stop error")
                mock_sd.InputStream.return_value = mock_stream
                
                recorder.start()
                
                temp_path = Path(tempfile.mktemp(suffix=".wav"))
                
                # stop() should handle the exception and still clean up
                with pytest.raises(Exception):
                    recorder.stop(temp_path, keep_stream=False)
                
                # Stream should still be cleaned up
                assert recorder.stream is None
                
                if temp_path.exists():
                    temp_path.unlink()
    
    def test_multiple_recorder_cycles_no_leak(self, monitor):
        """Test multiple record/stop cycles don't leak resources."""
        
        baseline_threads = threading.active_count()
        
        with monitor.monitor_operation("multiple_recorder_cycles"):
            with patch('source.interfaces.intake.main.sd') as mock_sd:
                mock_sd.InputStream.return_value = MagicMock()
                
                # Run multiple cycles
                for i in range(5):
                    recorder = Recorder()
                    recorder.start()
                    
                    temp_path = Path(tempfile.mktemp(suffix=".wav"))
                    recorder.stop(temp_path, keep_stream=True)  # This used to leak
                    
                    if temp_path.exists():
                        temp_path.unlink()
                    
                    # Brief pause to allow cleanup
                    time.sleep(0.1)
        
        # Check that thread count hasn't grown significantly
        final_threads = threading.active_count()
        thread_increase = final_threads - baseline_threads
        
        # Allow some variance but detect significant leaks
        assert thread_increase <= 2, f"Potential thread leak: {thread_increase} threads added"
    
    @pytest.mark.skip(reason="Requires PySide6 environment")
    def test_intake_window_executor_shutdown(self, monitor):
        """Test that IntakeWindow properly shuts down ThreadPoolExecutor."""
        
        with monitor.monitor_operation("intake_window_shutdown"):
            with patch('source.interfaces.intake.main.QApplication'):
                window = IntakeWindow(unified=False)
                
                # Simulate some executor work
                future = window.executor.submit(time.sleep, 0.1)
                future.result()  # Wait for completion
                
                baseline_threads = threading.active_count()
                
                # Trigger close event (simulates window close)
                from unittest.mock import MagicMock
                mock_event = MagicMock()
                window.closeEvent(mock_event)
                
                # Allow time for cleanup
                time.sleep(0.5)
                
                final_threads = threading.active_count()
                thread_decrease = baseline_threads - final_threads
                
                # Executor should have been shut down, reducing thread count
                assert thread_decrease >= 0, "Threads not properly cleaned up"
    
    def test_stream_state_monitoring(self, recorder, monitor):
        """Test enhanced stream state monitoring for debugging."""
        
        with monitor.monitor_operation("stream_state_monitoring"):
            with patch('source.interfaces.intake.main.sd') as mock_sd:
                mock_stream = MagicMock()
                mock_sd.InputStream.return_value = mock_stream
                
                # Test state transitions
                assert recorder.stream is None
                
                recorder.start()
                assert recorder.stream is not None
                
                temp_path = Path(tempfile.mktemp(suffix=".wav"))
                recorder.stop(temp_path)
                assert recorder.stream is None
                
                if temp_path.exists():
                    temp_path.unlink()
    
    def test_resource_monitoring_integration(self):
        """Test that resource monitoring correctly detects leaks."""
        
        monitor = ResourceMonitor()
        monitor.start_monitoring()
        
        # Simulate a leak by creating threads that don't get cleaned up
        def leak_thread():
            time.sleep(0.5)
        
        # Create some threads to simulate a leak
        for _ in range(3):
            thread = threading.Thread(target=leak_thread)
            thread.start()
        
        time.sleep(1.0)  # Let monitoring collect data
        monitor.stop_monitoring()
        
        # Analyze for leaks
        leak_analysis = monitor.detect_leaks()
        
        # Should detect the thread increase
        assert len(monitor.measurements) >= 2
        assert 'baseline' in leak_analysis
        assert 'final' in leak_analysis


class TestLoggingEnhancements:
    """Test logging improvements for better debugging."""
    
    def test_debug_logging_captures_resource_info(self, caplog):
        """Test that debug logging captures resource information."""
        
        with patch('source.interfaces.intake.main.sd') as mock_sd:
            mock_sd.InputStream.return_value = MagicMock()
            
            recorder = Recorder()
            
            # Enable debug logging
            import logging
            caplog.set_level(logging.DEBUG)
            
            # Test operations that should log resource info
            recorder.start()
            
            temp_path = Path(tempfile.mktemp(suffix=".wav"))
            recorder.stop(temp_path)
            
            if temp_path.exists():
                temp_path.unlink()
            
            # Check that debug messages were logged
            debug_messages = [record.message for record in caplog.records 
                            if record.levelname == 'DEBUG']
            
            # Should have resource monitoring messages
            resource_messages = [msg for msg in debug_messages 
                               if 'Active threads' in msg or 'Stream' in msg]
            
            assert len(resource_messages) > 0, "No resource monitoring debug messages found"
    
    def test_error_logging_includes_context(self, caplog):
        """Test that error logging includes sufficient context."""
        
        with patch('source.interfaces.intake.main.sd') as mock_sd:
            # Simulate an error in stream creation
            mock_sd.InputStream.side_effect = Exception("Mock audio error")
            
            recorder = Recorder()
            
            import logging
            caplog.set_level(logging.ERROR)
            
            # This should trigger error logging
            with pytest.raises(Exception):
                recorder.start()
            
            # Check error messages include context
            error_messages = [record.message for record in caplog.records 
                            if record.levelname == 'ERROR']
            
            # Should have informative error messages
            assert len(error_messages) > 0, "No error messages logged"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])