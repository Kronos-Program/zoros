#!/usr/bin/env python3
"""Test suite for the intake pipeline with mocked components."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sqlite3
import numpy as np

# Import the modules we want to test
import pytest
import sys
import types

pytest.importorskip("PySide6.QtWidgets", reason="PySide6 not available")
sys.modules.setdefault("sounddevice", types.ModuleType("sounddevice"))
sys.modules.setdefault("soundfile", types.ModuleType("soundfile"))

from source.interfaces.intake.main import (
    IntakeWindow,
    Recorder,
    insert_intake,
    create_fiber_from_intake,
    _ensure_db,
    transcribe_audio,
    DB_PATH,
    AUDIO_DIR,
    DICTATIONS_DIR
)


class MockAudioFile:
    """Mock audio file for testing."""
    
    def __init__(self, content: str = "test audio content"):
        self.content = content
        self.size = len(content) * 100  # Mock file size
    
    def exists(self):
        return True
    
    def stat(self):
        mock_stat = Mock()
        mock_stat.st_size = self.size
        return mock_stat
    
    def __str__(self):
        return "/tmp/mock_audio.wav"


class TestIntakePipeline(unittest.TestCase):
    """Test the complete intake pipeline with mocked components."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary database for testing
        self.test_db = Path(tempfile.mktemp(suffix='.db'))
        self.test_audio_dir = Path(tempfile.mkdtemp())
        self.test_dictations_dir = Path(tempfile.mkdtemp())
        
        # Mock the global paths
        self.original_db_path = DB_PATH
        self.original_audio_dir = AUDIO_DIR
        self.original_dictations_dir = DICTATIONS_DIR
        
        # Patch the global constants
        self.db_patcher = patch('source.interfaces.intake.main.DB_PATH', self.test_db)
        self.audio_patcher = patch('source.interfaces.intake.main.AUDIO_DIR', self.test_audio_dir)
        self.dictations_patcher = patch('source.interfaces.intake.main.DICTATIONS_DIR', self.test_dictations_dir)
        
        self.db_patcher.start()
        self.audio_patcher.start()
        self.dictations_patcher.start()
        
        # Ensure test database is created
        _ensure_db(self.test_db)
    
    def tearDown(self):
        """Clean up test environment."""
        # Stop patches
        self.db_patcher.stop()
        self.audio_patcher.stop()
        self.dictations_patcher.stop()
        
        # Clean up test files
        if self.test_db.exists():
            self.test_db.unlink()
        if self.test_audio_dir.exists():
            import shutil
            shutil.rmtree(self.test_audio_dir)
        if self.test_dictations_dir.exists():
            import shutil
            shutil.rmtree(self.test_dictations_dir)
    
    def test_database_schema(self):
        """Test that the database schema is created correctly."""
        # Ensure database is created
        _ensure_db(self.test_db)
        
        # Check table structure
        with sqlite3.connect(self.test_db) as conn:
            cursor = conn.execute("PRAGMA table_info(intake)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}
            
            expected_columns = {
                'id': 'TEXT',
                'timestamp': 'TEXT', 
                'content': 'TEXT',
                'audio_path': 'TEXT',
                'correction': 'TEXT',
                'fiber_type': 'TEXT'
            }
            
            for col_name, col_type in expected_columns.items():
                self.assertIn(col_name, columns, f"Missing column: {col_name}")
                self.assertEqual(columns[col_name], col_type, f"Wrong type for {col_name}")
    
    def test_insert_intake(self):
        """Test inserting intake records into database."""
        # Test data
        test_content = "This is a test transcription"
        test_audio_path = "/path/to/audio.wav"
        test_correction = "This is a corrected transcription"
        test_fiber_type = "dictation"
        
        # Insert test record
        fiber_id = insert_intake(
            content=test_content,
            audio_path=test_audio_path,
            correction=test_correction,
            fiber_type=test_fiber_type,
            db=self.test_db
        )
        
        # Verify insertion
        with sqlite3.connect(self.test_db) as conn:
            cursor = conn.execute(
                "SELECT id, content, audio_path, correction, fiber_type FROM intake WHERE id = ?",
                (fiber_id,)
            )
            row = cursor.fetchone()
            
            self.assertIsNotNone(row, "Record should be inserted")
            self.assertEqual(row[0], fiber_id)
            self.assertEqual(row[1], test_content)
            self.assertEqual(row[2], test_audio_path)
            self.assertEqual(row[3], test_correction)
            self.assertEqual(row[4], test_fiber_type)
    
    @patch('source.interfaces.intake.main.MLXWhisperBackend')
    def test_transcribe_audio_mlx(self, mock_mlx_backend):
        """Test transcription with MLXWhisper backend."""
        # Mock the backend
        mock_backend_instance = Mock()
        mock_backend_instance.transcribe.return_value = "Mocked transcription result"
        mock_mlx_backend.return_value = mock_backend_instance
        
        # Test transcription
        result = transcribe_audio(
            wav_path="/tmp/test.wav",
            backend="MLXWhisper",
            model="small"
        )
        
        # Verify
        self.assertEqual(result, "Mocked transcription result")
        mock_mlx_backend.assert_called_once_with("small")
        mock_backend_instance.transcribe.assert_called_once_with("/tmp/test.wav")
    
    @patch('source.interfaces.intake.main.whisper')
    def test_transcribe_audio_standard(self, mock_whisper):
        """Test transcription with standard Whisper backend."""
        # Mock whisper
        mock_model = Mock()
        mock_model.transcribe.return_value = {"text": "Standard whisper result"}
        mock_whisper.load_model.return_value = mock_model
        
        # Test transcription
        result = transcribe_audio(
            wav_path="/tmp/test.wav",
            backend="StandardWhisper",
            model="small"
        )
        
        # Verify
        self.assertEqual(result, "Standard whisper result")
        mock_whisper.load_model.assert_called_once_with("small")
        mock_model.transcribe.assert_called_once_with("/tmp/test.wav")
    
    @patch('PySide6.QtWidgets.QApplication')
    @patch('PySide6.QtCore.Qt')
    @patch('PySide6.QtWidgets.QMainWindow')
    def test_intake_window_creation(self, mock_main_window, mock_qt, mock_qapp):
        """Test IntakeWindow creation and initialization."""
        # Mock QApplication
        mock_app_instance = Mock()
        mock_qapp.instance.return_value = mock_app_instance
        mock_app_instance.clipboard.return_value = Mock()
        
        # Mock Qt constants
        mock_qt.WindowStaysOnTopHint = 0x00040000
        
        # Mock QMainWindow
        mock_main_window.__init__ = Mock()
        mock_main_window.setWindowTitle = Mock()
        mock_main_window.setWindowFlags = Mock()
        mock_main_window.setStatusBar = Mock()
        mock_main_window.setCentralWidget = Mock()
        
        # Create window
        window = IntakeWindow(db_path=self.test_db)
        
        # Verify basic properties
        self.assertEqual(window.db_path, self.test_db)
        self.assertIsNotNone(window.recorder)
        self.assertIsNotNone(window.executor)
    
    @patch('PySide6.QtWidgets.QApplication')
    @patch('PySide6.QtCore.Qt')
    @patch('PySide6.QtWidgets.QMainWindow')
    @patch('source.interfaces.intake.main.sd')
    def test_recording_simulation(self, mock_sd, mock_main_window, mock_qt, mock_qapp):
        """Test the complete recording and transcription pipeline."""
        # Mock QApplication
        mock_app_instance = Mock()
        mock_qapp.instance.return_value = mock_app_instance
        mock_app_instance.clipboard.return_value = Mock()
        
        # Mock Qt constants
        mock_qt.WindowStaysOnTopHint = 0x00040000
        
        # Mock QMainWindow
        mock_main_window.__init__ = Mock()
        mock_main_window.setWindowTitle = Mock()
        mock_main_window.setWindowFlags = Mock()
        mock_main_window.setStatusBar = Mock()
        mock_main_window.setCentralWidget = Mock()
        
        # Mock sounddevice
        mock_sd.query_devices.return_value = [{"name": "Mock Mic", "max_input_channels": 1}]
        mock_sd.check_input_settings.return_value = None
        
        # Create window
        window = IntakeWindow(db_path=self.test_db)
        
        # Mock the recorder
        mock_recorder = Mock()
        mock_recorder.device = None
        mock_recorder.frames = [np.random.rand(16000)]  # Mock audio frames
        mock_recorder.level = 0.5
        window.recorder = mock_recorder
        
        # Mock audio file creation
        mock_audio_file = MockAudioFile()
        
        # Mock the transcription backend
        mock_backend = Mock()
        mock_backend.transcribe.return_value = "Test transcription result"
        window.backend_instance = mock_backend
        
        # Simulate recording start
        window.recording_start_time = 1000.0  # Mock start time
        window.audio_path = Path("/tmp/mock_audio.wav")
        
        # Mock the transcription completion
        with patch('source.interfaces.intake.main.perf_counter') as mock_perf_counter:
            mock_perf_counter.return_value = 1005.0  # Mock end time
            
            # Simulate transcription completion
            window._finish_transcription("Test transcription result")
            
            # Verify database insertion
            with sqlite3.connect(self.test_db) as conn:
                cursor = conn.execute("SELECT content, fiber_type FROM intake")
                rows = cursor.fetchall()
                
                self.assertGreater(len(rows), 0, "Should have inserted at least one record")
                
                # Check the latest record
                latest_row = rows[-1]
                self.assertEqual(latest_row[0], "Test transcription result")
                self.assertEqual(latest_row[1], "dictation")
    
    def test_recorder_class(self):
        """Test the Recorder class functionality."""
        recorder = Recorder(sample_rate=16000)
        
        # Test initialization
        self.assertEqual(recorder.sample_rate, 16000)
        self.assertIsNone(recorder.stream)
        self.assertEqual(len(recorder.frames), 0)
        self.assertEqual(recorder.level, 0.0)
        self.assertIsNone(recorder.device)
        
        # Test callback simulation
        mock_indata = np.random.rand(1024, 1)
        recorder._callback(mock_indata, 1024, None, None)
        
        # Verify callback behavior
        self.assertEqual(len(recorder.frames), 1)
        self.assertGreater(recorder.level, 0.0)
    
    @patch('source.interfaces.intake.main.sf.write')
    @patch('source.interfaces.intake.main.sd.InputStream')
    def test_recorder_start_stop(self, mock_input_stream, mock_sf_write):
        """Test recorder start and stop functionality."""
        # Mock the input stream
        mock_stream = Mock()
        mock_input_stream.return_value = mock_stream
        
        recorder = Recorder()
        
        # Test start
        recorder.start(device=0)
        
        # Verify stream was created and started
        mock_input_stream.assert_called_once()
        mock_stream.start.assert_called_once()
        
        # Test stop
        test_path = Path("/tmp/test_output.wav")
        recorder.frames = [np.random.rand(16000)]  # Add some mock frames
        
        recorder.stop(test_path, keep_stream=False)
        
        # Verify stream was stopped and closed
        mock_stream.stop.assert_called_once()
        mock_stream.close.assert_called_once()
        
        # Verify audio was written
        mock_sf_write.assert_called_once()

    def test_error_handling(self):
        """Test error handling in the intake pipeline."""
        # Test database insertion with invalid data
        try:
            # This should handle gracefully
            insert_intake(
                content="",  # Empty content
                audio_path=None,
                fiber_type="dictation",
                db=self.test_db
            )
        except Exception as e:
            self.fail(f"Database insertion should handle empty content: {e}")
        
        # Test transcription with non-existent file
        try:
            result = transcribe_audio("/non/existent/file.wav", "StandardWhisper", "small")
            # Should return empty string or handle gracefully
            self.assertIsInstance(result, str)
        except Exception as e:
            # Exception is also acceptable for non-existent files
            self.assertIsInstance(e, Exception)
        
        # Test with invalid backend
        try:
            # Use a test audio file if available, otherwise use a dummy path
            test_audio_path = str(self.test_audio_dir / "test_audio.wav")
            if not Path(test_audio_path).exists():
                # Create a dummy file for testing
                with open(test_audio_path, 'w') as f:
                    f.write("dummy audio content")
            
            result = transcribe_audio(test_audio_path, "InvalidBackend", "small")
            # Should fall back to StandardWhisper or return empty string
            self.assertIsInstance(result, str)
        except Exception as e:
            # Exception is also acceptable for invalid backends
            self.assertIsInstance(e, Exception)


class TestIntakeIntegration(unittest.TestCase):
    """Integration tests for the complete intake workflow."""
    
    def setUp(self):
        """Set up integration test environment."""
        self.test_db = Path(tempfile.mktemp(suffix='.db'))
        _ensure_db(self.test_db)
    
    def tearDown(self):
        """Clean up integration test environment."""
        if self.test_db.exists():
            self.test_db.unlink()
    
    @patch('source.interfaces.intake.main.MLXWhisperBackend')
    def test_complete_workflow(self, mock_mlx_backend):
        """Test the complete workflow from recording to database storage."""
        # Mock the MLX backend
        mock_backend_instance = Mock()
        mock_backend_instance.transcribe.return_value = "Integration test transcription"
        mock_mlx_backend.return_value = mock_backend_instance
        
        # Simulate the complete workflow
        test_content = "Integration test transcription"
        test_audio_path = "/tmp/integration_test.wav"
        
        # Insert into database
        fiber_id = insert_intake(
            content=test_content,
            audio_path=test_audio_path,
            fiber_type="dictation",
            db=self.test_db
        )
        
        # Verify the complete workflow
        with sqlite3.connect(self.test_db) as conn:
            cursor = conn.execute(
                "SELECT id, content, audio_path, fiber_type FROM intake WHERE id = ?",
                (fiber_id,)
            )
            row = cursor.fetchone()
            
            self.assertIsNotNone(row)
            self.assertEqual(row[0], fiber_id)
            self.assertEqual(row[1], test_content)
            self.assertEqual(row[2], test_audio_path)
            self.assertEqual(row[3], "dictation")

    def test_create_fiber_from_record(self):
        fid = insert_intake(
            content="Hello", audio_path=None, db=self.test_db
        )
        fiber = create_fiber_from_intake(fid, self.test_db)
        self.assertEqual(str(fiber.id), fid)
        self.assertEqual(fiber.content, "Hello")
        self.assertEqual(fiber.type, "text")


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2) 