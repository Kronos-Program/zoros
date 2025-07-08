"""
ZorOS Dictation Library - Management Interface

This module provides a comprehensive PySide6-based interface for viewing,
editing, and managing all dictation objects stored in the intake database.
It supports filtering, searching, audio playback, and content editing
capabilities for both submitted and draft dictations.

Specification: docs/requirements/dictation_requirements.md#data-model
Architecture: docs/zoros_architecture.md#ui-blueprint
Tests: tests/test_dictation_library.py
Database: source/interfaces/intake/main.py#_ensure_db
Configuration: source/interfaces/intake/main.py#load_settings

Related Modules:
- source/interfaces/intake/main.py - Main intake UI
- docs/dictation_library.md - Library documentation
- docs/dictation.md - Workflow documentation

Dependencies:
- External libraries: PySide6, sqlite3
- Internal modules: source.interfaces.intake.main
- Database: zoros_intake.db

Example usage:
    python -m source.interfaces.intake.dictation_library
"""
from __future__ import annotations

import json
from zoros.logger import get_logger
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from time import perf_counter

from PySide6.QtCore import QDate, Qt, Slot, QUrl, QTimer, Signal
from PySide6.QtGui import QAction, QFont, QColor
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QTabWidget,
    QCheckBox,
    QGroupBox,
    QFormLayout,
    QSpinBox,
    QProgressBar,
    QStatusBar,
)

# Import from the main intake module
from .main import DB_PATH, _ensure_db, insert_intake

logger = get_logger(__name__)


class DictationItem:
    """Represents a single dictation item from the database.
    
    This class encapsulates a dictation record from the database,
    providing convenient access to its properties and computed
    values like status text and display content.
    
    Spec: docs/requirements/dictation_requirements.md#data-model
    Tests: tests/test_dictation_library.py#TestDictationItem
    Usage: source/interfaces/intake/dictation_library.py#DictationLibraryWindow
    
    Dependencies:
    - datetime for timestamp parsing
    - PySide6.QtGui for color representation
    """
    
    def __init__(self, row_data: Dict[str, Any]):
        self.id = row_data.get('id', '')
        self.timestamp = row_data.get('timestamp', '')
        self.content = row_data.get('content', '')
        self.audio_path = row_data.get('audio_path', '')
        self.correction = row_data.get('correction', '')
        self.fiber_type = row_data.get('fiber_type', 'dictation')
        self.submitted = bool(row_data.get('submitted', True))
        
        # Parse timestamp for display
        try:
            self.datetime = datetime.fromisoformat(self.timestamp)
        except:
            self.datetime = datetime.now()
    
    @property
    def display_content(self) -> str:
        """Return the content to display (correction if available, otherwise content)."""
        return self.correction if self.correction else self.content
    
    @property
    def status_text(self) -> str:
        """Return human-readable status."""
        return "Submitted" if self.submitted else "Draft"
    
    @property
    def status_color(self) -> QColor:
        """Return color for status display."""
        return QColor(0, 128, 0) if self.submitted else QColor(255, 165, 0)  # Green for submitted, orange for draft


