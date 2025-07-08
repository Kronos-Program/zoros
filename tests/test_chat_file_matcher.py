"""
Tests for Chat File Matcher

This module contains unit tests for the chat file matcher functionality,
ensuring that fuzzy matching and file operations work correctly.

Specification: docs/requirements/chat_file_matcher_requirements.md#testing
Architecture: docs/zoros_architecture.md#testing
Tests: tests/test_chat_file_matcher.py
Configuration: pytest.ini

Related Modules:
- scripts/chat_file_matcher.py - Core functionality being tested
- tests/conftest.py - Test configuration and fixtures

Dependencies:
- External libraries: pytest, pathlib
- Internal modules: scripts/chat_file_matcher.py
"""

import pytest
import tempfile
import shutil
from pathlib import Path
import sys

# Add the scripts directory to the path
sys.path.append(str(Path(__file__).parent.parent / "scripts"))

from chat_file_matcher import ChatFileMatcher, MatchResult


class TestChatFileMatcher:
    """Test cases for ChatFileMatcher class.
    
    This class contains comprehensive tests for the ChatFileMatcher
    functionality including initialization, file loading, matching,
    and file operations.
    
    Spec: docs/requirements/chat_file_matcher_requirements.md#testing
    Tests: tests/test_chat_file_matcher.py#TestChatFileMatcher
    """
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing.
        
        Returns:
            Tuple of (source_dir, target_dir, file_list_path)
            
        Spec: docs/requirements/chat_file_matcher_requirements.md#test-fixtures
        Tests: tests/test_chat_file_matcher.py#temp_dirs
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir) / "source"
            target_dir = Path(temp_dir) / "target"
            file_list_path = Path(temp_dir) / "file_list.md"
            
            # Create directories
            source_dir.mkdir()
            target_dir.mkdir()
            
            # Create some test files in source
            (source_dir / "test_file_1.md").write_text("content 1")
            (source_dir / "test_file_2.md").write_text("content 2")
            (source_dir / "different_name.md").write_text("content 3")
            
            # Create file list
            file_list_path.write_text("Test File 1\nTest File 2\nMissing File")
            
            yield source_dir, target_dir, file_list_path
    
    def test_initialization(self, temp_dirs):
        """Test ChatFileMatcher initialization.
        
        Args:
            temp_dirs: Fixture providing temporary directories
            
        Spec: docs/requirements/chat_file_matcher_requirements.md#initialization
        Tests: tests/test_chat_file_matcher.py#test_initialization
        """
        source_dir, target_dir, file_list_path = temp_dirs
        
        matcher = ChatFileMatcher(
            source_dir=str(source_dir),
            target_dir=str(target_dir),
            file_list_path=str(file_list_path)
        )
        
        assert matcher.source_dir == source_dir
        assert matcher.target_dir == target_dir
        assert matcher.file_list_path == file_list_path
        assert matcher.confidence_threshold == 80.0
    
    def test_initialization_invalid_paths(self):
        """Test ChatFileMatcher initialization with invalid paths.
        
        Spec: docs/requirements/chat_file_matcher_requirements.md#error-handling
        Tests: tests/test_chat_file_matcher.py#test_initialization_invalid_paths
        """
        with pytest.raises(ValueError, match="Source directory does not exist"):
            ChatFileMatcher(
                source_dir="nonexistent_source",
                target_dir="docs/zoros_chats",
                file_list_path="docs/zoros_chats/chat_directory.md"
            )
    
    def test_load_target_files(self, temp_dirs):
        """Test loading target files from file list.
        
        Args:
            temp_dirs: Fixture providing temporary directories
            
        Spec: docs/requirements/chat_file_matcher_requirements.md#load-target-files
        Tests: tests/test_chat_file_matcher.py#test_load_target_files
        """
        source_dir, target_dir, file_list_path = temp_dirs
        
        matcher = ChatFileMatcher(
            source_dir=str(source_dir),
            target_dir=str(target_dir),
            file_list_path=str(file_list_path)
        )
        
        target_files = matcher.load_target_files()
        
        assert len(target_files) == 3
        assert "Test File 1" in target_files
        assert "Test File 2" in target_files
        assert "Missing File" in target_files
    
    def test_get_source_files(self, temp_dirs):
        """Test getting source files from directory.
        
        Args:
            temp_dirs: Fixture providing temporary directories
            
        Spec: docs/requirements/chat_file_matcher_requirements.md#get-source-files
        Tests: tests/test_chat_file_matcher.py#test_get_source_files
        """
        source_dir, target_dir, file_list_path = temp_dirs
        
        matcher = ChatFileMatcher(
            source_dir=str(source_dir),
            target_dir=str(target_dir),
            file_list_path=str(file_list_path)
        )
        
        source_files = matcher.get_source_files()
        
        assert len(source_files) == 3
        assert "test_file_1" in source_files
        assert "test_file_2" in source_files
        assert "different_name" in source_files
    
    def test_match_files(self, temp_dirs):
        """Test fuzzy matching between target and source files.
        
        Args:
            temp_dirs: Fixture providing temporary directories
            
        Spec: docs/requirements/chat_file_matcher_requirements.md#match-files
        Tests: tests/test_chat_file_matcher.py#test_match_files
        """
        source_dir, target_dir, file_list_path = temp_dirs
        
        matcher = ChatFileMatcher(
            source_dir=str(source_dir),
            target_dir=str(target_dir),
            file_list_path=str(file_list_path),
            confidence_threshold=70.0  # Lower threshold for testing
        )
        
        results = matcher.match_files()
        
        assert len(results) == 3
        
        # Check that we found matches for the test files
        found_targets = [r.target_name for r in results if r.status == 'found']
        assert "Test File 1" in found_targets
        assert "Test File 2" in found_targets
        
        # Check that missing file is not found
        missing_results = [r for r in results if r.target_name == "Missing File"]
        assert len(missing_results) == 1
        assert missing_results[0].status == 'not_found'
    
    def test_copy_matched_files_dry_run(self, temp_dirs):
        """Test copying matched files in dry run mode.
        
        Args:
            temp_dirs: Fixture providing temporary directories
            
        Spec: docs/requirements/chat_file_matcher_requirements.md#copy-matched-files
        Tests: tests/test_chat_file_matcher.py#test_copy_matched_files_dry_run
        """
        source_dir, target_dir, file_list_path = temp_dirs
        
        matcher = ChatFileMatcher(
            source_dir=str(source_dir),
            target_dir=str(target_dir),
            file_list_path=str(file_list_path),
            confidence_threshold=70.0
        )
        
        results = matcher.match_files()
        stats = matcher.copy_matched_files(results, dry_run=True)
        
        # Check that no files were actually copied
        target_files = list(target_dir.glob("*.md"))
        assert len(target_files) == 0
        
        # Check stats
        assert stats['copied'] > 0  # Would have copied
        assert stats['errors'] == 0
    
    def test_copy_matched_files_execute(self, temp_dirs):
        """Test copying matched files in execute mode.
        
        Args:
            temp_dirs: Fixture providing temporary directories
            
        Spec: docs/requirements/chat_file_matcher_requirements.md#copy-matched-files
        Tests: tests/test_chat_file_matcher.py#test_copy_matched_files_execute
        """
        source_dir, target_dir, file_list_path = temp_dirs
        
        matcher = ChatFileMatcher(
            source_dir=str(source_dir),
            target_dir=str(target_dir),
            file_list_path=str(file_list_path),
            confidence_threshold=70.0
        )
        
        results = matcher.match_files()
        stats = matcher.copy_matched_files(results, dry_run=False)
        
        # Check that files were actually copied
        target_files = list(target_dir.glob("*.md"))
        assert len(target_files) > 0
        
        # Check stats
        assert stats['copied'] > 0
        assert stats['errors'] == 0
    
    def test_generate_report(self, temp_dirs):
        """Test report generation.
        
        Args:
            temp_dirs: Fixture providing temporary directories
            
        Spec: docs/requirements/chat_file_matcher_requirements.md#generate-report
        Tests: tests/test_chat_file_matcher.py#test_generate_report
        """
        source_dir, target_dir, file_list_path = temp_dirs
        
        matcher = ChatFileMatcher(
            source_dir=str(source_dir),
            target_dir=str(target_dir),
            file_list_path=str(file_list_path)
        )
        
        results = matcher.match_files()
        stats = {'copied': 2, 'already_exists': 0, 'not_found': 1, 'errors': 0}
        
        report = matcher.generate_report(results, stats)
        
        assert "CHAT FILE MATCHING REPORT" in report
        assert "Total target files: 3" in report
        assert "Files copied: 2" in report
        assert "Files not found: 1" in report


