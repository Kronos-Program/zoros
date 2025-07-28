"""
Audio Test Panel for Intake UI

This module provides a UI panel for managing audio files for testing and benchmarking.
It integrates with the main intake interface to provide easy access to audio file
management features.

Spec: docs/streaming_backend_plan.md#test-data
Tests: tests/test_intake_pipeline.py
Integration: source/interfaces/intake/main.py#IntakeWindow

Dependencies:
- PySide6 for UI components
- scripts/audio_file_manager.py for backend functionality

Usage Example:
    # Create and show the audio test panel
    from source.interfaces.intake.audio_test_panel import AudioTestPanel
    from PySide6.QtWidgets import QApplication
    
    app = QApplication([])
    panel = AudioTestPanel()
    panel.show()
    
    # The panel provides:
    # - "List Test Files" button: Shows available test audio files
    # - "Copy Latest" button: Copies most recent recording to test assets
    # - "Generate Test Audio" button: Creates synthetic test files
    # - "Cleanup" button: Removes old test files
    # - File list display with timestamps and sizes
    # - Progress bar for long operations
    # - Status messages for operation feedback
"""

from pathlib import Path
from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QInputDialog,
    QProgressBar,
    QGroupBox,
    QTextEdit,
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
import time


class AudioFileManagerThread(QThread):
    """Background thread for audio file management operations."""
    
    # Signals for UI updates
    file_list_updated = Signal(list)
    operation_completed = Signal(str, bool, str)  # operation, success, message
    progress_updated = Signal(int, str)  # progress, status
    
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.operation = None
        self.args = {}
    
    def run(self):
        """Run the requested operation."""
        try:
            if self.operation == "list":
                self.progress_updated.emit(50, "Listing audio files...")
                files = self.manager.list_test_audio_files()
                self.file_list_updated.emit(files)
                self.operation_completed.emit("list", True, f"Found {len(files)} files")
                
            elif self.operation == "copy_latest":
                self.progress_updated.emit(25, "Finding latest audio file...")
                filename = self.args.get("filename")
                result = self.manager.copy_latest_to_test_assets(filename)
                if result:
                    self.progress_updated.emit(100, "Copy completed")
                    self.operation_completed.emit("copy", True, f"Copied to {result.name}")
                else:
                    self.operation_completed.emit("copy", False, "No audio file found or copy failed")
                    
            elif self.operation == "generate":
                self.progress_updated.emit(25, "Generating test audio...")
                duration = self.args.get("duration", 30)
                filename = self.args.get("filename")
                result = self.manager.generate_test_audio(duration, filename)
                if result:
                    self.progress_updated.emit(100, "Generation completed")
                    self.operation_completed.emit("generate", True, f"Generated {result.name}")
                else:
                    self.operation_completed.emit("generate", False, "Generation failed")
                    
        except Exception as e:
            self.operation_completed.emit(self.operation, False, str(e))