class DictationLibraryWindow(QMainWindow):
    """Main dictation library window.
    
    This class provides the primary interface for managing dictation objects,
    including viewing, filtering, editing, and exporting dictations. It
    integrates with the intake database and provides audio playback
    capabilities.
    
    Spec: docs/requirements/dictation_requirements.md#data-model
    Tests: tests/test_dictation_library.py#TestDictationLibraryIntegration
    Integration: source/interfaces/intake/main.py#open_dictation_library
    
    Dependencies:
    - PySide6 for UI components
    - SQLite for database access
    - source.interfaces.intake.main for database operations
    """
    
    # Signal for status updates
    status_updated = Signal(str)
    
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Dictation Library")
        self.setMinimumSize(1200, 800)
        
        # Set window icon
        icon_path = Path(__file__).resolve().parents[3] / "assets" / "icon.png"
        if icon_path.exists():
            from PySide6.QtGui import QIcon
            self.setWindowIcon(QIcon(str(icon_path)))
        
        # Database connection - will be created/closed as needed
        self.conn = None
        
        # Data storage
        self.dictations: List[DictationItem] = []
        self.filtered_dictations: List[DictationItem] = []
        self.current_item: Optional[DictationItem] = None
        
        # Audio playback
        self.player: Optional[QMediaPlayer] = None
        self.audio_output: Optional[QAudioOutput] = None
        
        # Auto-refresh timer
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start(5000)  # Refresh every 5 seconds
        
        self._build_ui()
        self.load_dictations()
    
    def _build_ui(self) -> None:
        """Build the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel: Filters and table
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)
        
        # Right panel: Detail view
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)
        
        # Set initial splitter sizes
        splitter.setSizes([600, 600])
        
        main_layout.addWidget(splitter)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_updated.connect(self.status_bar.showMessage)
    
    def _create_left_panel(self) -> QWidget:
        """Create the left panel with filters and dictation table."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Filters group
        filters_group = QGroupBox("Filters")
        filters_layout = QFormLayout(filters_group)
        
        # Status filter
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "Draft", "Submitted"])
        self.status_filter.currentTextChanged.connect(self.apply_filters)
        filters_layout.addRow("Status:", self.status_filter)
        
        # Type filter
        self.type_filter = QComboBox()
        self.type_filter.addItems(["All", "dictation", "free_text"])
        self.type_filter.currentTextChanged.connect(self.apply_filters)
        filters_layout.addRow("Type:", self.type_filter)
        
        # Date range
        date_layout = QHBoxLayout()
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        self.start_date.dateChanged.connect(self.apply_filters)
        
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        self.end_date.dateChanged.connect(self.apply_filters)
        
        # Set default date range (30 days back to 7 days forward)
        from PySide6.QtCore import QDate
        self.start_date.setDate(QDate.currentDate().addDays(-30))
        self.end_date.setDate(QDate.currentDate().addDays(7))
        
        date_layout.addWidget(QLabel("From:"))
        date_layout.addWidget(self.start_date)
        date_layout.addWidget(QLabel("To:"))
        date_layout.addWidget(self.end_date)
        filters_layout.addRow("Date Range:", date_layout)
        
        # Search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search content...")
        self.search_box.textChanged.connect(self.apply_filters)
        filters_layout.addRow("Search:", self.search_box)
        
        layout.addWidget(filters_group)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "ID", "Status", "Type", "Date", "Duration", "Content Preview", "Audio"
        ])
        
        # Set column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # ID
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Status
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Type
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Date
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Duration
        header.setSectionResizeMode(5, QHeaderView.Stretch)           # Content
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Audio
        
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addWidget(self.table)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_data)
        button_layout.addWidget(self.refresh_btn)
        
        self.new_dictation_btn = QPushButton("New Dictation")
        self.new_dictation_btn.clicked.connect(self.create_new_dictation)
        button_layout.addWidget(self.new_dictation_btn)
        
        self.export_btn = QPushButton("Export")
        self.export_btn.clicked.connect(self.export_dictations)
        button_layout.addWidget(self.export_btn)
        
        self.recovery_btn = QPushButton("🔧 Recovery Tool")
        self.recovery_btn.clicked.connect(self.open_recovery_tool)
        self.recovery_btn.setToolTip("Open dictation recovery and performance analysis tool")
        button_layout.addWidget(self.recovery_btn)
        
        layout.addLayout(button_layout)
        
        return panel
    
    def _create_right_panel(self) -> QWidget:
        """Create the right panel with detail view and editing."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Detail tabs
        self.detail_tabs = QTabWidget()
        
        # Content tab
        content_tab = QWidget()
        content_layout = QVBoxLayout(content_tab)
        
        content_layout.addWidget(QLabel("Content:"))
        self.content_edit = QTextEdit()
        self.content_edit.textChanged.connect(self.on_content_changed)
        content_layout.addWidget(self.content_edit)
        
        self.detail_tabs.addTab(content_tab, "Content")
        
        # Metadata tab
        metadata_tab = QWidget()
        metadata_layout = QVBoxLayout(metadata_tab)
        
        # Metadata form
        metadata_form = QFormLayout()
        
        self.id_label = QLabel()
        metadata_form.addRow("ID:", self.id_label)
        
        self.timestamp_label = QLabel()
        metadata_form.addRow("Created:", self.timestamp_label)
        
        self.status_label = QLabel()
        metadata_form.addRow("Status:", self.status_label)
        
        self.type_label = QLabel()
        metadata_form.addRow("Type:", self.type_label)
        
        self.audio_path_label = QLabel()
        metadata_form.addRow("Audio Path:", self.audio_path_label)
        
        metadata_layout.addLayout(metadata_form)
        
        # Audio controls
        audio_group = QGroupBox("Audio")
        audio_layout = QVBoxLayout(audio_group)
        
        self.play_btn = QPushButton("Play Audio")
        self.play_btn.clicked.connect(self.play_audio)
        audio_layout.addWidget(self.play_btn)
        
        self.audio_progress = QProgressBar()
        self.audio_progress.setVisible(False)
        audio_layout.addWidget(self.audio_progress)
        
        metadata_layout.addWidget(audio_group)
        metadata_layout.addStretch()
        
        self.detail_tabs.addTab(metadata_tab, "Metadata")
        
        layout.addWidget(self.detail_tabs)
        
        # Action buttons
        action_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("Save Changes")
        self.save_btn.clicked.connect(self.save_changes)
        self.save_btn.setEnabled(False)
        action_layout.addWidget(self.save_btn)
        
        self.submit_btn = QPushButton("Mark as Submitted")
        self.submit_btn.clicked.connect(self.mark_as_submitted)
        self.submit_btn.setEnabled(False)
        action_layout.addWidget(self.submit_btn)
        
        self.retranscribe_btn = QPushButton("🔄 Retranscribe")
        self.retranscribe_btn.clicked.connect(self.retranscribe_audio)
        self.retranscribe_btn.setEnabled(False)
        action_layout.addWidget(self.retranscribe_btn)
        
        self.send_to_test_btn = QPushButton("🧪 Send to Test")
        self.send_to_test_btn.clicked.connect(self.send_to_test_assets)
        self.send_to_test_btn.setEnabled(False)
        action_layout.addWidget(self.send_to_test_btn)
        
        self.delete_btn = QPushButton("🗑️ Delete")
        self.delete_btn.clicked.connect(self.delete_dictation)
        self.delete_btn.setEnabled(False)
        action_layout.addWidget(self.delete_btn)
        
        layout.addLayout(action_layout)
        
        return panel
    
    def _get_db_connection(self):
        """Get a database connection, creating one if needed."""
        try:
            _ensure_db(DB_PATH)  # Ensure database exists with correct schema
            return sqlite3.connect(DB_PATH)
        except Exception as e:
            logger.error(f"Error creating database connection: {e}")
            raise
    
    def load_dictations(self) -> None:
        """Load all dictations from the database."""
        try:
            conn = self._get_db_connection()
            cursor = conn.execute("""
                SELECT id, timestamp, content, audio_path, correction, fiber_type, submitted
                FROM intake
                ORDER BY timestamp DESC
            """)
            
            self.dictations = []
            for row in cursor.fetchall():
                item = DictationItem({
                    'id': row[0],
                    'timestamp': row[1],
                    'content': row[2],
                    'audio_path': row[3],
                    'correction': row[4],
                    'fiber_type': row[5],
                    'submitted': row[6]
                })
                self.dictations.append(item)
            
            conn.close()
            self.apply_filters()
            self.status_updated.emit(f"Loaded {len(self.dictations)} dictations")
            
        except Exception as e:
            logger.error(f"Error loading dictations: {e}")
            self.status_updated.emit(f"Error loading dictations: {e}")
    
    def apply_filters(self) -> None:
        """Apply current filters to the dictation list."""
        status_filter = self.status_filter.currentText()
        type_filter = self.type_filter.currentText()
        search_text = self.search_box.text().lower()
        
        start_date = self.start_date.date().toPython() if self.start_date.date().isValid() else None
        end_date = self.end_date.date().toPython() if self.end_date.date().isValid() else None
        
        self.filtered_dictations = []
        
        for item in self.dictations:
            # Status filter
            if status_filter != "All":
                if status_filter == "Draft" and item.submitted:
                    continue
                if status_filter == "Submitted" and not item.submitted:
                    continue
            
            # Type filter
            if type_filter != "All" and item.fiber_type != type_filter:
                continue
            
            # Search filter
            if search_text and search_text not in item.display_content.lower():
                continue
            
            # Date filter
            if start_date and item.datetime.date() < start_date:
                continue
            if end_date and item.datetime.date() > end_date:
                continue
            
            self.filtered_dictations.append(item)
        
        self.populate_table()
        self.status_updated.emit(f"Showing {len(self.filtered_dictations)} of {len(self.dictations)} dictations")
    
    def populate_table(self) -> None:
        """Populate the table with filtered dictations."""
        self.table.setRowCount(len(self.filtered_dictations))
        
        for row, item in enumerate(self.filtered_dictations):
            # ID
            id_item = QTableWidgetItem(item.id[:8] + "...")  # Truncate long IDs
            id_item.setData(Qt.UserRole, item.id)
            self.table.setItem(row, 0, id_item)
            
            # Status
            status_item = QTableWidgetItem(item.status_text)
            status_item.setForeground(item.status_color)
            self.table.setItem(row, 1, status_item)
            
            # Type
            type_item = QTableWidgetItem(item.fiber_type)
            self.table.setItem(row, 2, type_item)
            
            # Date
            date_item = QTableWidgetItem(item.datetime.strftime("%Y-%m-%d %H:%M"))
            self.table.setItem(row, 3, date_item)
            
            # Duration
            duration = self.get_audio_duration(item.audio_path) if item.audio_path else 0.0
            duration_item = QTableWidgetItem(f"{duration:.1f}s" if duration > 0 else "N/A")
            self.table.setItem(row, 4, duration_item)
            
            # Content preview
            preview = item.display_content[:50] + "..." if len(item.display_content) > 50 else item.display_content
            content_item = QTableWidgetItem(preview)
            self.table.setItem(row, 5, content_item)
            
            # Audio indicator
            audio_icon = "🔊" if item.audio_path and Path(item.audio_path).exists() else "🔇"
            audio_item = QTableWidgetItem(audio_icon)
            self.table.setItem(row, 6, audio_item)
        
        # Select first row if available
        if self.filtered_dictations and self.table.rowCount() > 0:
            self.table.selectRow(0)
    
    def on_selection_changed(self) -> None:
        """Handle table selection changes."""
        current_row = self.table.currentRow()
        if current_row >= 0 and current_row < len(self.filtered_dictations):
            self.current_item = self.filtered_dictations[current_row]
            self.show_item_details()
        else:
            self.current_item = None
            self.clear_details()
    
    def show_item_details(self) -> None:
        """Show details for the selected item."""
        if not self.current_item:
            return
        
        # Update content editor
        self.content_edit.setPlainText(self.current_item.display_content)
        
        # Update metadata
        self.id_label.setText(self.current_item.id)
        self.timestamp_label.setText(self.current_item.datetime.strftime("%Y-%m-%d %H:%M:%S"))
        self.status_label.setText(self.current_item.status_text)
        self.status_label.setStyleSheet(f"color: {self.current_item.status_color.name()}")
        self.type_label.setText(self.current_item.fiber_type)
        self.audio_path_label.setText(self.current_item.audio_path or "None")
        
        # Update audio button
        if self.current_item.audio_path and Path(self.current_item.audio_path).exists():
            self.play_btn.setEnabled(True)
            self.play_btn.setText("Play Audio")
        else:
            self.play_btn.setEnabled(False)
            self.play_btn.setText("No Audio")
        
        # Enable action buttons
        self.save_btn.setEnabled(True)
        self.submit_btn.setEnabled(not self.current_item.submitted)
        # Fix boolean conversion for setEnabled
        has_audio = bool(self.current_item.audio_path and Path(self.current_item.audio_path).exists()) if self.current_item.audio_path else False
        self.retranscribe_btn.setEnabled(has_audio)
        self.send_to_test_btn.setEnabled(has_audio)
        self.delete_btn.setEnabled(True)
    
    def clear_details(self) -> None:
        """Clear the detail view."""
        self.content_edit.clear()
        self.id_label.clear()
        self.timestamp_label.clear()
        self.status_label.clear()
        self.type_label.clear()
        self.audio_path_label.clear()
        
        self.play_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.submit_btn.setEnabled(False)
        self.retranscribe_btn.setEnabled(False)
        self.send_to_test_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
    
    def on_content_changed(self) -> None:
        """Handle content editor changes."""
        if self.current_item:
            # Enable save button when content changes
            self.save_btn.setEnabled(True)
    
    def save_changes(self) -> None:
        """Save changes to the current dictation."""
        if not self.current_item:
            return
        
        try:
            new_content = self.content_edit.toPlainText()
            
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    "UPDATE intake SET content = ?, correction = ? WHERE id = ?",
                    (new_content, new_content, self.current_item.id)
                )
                conn.commit()
            
            # Update local data
            self.current_item.content = new_content
            self.current_item.correction = new_content
            
            self.save_btn.setEnabled(False)
            self.status_updated.emit("Changes saved successfully")
            
            # Refresh the table to show updated content
            self.refresh_data()
            
        except Exception as e:
            logger.error(f"Error saving changes: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save changes: {e}")
    
    def mark_as_submitted(self) -> None:
        """Mark the current dictation as submitted."""
        if not self.current_item:
            return
        
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    "UPDATE intake SET submitted = 1 WHERE id = ?",
                    (self.current_item.id,)
                )
                conn.commit()
            
            # Update local data
            self.current_item.submitted = True
            
            self.submit_btn.setEnabled(False)
            self.status_updated.emit("Dictation marked as submitted")
            
            # Refresh the table to show updated status
            self.refresh_data()
            
        except Exception as e:
            logger.error(f"Error marking as submitted: {e}")
            QMessageBox.critical(self, "Error", f"Failed to mark as submitted: {e}")
    
    def delete_dictation(self) -> None:
        """Delete the current dictation."""
        if not self.current_item:
            return
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete this dictation?\n\n{self.current_item.display_content[:100]}...",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("DELETE FROM intake WHERE id = ?", (self.current_item.id,))
                    conn.commit()
                
                self.status_updated.emit("Dictation deleted")
                self.refresh_data()
                
            except Exception as e:
                logger.error(f"Error deleting dictation: {e}")
                QMessageBox.critical(self, "Error", f"Failed to delete dictation: {e}")
    
    def play_audio(self) -> None:
        """Play the audio for the current dictation."""
        if not self.current_item or not self.current_item.audio_path:
            return
        
        audio_path = Path(self.current_item.audio_path)
        if not audio_path.exists():
            QMessageBox.warning(self, "Audio Not Found", f"Audio file not found: {audio_path}")
            return
        
        try:
            if not self.player:
                self.player = QMediaPlayer()
                self.audio_output = QAudioOutput()
                self.player.setAudioOutput(self.audio_output)
            
            self.player.setSource(QUrl.fromLocalFile(str(audio_path)))
            self.player.play()
            
            self.play_btn.setText("Playing...")
            self.status_updated.emit("Playing audio...")
            
        except Exception as e:
            logger.error(f"Error playing audio: {e}")
            QMessageBox.critical(self, "Audio Error", f"Failed to play audio: {e}")
    
    def create_new_dictation(self) -> None:
        """Create a new empty dictation."""
        try:
            # Create a new dictation with empty content
            fiber_id = insert_intake(
                content="",
                audio_path=None,
                fiber_type="free_text",
                submitted=False
            )
            
            self.status_updated.emit("New dictation created")
            self.refresh_data()
            
            # Select the new dictation
            for i, item in enumerate(self.filtered_dictations):
                if item.id == fiber_id:
                    self.table.selectRow(i)
                    break
                    
        except Exception as e:
            logger.error(f"Error creating new dictation: {e}")
            QMessageBox.critical(self, "Error", f"Failed to create new dictation: {e}")
    
    def export_dictations(self) -> None:
        """Export dictations to JSON.

        Spec: docs/requirements/dictation_requirements.md#data-model
        Tests: tests/test_dictation_library.py#test_export_dictations
        """
        try:
            export_path = Path("artifacts") / "dictations_export.json"
            export_path.parent.mkdir(exist_ok=True)
            
            export_data = []
            for item in self.filtered_dictations:
                export_data.append({
                    'id': item.id,
                    'timestamp': item.timestamp,
                    'content': item.content,
                    'correction': item.correction,
                    'audio_path': item.audio_path,
                    'fiber_type': item.fiber_type,
                    'submitted': item.submitted,
                    'status': item.status_text
                })
            
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            self.status_updated.emit(f"Exported {len(export_data)} dictations to {export_path}")
            
        except Exception as e:
            logger.error(f"Error exporting dictations: {e}")
            QMessageBox.critical(self, "Export Error", f"Failed to export dictations: {e}")
    
    def open_recovery_tool(self) -> None:
        """Open the dictation recovery and performance analysis tool.
        
        This launches a Streamlit interface for recovering failed transcriptions,
        batch reprocessing with different backends, and performance benchmarking.
        """
        try:
            import subprocess
            import sys
            from pathlib import Path
            
            # Launch the recovery tool as a Streamlit app
            recovery_script = Path(__file__).parent.parent / "dictation_recovery.py"
            
            if not recovery_script.exists():
                QMessageBox.warning(
                    self, 
                    "Recovery Tool Not Found", 
                    f"Recovery tool not found at {recovery_script}"
                )
                return
            
            # Launch Streamlit app
            cmd = [
                sys.executable, "-m", "streamlit", "run", 
                str(recovery_script), "--server.port", "8502"
            ]
            
            logger.info(f"Launching recovery tool: {' '.join(cmd)}")
            subprocess.Popen(cmd, cwd=str(Path(__file__).parent.parent.parent))
            
            self.status_updated.emit("Recovery tool launched on http://localhost:8502")
            
            # Also show quick info about recovery directory
            recovery_dir = Path.home() / ".zoros" / "recovery"
            if recovery_dir.exists():
                audio_files = list(recovery_dir.glob("*.wav"))
                recovery_log = recovery_dir / "recovery_log.json"
                
                info_msg = f"Recovery directory: {recovery_dir}\n"
                info_msg += f"Audio files available: {len(audio_files)}\n"
                
                if recovery_log.exists():
                    try:
                        with open(recovery_log, 'r') as f:
                            log_data = json.load(f)
                        info_msg += f"Recovery log entries: {len(log_data)}"
                    except:
                        info_msg += "Recovery log: error reading"
                else:
                    info_msg += "Recovery log: not found"
                
                QMessageBox.information(
                    self,
                    "Recovery Tool",
                    f"Recovery tool launching...\n\n{info_msg}\n\nAccess at: http://localhost:8502"
                )
            else:
                QMessageBox.information(
                    self,
                    "Recovery Tool",
                    "Recovery tool launched at http://localhost:8502\n\nNo recovery files found yet."
                )
            
        except Exception as e:
            logger.error(f"Error launching recovery tool: {e}")
            QMessageBox.critical(
                self, 
                "Launch Error", 
                f"Failed to launch recovery tool: {e}\n\n"
                f"Make sure Streamlit is installed:\npip install streamlit"
            )
    
    def refresh_data(self) -> None:
        """Refresh the data from the database.

        Tests: tests/test_dictation_library.py#test_refresh_data
        """
        self.load_dictations()
    
    def retranscribe_audio(self) -> None:
        """Retranscribe the audio for the current dictation.
        
        This method re-processes the audio file using the current
        transcription backend and updates the dictation content.
        
        Spec: docs/requirements/dictation_requirements.md#transcription-pipeline
        Tests: tests/test_dictation_library.py#test_retranscribe_audio
        Integration: source/interfaces/intake/main.py#transcribe_audio
        """
        if not self.current_item or not self.current_item.audio_path:
            QMessageBox.warning(self, "No Audio", "No audio file available for retranscription")
            return
        
        audio_path = Path(self.current_item.audio_path)
        if not audio_path.exists():
            QMessageBox.warning(self, "Audio Not Found", f"Audio file not found: {audio_path}")
            return
        
        try:
            # Show progress dialog
            progress_dialog = QMessageBox(self)
            progress_dialog.setWindowTitle("Retranscribing")
            progress_dialog.setText("Retranscribing audio...\nThis may take a few moments.")
            progress_dialog.setStandardButtons(QMessageBox.NoButton)
            progress_dialog.show()
            
            # Force UI update
            QApplication.processEvents()
            
            # Import transcription function
            from .main import transcribe_audio
            
            # Get current settings for backend and model
            from .main import load_settings
            settings = load_settings()
            backend = settings.get("WhisperBackend", "StandardWhisper")
            model = settings.get("WhisperModel", "small")
            
            print(f"DEBUG: Retranscribing {audio_path} with {backend}/{model}")
            
            # Perform transcription
            start_time = perf_counter()
            new_transcript = transcribe_audio(str(audio_path), backend, model)
            transcription_time = perf_counter() - start_time
            
            print(f"DEBUG: Retranscription completed in {transcription_time:.2f}s")
            print(f"DEBUG: New transcript: {new_transcript[:100]}...")
            
            # Close progress dialog
            progress_dialog.close()
            
            if new_transcript:
                # Update the content editor
                self.content_edit.setPlainText(new_transcript)
                
                # Update database
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute(
                        "UPDATE intake SET content = ?, correction = ? WHERE id = ?",
                        (new_transcript, new_transcript, self.current_item.id)
                    )
                    conn.commit()
                
                # Update local data
                self.current_item.content = new_transcript
                self.current_item.correction = new_transcript
                
                self.status_updated.emit(f"Retranscription completed in {transcription_time:.2f}s")
                
                # Refresh the table to show updated content
                self.refresh_data()
                
                QMessageBox.information(self, "Retranscription Complete", 
                                       f"Audio retranscribed successfully in {transcription_time:.2f} seconds.")
            else:
                QMessageBox.warning(self, "Retranscription Failed", 
                                   "No transcript was generated. Please check the audio file.")
                
        except Exception as e:
            logger.error(f"Error retranscribing audio: {e}")
            QMessageBox.critical(self, "Retranscription Error", f"Failed to retranscribe audio: {e}")
    
    def get_audio_duration(self, audio_path: str) -> float:
        """Get the duration of an audio file in seconds."""
        if not audio_path:
            return 0.0
        
        try:
            import soundfile as sf
            info = sf.info(audio_path)
            return info.duration
        except Exception as e:
            logger.error(f"Error getting audio duration: {e}")
            return 0.0
    
    def send_to_test_assets(self) -> None:
        """Send the current dictation's audio file to test assets."""
        if not self.current_item or not self.current_item.audio_path:
            QMessageBox.warning(self, "Warning", "No audio file available for this dictation.")
            return
        
        try:
            from scripts.audio_file_manager import AudioFileManager
            manager = AudioFileManager()
            
            # Copy the dictation to test assets
            result = manager.copy_dictation_to_test_assets(self.current_item.id)
            
            if result:
                QMessageBox.information(self, "Success", 
                    f"Audio file copied to test assets:\n{result.name}")
                self.status_updated.emit(f"Audio file sent to test assets: {result.name}")
            else:
                QMessageBox.warning(self, "Warning", "Failed to copy audio file to test assets.")
                
        except Exception as e:
            logger.error(f"Error sending to test assets: {e}")
            QMessageBox.critical(self, "Error", f"Failed to send to test assets: {e}")
    
    def closeEvent(self, event) -> None:
        """Handle window close event.

        Integration: source/interfaces/intake/main.py#open_dictation_library
        """
        if self.player:
            self.player.stop()
        if self.conn:
            self.conn.close()
        event.accept()


def main() -> None:
    """Launch the dictation library application.

    Spec: docs/requirements/dictation_requirements.md#ui-workflow
    Tests: tests/test_dictation_library.py#test_window
    """
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("Dictation Library")
    app.setApplicationVersion("1.0")
    
    # Create and show the main window
    window = DictationLibraryWindow()
    window.show()
    
    # Run the application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