class TestMatchResult:
    """Test cases for MatchResult dataclass.
    
    This class contains tests for the MatchResult dataclass that
    represents individual matching results.
    
    Spec: docs/requirements/chat_file_matcher_requirements.md#match-result
    Tests: tests/test_chat_file_matcher.py#TestMatchResult
    """
    
    def test_match_result_creation(self):
        """Test MatchResult dataclass creation.
        
        Spec: docs/requirements/chat_file_matcher_requirements.md#match-result
        Tests: tests/test_chat_file_matcher.py#test_match_result_creation
        """
        result = MatchResult(
            target_name="Test File",
            source_file="test_file",
            confidence=85.5,
            status="found"
        )
        
        assert result.target_name == "Test File"
        assert result.source_file == "test_file"
        assert result.confidence == 85.5
        assert result.status == "found"
    
    def test_match_result_not_found(self):
        """Test MatchResult for not found case.
        
        Spec: docs/requirements/chat_file_matcher_requirements.md#match-result
        Tests: tests/test_chat_file_matcher.py#test_match_result_not_found
        """
        result = MatchResult(
            target_name="Missing File",
            source_file=None,
            confidence=45.2,
            status="not_found"
        )
        
        assert result.target_name == "Missing File"
        assert result.source_file is None
        assert result.confidence == 45.2
        assert result.status == "not_found"


if __name__ == "__main__":
    pytest.main([__file__]) 