class AudioTestPanel(QWidget):
    """UI panel for audio file management and testing."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = None
        self.worker_thread = None
        self.setup_ui()
        self.load_manager()
    
    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("Audio Test Management")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        # File list
        self.file_group = QGroupBox("Test Audio Files")
        file_layout = QVBoxLayout(self.file_group)
        
        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(200)
        file_layout.addWidget(self.file_list)
        
        # File list buttons
        file_btn_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_file_list)
        file_btn_layout.addWidget(self.refresh_btn)
        
        self.copy_latest_btn = QPushButton("Copy Latest")
        self.copy_latest_btn.clicked.connect(self.copy_latest_audio)
        file_btn_layout.addWidget(self.copy_latest_btn)
        
        self.generate_btn = QPushButton("Generate Test")
        self.generate_btn.clicked.connect(self.generate_test_audio)
        file_btn_layout.addWidget(self.generate_btn)
        
        file_layout.addLayout(file_btn_layout)
        layout.addWidget(self.file_group)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Status
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.status_label)
        
        # Log
        self.log_group = QGroupBox("Operation Log")
        log_layout = QVBoxLayout(self.log_group)
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(100)
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        layout.addWidget(self.log_group)
        
        # Auto-refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_file_list)
        self.refresh_timer.start(30000)  # Refresh every 30 seconds
    
    def load_manager(self):
        """Load the audio file manager."""
        try:
            from scripts.audio_file_manager import AudioFileManager
            self.manager = AudioFileManager()
            self.log_message("Audio file manager loaded successfully")
            self.refresh_file_list()
        except Exception as e:
            self.log_message(f"Error loading audio file manager: {e}", error=True)
    
    def refresh_file_list(self):
        """Refresh the list of test audio files."""
        if not self.manager:
            return
        
        self.start_operation("list")
    
    def copy_latest_audio(self):
        """Copy the latest recorded audio to test assets."""
        if not self.manager:
            return
        
        # Ask for custom filename
        filename, ok = QInputDialog.getText(
            self, "Copy Latest Audio", 
            "Enter filename (leave empty for auto-generated):"
        )
        
        if ok:
            self.start_operation("copy_latest", {"filename": filename if filename else None})
    
    def generate_test_audio(self):
        """Generate a test audio file."""
        if not self.manager:
            return
        
        # Ask for duration
        duration, ok = QInputDialog.getDouble(
            self, "Generate Test Audio", 
            "Duration (seconds):", 30.0, 1.0, 3600.0, 1
        )
        
        if ok:
            # Ask for filename
            filename, ok = QInputDialog.getText(
                self, "Generate Test Audio", 
                "Enter filename (leave empty for auto-generated):"
            )
            
            if ok:
                self.start_operation("generate", {
                    "duration": duration,
                    "filename": filename if filename else None
                })
    
    def start_operation(self, operation: str, args: dict = None):
        """Start a background operation."""
        if self.worker_thread and self.worker_thread.isRunning():
            self.log_message("Operation already in progress", error=True)
            return
        
        self.worker_thread = AudioFileManagerThread(self.manager)
        self.worker_thread.operation = operation
        self.worker_thread.args = args or {}
        
        # Connect signals
        self.worker_thread.file_list_updated.connect(self.update_file_list)
        self.worker_thread.operation_completed.connect(self.operation_finished)
        self.worker_thread.progress_updated.connect(self.update_progress)
        
        # Update UI
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText(f"Running {operation}...")
        
        # Start operation
        self.worker_thread.start()
    
    def update_file_list(self, files: List[Path]):
        """Update the file list display."""
        self.file_list.clear()
        
        for file_path in files:
            try:
                # Get file info
                size_kb = file_path.stat().st_size / 1024
                modified = time.ctime(file_path.stat().st_mtime)
                duration = self.manager.get_audio_duration(file_path)
                
                # Create display text
                display_text = f"{file_path.name} ({duration:.1f}s, {size_kb:.1f}KB)"
                
                # Create list item
                item = QListWidgetItem(display_text)
                item.setData(Qt.UserRole, str(file_path))
                item.setToolTip(f"Modified: {modified}\nPath: {file_path}")
                
                self.file_list.addItem(item)
                
            except Exception as e:
                # Add item with error
                item = QListWidgetItem(f"{file_path.name} (ERROR)")
                item.setData(Qt.UserRole, str(file_path))
                item.setToolTip(f"Error: {e}")
                self.file_list.addItem(item)
    
    def operation_finished(self, operation: str, success: bool, message: str):
        """Handle operation completion."""
        # Hide progress bar
        self.progress_bar.setVisible(False)
        
        # Update status
        if success:
            self.status_label.setText(f"{operation} completed successfully")
            self.status_label.setStyleSheet("color: green;")
            self.log_message(f"✅ {operation}: {message}")
        else:
            self.status_label.setText(f"{operation} failed")
            self.status_label.setStyleSheet("color: red;")
            self.log_message(f"❌ {operation}: {message}", error=True)
        
        # Reset status after 3 seconds
        QTimer.singleShot(3000, self.reset_status)
        
        # Refresh file list if operation modified files
        if operation in ["copy", "generate"]:
            self.refresh_file_list()
    
    def update_progress(self, value: int, status: str):
        """Update progress bar and status."""
        self.progress_bar.setValue(value)
        self.status_label.setText(status)
    
    def reset_status(self):
        """Reset status label to default."""
        self.status_label.setText("Ready")
        self.status_label.setStyleSheet("color: gray; font-style: italic;")
    
    def log_message(self, message: str, error: bool = False):
        """Add a message to the log."""
        timestamp = time.strftime("%H:%M:%S")
        color = "red" if error else "black"
        log_entry = f'<span style="color: {color}">[{timestamp}] {message}</span>'
        
        self.log_text.append(log_entry)
        
        # Scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def get_selected_file(self) -> Optional[Path]:
        """Get the currently selected file path."""
        current_item = self.file_list.currentItem()
        if current_item:
            return Path(current_item.data(Qt.UserRole))
        return None
    
    def get_all_files(self) -> List[Path]:
        """Get all listed file paths."""
        files = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            file_path = Path(item.data(Qt.UserRole))
            files.append(file_path)
        return files 