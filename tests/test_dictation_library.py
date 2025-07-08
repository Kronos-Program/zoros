#!/usr/bin/env python3
"""Test suite for the dictation library UI."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sqlite3
import numpy as np
import pytest
import sys
import types

pytest.importorskip("PySide6.QtWidgets", reason="PySide6 not available")
sys.modules.setdefault("sounddevice", types.ModuleType("sounddevice"))
sys.modules.setdefault("soundfile", types.ModuleType("soundfile"))

# Import the modules we want to test
from source.interfaces.intake.dictation_library import (
    DictationItem,
    DictationLibraryWindow,
    DB_PATH,
)
from source.interfaces.intake.main import _ensure_db, insert_intake


class TestDictationItem(unittest.TestCase):
    """Test the DictationItem class."""
    
    def test_dictation_item_creation(self):
        """Test creating a DictationItem from row data."""
        row_data = {
            'id': 'test-id-123',
            'timestamp': '2025-01-01T12:00:00',
            'content': 'Test content',
            'audio_path': '/path/to/audio.wav',
            'correction': 'Corrected content',
            'fiber_type': 'dictation',
            'submitted': 1
        }
        
        item = DictationItem(row_data)
        
        self.assertEqual(item.id, 'test-id-123')
        self.assertEqual(item.content, 'Test content')
        self.assertEqual(item.audio_path, '/path/to/audio.wav')
        self.assertEqual(item.correction, 'Corrected content')
        self.assertEqual(item.fiber_type, 'dictation')
        self.assertTrue(item.submitted)
        self.assertEqual(item.status_text, "Submitted")
    
    def test_dictation_item_draft_status(self):
        """Test DictationItem with draft status."""
        row_data = {
            'id': 'test-id-456',
            'timestamp': '2025-01-01T12:00:00',
            'content': 'Draft content',
            'audio_path': None,
            'correction': None,
            'fiber_type': 'free_text',
            'submitted': 0
        }
        
        item = DictationItem(row_data)
        
        self.assertFalse(item.submitted)
        self.assertEqual(item.status_text, "Draft")
        self.assertEqual(item.display_content, "Draft content")  # Should use content when no correction
    
    def test_display_content_with_correction(self):
        """Test that display_content returns correction when available."""
        row_data = {
            'id': 'test-id',
            'timestamp': '2025-01-01T12:00:00',
            'content': 'Original content',
            'audio_path': None,
            'correction': 'Corrected content',
            'fiber_type': 'dictation',
            'submitted': 1
        }
        
        item = DictationItem(row_data)
        self.assertEqual(item.display_content, "Corrected content")


class TestDictationLibraryIntegration(unittest.TestCase):
    """Integration tests for the dictation library."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary database for testing
        self.test_db = Path(tempfile.mktemp(suffix='.db'))
        
        # Patch the global DB_PATH
        self.db_patcher = patch('source.interfaces.intake.dictation_library.DB_PATH', self.test_db)
        self.db_patcher.start()
        
        # Ensure test database is created
        _ensure_db(self.test_db)
    
    def tearDown(self):
        """Clean up test environment."""
        # Stop patches
        self.db_patcher.stop()
        
        # Clean up test files
        if self.test_db.exists():
            self.test_db.unlink()
    
    def test_database_schema_compatibility(self):
        """Test that the dictation library works with the current database schema."""
        # Insert test data
        test_content = "Test dictation content"
        test_audio_path = "/tmp/test_audio.wav"
        
        fiber_id = insert_intake(
            content=test_content,
            audio_path=test_audio_path,
            correction="Corrected test content",
            fiber_type="dictation",
            submitted=False,
            db=self.test_db
        )
        
        # Verify the data was inserted correctly
        with sqlite3.connect(self.test_db) as conn:
            cursor = conn.execute(
                "SELECT id, content, audio_path, correction, fiber_type, submitted FROM intake WHERE id = ?",
                (fiber_id,)
            )
            row = cursor.fetchone()
            
            self.assertIsNotNone(row)
            self.assertEqual(row[0], fiber_id)
            self.assertEqual(row[1], test_content)
            self.assertEqual(row[2], test_audio_path)
            self.assertEqual(row[3], "Corrected test content")
            self.assertEqual(row[4], "dictation")
            self.assertEqual(row[5], 0)  # submitted = False
    
    @patch('PySide6.QtWidgets.QApplication')
    @patch('PySide6.QtCore.Qt')
    @patch('PySide6.QtWidgets.QMainWindow')
    def test_dictation_library_window_creation(self, mock_main_window, mock_qt, mock_qapp):
        """Test that the DictationLibraryWindow can be created."""
        # Mock QApplication.instance()
        mock_app = Mock()
        mock_qapp.instance.return_value = mock_app
        
        # Create test data
        insert_intake(
            content="Test content 1",
            audio_path=None,
            fiber_type="dictation",
            submitted=True,
            db=self.test_db
        )
        
        insert_intake(
            content="Test content 2",
            audio_path=None,
            fiber_type="free_text",
            submitted=False,
            db=self.test_db
        )
        
        # Test window creation
        try:
            window = DictationLibraryWindow()
            # The window should load the dictations from the database
            self.assertIsNotNone(window.dictations)
            self.assertEqual(len(window.dictations), 2)
        except Exception as e:
            self.fail(f"Failed to create DictationLibraryWindow: {e}")


class TestDictationLibraryFilters(unittest.TestCase):
    """Test the filtering functionality of the dictation library."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_db = Path(tempfile.mktemp(suffix='.db'))
        self.db_patcher = patch('source.interfaces.intake.dictation_library.DB_PATH', self.test_db)
        self.db_patcher.start()
        _ensure_db(self.test_db)
        
        # Create test data
        self.create_test_data()
    
    def tearDown(self):
        """Clean up test environment."""
        self.db_patcher.stop()
        if self.test_db.exists():
            self.test_db.unlink()
    
    def create_test_data(self):
        """Create test dictations with various properties."""
        test_data = [
            ("dictation-1", "First dictation", "dictation", True),
            ("dictation-2", "Second dictation", "dictation", False),
            ("free-text-1", "First free text", "free_text", True),
            ("free-text-2", "Second free text", "free_text", False),
        ]
        
        for content_id, content, fiber_type, submitted in test_data:
            insert_intake(
                content=content,
                audio_path=None,
                fiber_type=fiber_type,
                submitted=submitted,
                db=self.test_db
            )
    
    @patch('PySide6.QtWidgets.QApplication')
    @patch('PySide6.QtCore.Qt')
    @patch('PySide6.QtWidgets.QMainWindow')
    def test_status_filtering(self, mock_main_window, mock_qt, mock_qapp):
        """Test filtering by submission status."""
        mock_app = Mock()
        mock_qapp.instance.return_value = mock_app
        
        window = DictationLibraryWindow()
        
        # Test "All" filter
        window.status_filter.setCurrentText("All")
        window.apply_filters()
        self.assertEqual(len(window.filtered_dictations), 4)
        
        # Test "Submitted" filter
        window.status_filter.setCurrentText("Submitted")
        window.apply_filters()
        self.assertEqual(len(window.filtered_dictations), 2)
        
        # Test "Draft" filter
        window.status_filter.setCurrentText("Draft")
        window.apply_filters()
        self.assertEqual(len(window.filtered_dictations), 2)
    
    @patch('PySide6.QtWidgets.QApplication')
    @patch('PySide6.QtCore.Qt')
    @patch('PySide6.QtWidgets.QMainWindow')
    def test_type_filtering(self, mock_main_window, mock_qt, mock_qapp):
        """Test filtering by fiber type."""
        mock_app = Mock()
        mock_qapp.instance.return_value = mock_app
        
        window = DictationLibraryWindow()
        
        # Test "All" filter
        window.type_filter.setCurrentText("All")
        window.apply_filters()
        self.assertEqual(len(window.filtered_dictations), 4)
        
        # Test "dictation" filter
        window.type_filter.setCurrentText("dictation")
        window.apply_filters()
        self.assertEqual(len(window.filtered_dictations), 2)
        
        # Test "free_text" filter
        window.type_filter.setCurrentText("free_text")
        window.apply_filters()
        self.assertEqual(len(window.filtered_dictations), 2)
    
    @patch('PySide6.QtWidgets.QApplication')
    @patch('PySide6.QtCore.Qt')
    @patch('PySide6.QtWidgets.QMainWindow')
    def test_search_filtering(self, mock_main_window, mock_qt, mock_qapp):
        """Test search functionality."""
        mock_app = Mock()
        mock_qapp.instance.return_value = mock_app
        
        window = DictationLibraryWindow()
        
        # Test search for "First"
        window.search_box.setText("First")
        window.apply_filters()
        self.assertEqual(len(window.filtered_dictations), 2)
        
        # Test search for "dictation"
        window.search_box.setText("dictation")
        window.apply_filters()
        self.assertEqual(len(window.filtered_dictations), 2)
        
        # Test search for non-existent text
        window.search_box.setText("nonexistent")
        window.apply_filters()
        self.assertEqual(len(window.filtered_dictations), 0)

    @patch('PySide6.QtWidgets.QApplication')
    @patch('PySide6.QtCore.Qt')
    @patch('PySide6.QtWidgets.QMainWindow')
    def test_retranscribe_audio(self, mock_main_window, mock_qt, mock_qapp):
        """Test retranscription functionality."""
        mock_app = Mock()
        mock_qapp.instance.return_value = mock_app
        
        # Create test data with audio path
        test_audio_path = str(self.test_audio_dir / "test_audio.wav")
        
        # Create a dummy audio file
        with open(test_audio_path, 'w') as f:
            f.write("dummy audio content")
        
        fiber_id = insert_intake(
            content="Original transcript",
            audio_path=test_audio_path,
            fiber_type="dictation",
            submitted=False,
            db=self.test_db
        )
        
        window = DictationLibraryWindow()
        
        # Find the dictation in the list
        for item in window.dictations:
            if item.id == fiber_id:
                window.current_item = item
                break
        
        # Mock the transcription function
        with patch('source.interfaces.intake.dictation_library.transcribe_audio') as mock_transcribe:
            mock_transcribe.return_value = "New retranscribed content"
            
            # Mock the settings
            with patch('source.interfaces.intake.dictation_library.load_settings') as mock_settings:
                mock_settings.return_value = {
                    "WhisperBackend": "StandardWhisper",
                    "WhisperModel": "small"
                }
                
                # Call retranscribe
                window.retranscribe_audio()
                
                # Verify transcription was called
                mock_transcribe.assert_called_once_with(test_audio_path, "StandardWhisper", "small")
                
                # Verify database was updated
                with sqlite3.connect(self.test_db) as conn:
                    cursor = conn.execute(
                        "SELECT content, correction FROM intake WHERE id = ?",
                        (fiber_id,)
                    )
                    row = cursor.fetchone()
                    self.assertEqual(row[0], "New retranscribed content")
                    self.assertEqual(row[1], "New retranscribed content")


if __name__ == "__main__":
    unittest.main() 