# See architecture: docs/zoros_architecture.md#ui-blueprint
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QDockWidget, QWidget, QVBoxLayout,
    QTableView, QPushButton, QStackedWidget, QTextEdit, QLabel, QHBoxLayout,
    QSplitter, QDateEdit, QCheckBox, QListView, QFormLayout, QMessageBox
)
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QUrl, Signal
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtGui import QPalette, QColor, QFont
import sys
import os
import datetime
from pathlib import Path

# Import DictationManager from the whisper utils module
sys.path.append(
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "modules",
        "whisper",
        "src",
    )
)
from utils import DictationManager

import re
from jiwer import wer

def calculate_transcript_score(reference, hypothesis):
    """
    Calculate the Word Error Rate between two transcripts
    
    Args:
        reference (str): The reference transcript (corrected by human)
        hypothesis (str): The hypothesis transcript (from the system)
        
    Returns:
        float: Word Error Rate score (lower is better)
    """
    if not reference or not hypothesis:
        return None
    
    # Clean and normalize strings
    reference = re.sub(r'\s+', ' ', reference.strip().lower())
    hypothesis = re.sub(r'\s+', ' ', hypothesis.strip().lower())
    
    # Calculate WER
    try:
        error_rate = wer(reference, hypothesis)
        return error_rate
    except Exception as e:
        print(f"Error calculating WER: {str(e)}")
        return None

# --- Data stubs ---
class Dictation:
    """
    A wrapper class for dictation data to make it compatible with the UI model
    """
    def __init__(self, dictation_data):
        """
        Initialize from the dictation JSON data
        
        Args:
            dictation_data (dict): Raw dictation data from DictationManager
        """
        self.data = dictation_data
        self.id = dictation_data.get("dictation_id", "")
        self.date = self._format_date(dictation_data.get("created_at", ""))
        
        # Check if corrected_transcript exists but status is still Draft
        # This handles manually edited JSON files
        if dictation_data.get("corrected_transcript") and dictation_data.get("status") == "Draft":
            self.status = "Processed"  # Update status for display
            # Also update the underlying data
            dictation_data["status"] = "Processed"
            # Save the updated status to disk
            DictationManager.update_dictation(self.id, status="Processed")
        else:
            self.status = dictation_data.get("status", "Draft")
            
        self.accuracy = dictation_data.get("accuracy", {})
        self.wer_qf = self.accuracy.get("quick_to_full_wer", 0.0)
        self.wer_fc = self.accuracy.get("full_to_corrected_wer", 0.0)
        self.audio_path = dictation_data.get("audio_path", "")
        self.quick_transcript = dictation_data.get("quick_transcript", "")
        self.full_transcript = dictation_data.get("full_transcript", "")
        self.corrected_transcript = dictation_data.get("corrected_transcript", "")
    
    def _format_date(self, iso_date):
        """Format ISO date string to a more readable format"""
        if not iso_date:
            return ""
        try:
            dt = datetime.datetime.fromisoformat(iso_date)
            return dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return iso_date
    
    def save_correction(self, corrected_text):
        """
        Save the corrected transcript and update WER metrics
        
        Args:
            corrected_text (str): The corrected transcript text
        """
        # Update the corrected transcript
        self.corrected_transcript = corrected_text
        
        # Calculate WER between full and corrected transcripts
        # In a real implementation, we'd calculate WER here
        # For now, placeholder values
        if self.full_transcript and corrected_text:
            self.wer_fc = calculate_transcript_score(self.full_transcript, corrected_text)
        
        # Update status if needed
        if self.status == "Draft" and corrected_text:
            self.status = "Processed"
            
        # Update the underlying dictation data
        self.data["corrected_transcript"] = corrected_text
        self.data["status"] = self.status
        self.data["accuracy"]["full_to_corrected_wer"] = self.wer_fc
        
        # Save to disk using DictationManager
        DictationManager.update_dictation(
            self.id,
            corrected_transcript=corrected_text,
            status=self.status,
            accuracy=self.data["accuracy"]
        )

# Sample model for QTableView
class DictationTableModel(QAbstractTableModel):
    # Define a custom signal to request opening a dictation
    
    headers = ['ID', 'Date', 'Status', 'WER Q→F', 'WER F→C']
    def __init__(self, dictations=None):
        super().__init__()
        self._data = dictations or []
        self._all_data = []  # Store all dictations for filtering

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            d = self._data[index.row()]
            col = index.column()
            if col == 0:
                # Show shorter ID for readability
                return d.id[:8] + "..."
            elif col == 1:
                return d.date
            elif col == 2:
                return d.status
            elif col == 3:
                return f"{d.wer_qf:.3f}" if d.wer_qf else "-"
            elif col == 4:
                return f"{d.wer_fc:.3f}" if d.wer_fc else "-"
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.headers[section]
        return None
        
    def getDictation(self, row):
        """Get the dictation object at the specified row"""
        if 0 <= row < len(self._data):
            return self._data[row]
        return None
        
    def refresh(self):
        """Reload dictations from the storage"""
        self.beginResetModel()
        self._all_data = self.loadDictations()
        self._data = self._all_data.copy()  # Start with unfiltered data
        self.endResetModel()
        
    def filter_dictations(self, drafts_only=False, from_date=None, to_date=None):
        """
        Filter dictations based on criteria
        
        Args:
            drafts_only (bool): Show only dictations with Draft status
            from_date (datetime.date): Show dictations created on or after this date
            to_date (datetime.date): Show dictations created on or before this date
        """
        self.beginResetModel()
        
        # Start with all dictations
        filtered_data = self._all_data.copy()
        
        # Apply status filter
        if drafts_only:
            filtered_data = [d for d in filtered_data if d.status == "Draft"]
            
        # Apply date filters if provided
        if from_date or to_date:
            date_filtered = []
            for d in filtered_data:
                try:
                    # Parse the dictation date (assumes format "YYYY-MM-DD HH:MM")
                    parts = d.date.split()
                    if len(parts) > 0:
                        date_str = parts[0]
                        year, month, day = map(int, date_str.split('-'))
                        dictation_date = datetime.date(year, month, day)
                        
                        # Check if date is within range
                        if from_date and dictation_date < from_date:
                            continue
                        if to_date and dictation_date > to_date:
                            continue
                        date_filtered.append(d)
                except (ValueError, IndexError):
                    # If date parsing fails, include the dictation anyway
                    date_filtered.append(d)
            filtered_data = date_filtered
            
        # Update displayed data
        self._data = filtered_data
        self.endResetModel()
        
    @staticmethod
    def loadDictations():
        """
        Load dictations from the DictationManager
        
        Returns:
            list: List of Dictation objects
        """
        dictations_data = DictationManager.list_dictations()
        return [Dictation(d) for d in dictations_data]

# --- UI Components ---
class DictationListPage(QWidget):
    open_dictation_requested = Signal(object)
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        # Create table and load real dictation data
        self.table = QTableView()
        self.model = DictationTableModel()
        self.model._data = self.model.loadDictations()  # Load initial data
        self.table.setModel(self.model)
        
        # Configure table appearance
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.resizeColumnsToContents()
        
        layout.addWidget(self.table)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.open_button = QPushButton('Open Selected')
        self.delete_button = QPushButton('Delete Selected')
        self.score_button = QPushButton('Score Transcript')
        self.refresh_button = QPushButton('Refresh List')
        
        button_layout.addWidget(self.open_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.score_button)
        button_layout.addWidget(self.refresh_button)
        layout.addLayout(button_layout)
        
        # Connect signals
        self.refresh_button.clicked.connect(self.refresh_dictations)
        self.delete_button.clicked.connect(self.delete_selected_dictation)
        self.score_button.clicked.connect(self.score_all_unscored_dictations)
        
        # Connect double-click to open dictation
        self.table.doubleClicked.connect(self.on_double_click)
        
    def refresh_dictations(self):
        """Refresh the dictation list from storage"""
        self.model.refresh()
        self.table.resizeColumnsToContents()
        
    def get_selected_dictation(self):
        """Get the currently selected dictation or None"""
        indexes = self.table.selectedIndexes()
        if indexes:
            row = indexes[0].row()
            return self.model.getDictation(row)
        return None
        
    def delete_selected_dictation(self):
        """Delete the currently selected dictation"""
        dictation = self.get_selected_dictation()
        if not dictation:
            QMessageBox.warning(self, "No Selection", "Please select a dictation to delete.")
            return
            
        # Confirm deletion
        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete this dictation?\n\nID: {dictation.id}\nDate: {dictation.date}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            # Delete the dictation
            success = DictationManager.delete_dictation(dictation.id)
            if success:
                self.refresh_dictations()
                QMessageBox.information(self, "Delete Successful", "The dictation has been deleted.")
            else:
                QMessageBox.critical(self, "Delete Failed", "Failed to delete the dictation. See console for details.")
    
    def on_double_click(self, index):
        """Handle double-click on a table row by opening the dictation"""
        # Just emit a signal that will be connected to the show_correction method
        dictation = self.get_selected_dictation()
        if dictation:
            self.open_dictation_requested.emit(dictation)
    
    def score_all_unscored_dictations(self):
        """Calculate and save scores for all unscored dictations that are processed (have a corrected transcript)"""
        count = 0
        for dictation in self.model._all_data:
            # Only process dictations that are processed, i.e., have a corrected transcript
            if not dictation.corrected_transcript:
                continue

            # Skip already scored dictations (assuming non-None scores indicate scoring has been done)
            if (dictation.wer_qf is not None and dictation.wer_fc is not None and 
                (dictation.wer_qf != 0.0 or dictation.wer_fc != 0.0)):
                continue

            # Calculate WER scores
            wer_qf = None
            wer_fc = None

            if dictation.quick_transcript:
                wer_qf = calculate_transcript_score(dictation.corrected_transcript, dictation.quick_transcript)

            if dictation.full_transcript:
                wer_fc = calculate_transcript_score(dictation.corrected_transcript, dictation.full_transcript)

            # Update the dictation with new scores
            accuracy = {
                "quick_to_full_wer": wer_qf,
                "full_to_corrected_wer": wer_fc
            }

            dictation.wer_qf = wer_qf
            dictation.wer_fc = wer_fc
            dictation.accuracy = accuracy
            dictation.data["accuracy"] = accuracy

            # Save to disk
            DictationManager.update_dictation(dictation.id, accuracy=accuracy)

            count += 1

        if count == 0:
            QMessageBox.information(
                self, 
                "No Unscored Dictations", 
                "All dictations are already scored or lack the necessary transcripts."
            )
        else:
            self.refresh_dictations()
            QMessageBox.information(self, "Scoring Complete", f"Scored {count} dictation(s).")
        
    def show_score_results(self, dictation, wer_qf, wer_fc, wer_qc, comparisons_made):
        """Display the scoring results in a dialog"""
        message = f"Scoring Results for Dictation: {dictation.id[:8]}...\n\n"
        
        if "quick_to_full" in comparisons_made and wer_qf is not None:
            message += f"Quick → Full Transcript WER: {wer_qf:.3f}\n"
            message += f"Quick → Full Accuracy: {(1-wer_qf)*100:.1f}%\n\n"
        
        if "full_to_corrected" in comparisons_made and wer_fc is not None:
            message += f"Full → Corrected Transcript WER: {wer_fc:.3f}\n"
            message += f"Full → Corrected Accuracy: {(1-wer_fc)*100:.1f}%\n\n"
            
        if "quick_to_corrected" in comparisons_made and wer_qc is not None:
            message += f"Quick → Corrected Transcript WER: {wer_qc:.3f}\n"
            message += f"Quick → Corrected Accuracy: {(1-wer_qc)*100:.1f}%\n"
            message += "(Used because full transcript was not available)\n\n"
            
        if not comparisons_made:
            message += "No transcript comparisons could be made with the available data.\n\n"
            
        message += "Lower WER scores indicate better transcript quality."
        
        QMessageBox.information(self, "Transcript Scoring Results", message)

    def score_selected_dictation(self):
        """Calculate and save scores for the selected dictation"""
        dictation = self.get_selected_dictation()
        if not dictation:
            QMessageBox.warning(self, "No Selection", "Please select a dictation to score.")
            return
        
        # Track which comparisons we're actually performing
        comparisons_made = []
        wer_qf = None
        wer_fc = None
        wer_qc = None  # Direct quick to corrected comparison
        
        # Check which transcripts are available
        has_quick = bool(dictation.quick_transcript and dictation.quick_transcript.strip())
        has_full = bool(dictation.full_transcript and dictation.full_transcript.strip()) 
        has_corrected = bool(dictation.corrected_transcript and dictation.corrected_transcript.strip())
        
        # Check if we can score anything
        if not has_corrected:
            QMessageBox.warning(
                self, 
                "Missing Corrected Transcript", 
                "This dictation cannot be scored because it doesn't have a corrected transcript."
            )
            return
            
        # Calculate WER scores for available transcript pairs
        
        # Quick to Full transcript score (if both exist)
        if has_quick and has_full:
            wer_qf = calculate_transcript_score(dictation.full_transcript, dictation.quick_transcript)
            comparisons_made.append("quick_to_full")
        
        # Full to Corrected transcript score (if both exist)  
        if has_full and has_corrected:
            wer_fc = calculate_transcript_score(dictation.corrected_transcript, dictation.full_transcript)
            comparisons_made.append("full_to_corrected")
            
        # Direct Quick to Corrected score (if full doesn't exist)
        if has_quick and has_corrected and not has_full:
            wer_qc = calculate_transcript_score(dictation.corrected_transcript, dictation.quick_transcript)
            comparisons_made.append("quick_to_corrected")
            
            # For backward compatibility, also store this in wer_fc if that's missing
            if wer_fc is None:
                wer_fc = wer_qc
        
        # Update the dictation with new scores
        accuracy = dictation.data.get("accuracy", {})
        
        # Only update scores that we've calculated
        if wer_qf is not None:
            accuracy["quick_to_full_wer"] = wer_qf
            dictation.wer_qf = wer_qf
            
        if wer_fc is not None:
            accuracy["full_to_corrected_wer"] = wer_fc  
            dictation.wer_fc = wer_fc
            
        if wer_qc is not None:
            accuracy["quick_to_corrected_wer"] = wer_qc
        
        # Update both the UI model and save to disk
        dictation.accuracy = accuracy
        dictation.data["accuracy"] = accuracy
        
        # Save to disk
        DictationManager.update_dictation(dictation.id, accuracy=accuracy)
        
        # Show results
        self.show_score_results(dictation, wer_qf, wer_fc, wer_qc, comparisons_made)
        
        # Refresh the table to show updated scores
        self.refresh_dictations()

# --- UI Components ---
class CorrectionPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        
        # Dictation info header
        self.info_label = QLabel()
        main_layout.addWidget(self.info_label)
        
        # Audio player
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        
        controls = QHBoxLayout()
        self.play_btn = QPushButton('Play')
        self.play_btn.clicked.connect(self.toggle_play)
        controls.addWidget(self.play_btn)
        main_layout.addLayout(controls)
        
        # Transcript editors with labels
        editor_layout = QHBoxLayout()
        
        # Original transcript section
        original_layout = QVBoxLayout()
        original_layout.addWidget(QLabel("Original Transcript:"))
        self.original = QTextEdit()
        self.original.setReadOnly(True)
        original_layout.addWidget(self.original)
        
        # Corrected transcript section
        corrected_layout = QVBoxLayout()
        corrected_layout.addWidget(QLabel("Corrected Transcript:"))
        self.corrected = QTextEdit()
        corrected_layout.addWidget(self.corrected)
        
        # Add both sections to the editor layout
        editor_layout.addLayout(original_layout)
        editor_layout.addLayout(corrected_layout)
        main_layout.addLayout(editor_layout)
        
        # Save/Next buttons
        bottom = QHBoxLayout()
        self.save_btn = QPushButton('Save Correction')
        self.save_btn.clicked.connect(self.save_and_return)
        self.delete_btn = QPushButton('Delete Dictation')
        self.delete_btn.clicked.connect(self.delete_current_dictation)
        self.back_btn = QPushButton('Back to List')
        
        bottom.addWidget(self.save_btn)
        bottom.addWidget(self.delete_btn)
        bottom.addWidget(self.back_btn)
        main_layout.addLayout(bottom)
        
        # Current dictation reference
        self.current_dictation = None

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.play_btn.setText('Play')
        else:
            self.player.play()
            self.play_btn.setText('Pause')
    
    def load_dictation(self, dictation):
        """
        Load a dictation for correction
        
        Args:
            dictation: The Dictation object to load
        """
        self.current_dictation = dictation
        
        # Update information label
        self.info_label.setText(f"Dictation ID: {dictation.id} | Date: {dictation.date} | Status: {dictation.status}")
        
        # Load audio if available
        if dictation.audio_path and os.path.exists(dictation.audio_path):
            self.player.setSource(QUrl.fromLocalFile(dictation.audio_path))
            self.play_btn.setEnabled(True)
        else:
            self.play_btn.setEnabled(False)
        
        # Load transcripts
        # Prefer full transcript if available, otherwise use quick transcript
        transcript_text = dictation.full_transcript or dictation.quick_transcript
        self.original.setText(transcript_text)
        
        # Load existing corrected transcript if available
        if dictation.corrected_transcript:
            self.corrected.setText(dictation.corrected_transcript)
        else:
            # Start with a copy of the original for easier editing
            self.corrected.setText(transcript_text)
    
    def save_and_return(self):
        """Save the correction and return to the list view"""
        # Save the correction
        self.save_correction(show_message=False)
        
        # Emit signal to return to list
        self.correction_saved.emit()
        
    def save_correction(self, show_message=False):
        """
        Save the current correction to the dictation
        
        Args:
            show_message (bool): Whether to show a confirmation message
        """
        if not self.current_dictation:
            return
            
        corrected_text = self.corrected.toPlainText()
        self.current_dictation.save_correction(corrected_text)
        
        # Show confirmation message only if explicitly requested
        if show_message:
            QMessageBox.information(self, "Saved", "Correction saved successfully.")
            
    def delete_current_dictation(self):
        """Delete the currently loaded dictation"""
        if not self.current_dictation:
            return
            
        # Confirm deletion
        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete this dictation?\n\nID: {self.current_dictation.id}\nDate: {self.current_dictation.date}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            # Release audio resources before deletion
            self.release_resources()
            
            # Delete the dictation
            success = DictationManager.delete_dictation(self.current_dictation.id)
            if success:
                # Signal that we need to go back to the list
                self.dictation_deleted.emit()
            else:
                QMessageBox.critical(self, "Delete Failed", "Failed to delete the dictation. See console for details.")
    
    def release_resources(self):
        """Release all resources that might be using dictation files"""
        # Stop and clear the media player to release audio file
        self.player.stop()
        self.player.setSource(QUrl())
    
    def clear(self):
        """Clear the current dictation data"""
        self.current_dictation = None
        self.info_label.setText("")
        self.original.setText("")
        self.corrected.setText("")
        self.release_resources()
        self.play_btn.setText("Play")
        self.play_btn.setEnabled(False)
        
    # Define custom signals
    from PySide6.QtCore import Signal
    dictation_deleted = Signal()
    correction_saved = Signal()  # New signal for when a correction is saved

class DashboardPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Dashboard coming soon...'))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('ZorOS Transcription Correction')
        self.setMinimumSize(800, 600)
        
        # Sidebar
        dock = QDockWidget('Filters', self)
        filter_widget = QWidget()
        form = QFormLayout(filter_widget)
        self.draft_checkbox = QCheckBox('Show Drafts Only')
        form.addRow('Status:', self.draft_checkbox)
        
        # Date filters
        self.from_date = QDateEdit()
        self.to_date = QDateEdit()
        self.from_date.setDate(datetime.date.today() - datetime.timedelta(days=30))
        self.to_date.setDate(datetime.date.today())
        self.from_date.setCalendarPopup(True)
        self.to_date.setCalendarPopup(True)
        form.addRow('From:', self.from_date)
        form.addRow('To:', self.to_date)
        
        # Apply filters button
        self.apply_filters_btn = QPushButton('Apply Filters')
        self.apply_filters_btn.clicked.connect(self.apply_filters)  # Connect to apply_filters method
        form.addRow(self.apply_filters_btn)
        
        dock.setWidget(filter_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        
        # Central stack
        self.stack = QStackedWidget()
        self.list_page = DictationListPage()
        self.correction_page = CorrectionPage()
        self.dashboard_page = DashboardPage()
        self.stack.addWidget(self.list_page)
        self.stack.addWidget(self.correction_page)
        self.stack.addWidget(self.dashboard_page)
        self.setCentralWidget(self.stack)
        
        # Menu bar
        menubar = self.menuBar()
        file_menu = menubar.addMenu('File')
        view_menu = menubar.addMenu('View')
        
        # Add actions
        refresh_action = file_menu.addAction('Refresh List')
        refresh_action.triggered.connect(self.list_page.refresh_dictations)
        
        dashboard_action = view_menu.addAction('Dashboard')
        dashboard_action.triggered.connect(lambda: self.stack.setCurrentWidget(self.dashboard_page))
        
        list_action = view_menu.addAction('Dictation List')
        list_action.triggered.connect(lambda: self.stack.setCurrentWidget(self.list_page))
        
        # Connect signals
        self.list_page.open_button.clicked.connect(self.show_correction)
        self.list_page.open_dictation_requested.connect(self.show_correction)  # Connect double-click signal
        self.correction_page.back_btn.clicked.connect(self.back_to_list)
        self.correction_page.dictation_deleted.connect(self.on_dictation_deleted)  # Connect deletion signal
        self.correction_page.correction_saved.connect(self.on_correction_saved)  # Connect save signal
        
        # Load initial data
        self.list_page.refresh_dictations()
        
    def on_correction_saved(self):
        """Handle when a dictation is saved from the correction page"""
        # Show confirmation
        self.statusBar().showMessage("Correction saved successfully", 3000)
        
        # Go back to the list page and refresh
        self.list_page.refresh_dictations()
        self.apply_filters()  # Reapply any active filters
        self.stack.setCurrentWidget(self.list_page)
        
    def on_dictation_deleted(self):
        """Handle when a dictation is deleted from the correction page"""
        # Show confirmation
        self.statusBar().showMessage("Dictation deleted successfully", 3000)
        
        # Go back to the list page and refresh
        self.list_page.refresh_dictations()
        self.apply_filters()  # Reapply any active filters
        self.stack.setCurrentWidget(self.list_page)

    def apply_filters(self):
        """Apply the current filter settings to the dictation list"""
        # Get filter values
        drafts_only = self.draft_checkbox.isChecked()
        from_date = self.from_date.date().toPyDate() if self.from_date.date().isValid() else None
        to_date = self.to_date.date().toPyDate() if self.to_date.date().isValid() else None
        
        # Apply filters
        self.list_page.model.filter_dictations(
            drafts_only=drafts_only,
            from_date=from_date,
            to_date=to_date
        )
        
        # Resize columns to fit content
        self.list_page.table.resizeColumnsToContents()
        
        # Show filter status in status bar
        filter_status = []
        if drafts_only:
            filter_status.append("Drafts only")
        if from_date:
            filter_status.append(f"From {from_date.strftime('%Y-%m-%d')}")
        if to_date:
            filter_status.append(f"To {to_date.strftime('%Y-%m-%d')}")
            
        status_msg = "Filters applied: " + ", ".join(filter_status) if filter_status else "No filters applied"
        self.statusBar().showMessage(status_msg, 3000)  # Show for 3 seconds

    def show_correction(self, dictation=None):
        """Switch to correction page and load selected dictation"""
        if dictation is None:
            dictation = self.list_page.get_selected_dictation()
        
        if dictation:
            self.correction_page.load_dictation(dictation)
            self.stack.setCurrentWidget(self.correction_page)
        else:
            QMessageBox.warning(self, "No Selection", "Please select a dictation to correct.")
            
    def back_to_list(self):
        """Go back to list page and refresh the list"""
        self.list_page.refresh_dictations()
        # Re-apply any filters that were active
        self.apply_filters()
        self.stack.setCurrentWidget(self.list_page)

def set_dark_theme(app):
    """Apply dark theme styling to the application"""
    # Create dark palette
    dark_palette = QPalette()
    
    # Set colors
    dark_color = QColor(45, 45, 45)
    disabled_color = QColor(70, 70, 70)
    text_color = QColor(225, 225, 225)
    highlight_color = QColor(42, 130, 218)
    disabled_text_color = QColor(120, 120, 120)
    
    # Base colors
    dark_palette.setColor(QPalette.ColorRole.Window, dark_color)
    dark_palette.setColor(QPalette.ColorRole.WindowText, text_color)
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, dark_color)
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, dark_color)
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, text_color)
    dark_palette.setColor(QPalette.ColorRole.Text, text_color)
    dark_palette.setColor(QPalette.ColorRole.Button, dark_color)
    dark_palette.setColor(QPalette.ColorRole.ButtonText, text_color)
    dark_palette.setColor(QPalette.ColorRole.Link, highlight_color)
    
    # Highlight colors
    dark_palette.setColor(QPalette.ColorRole.Highlight, highlight_color)
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    
    # Disabled colors
    dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_text_color)
    dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_text_color)
    dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled_text_color)
    dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button, disabled_color)
    dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Window, disabled_color)
    
    # Apply palette to application
    app.setPalette(dark_palette)
    
    # Additional stylesheet for fine control
    app.setStyleSheet("""
        QTableView {
            background-color: #262626;
            border: 1px solid #555;
            gridline-color: #505050;
            color: #e1e1e1;
        }
        QTableView::item:selected {
            background-color: #2a82da;
            color: white;
        }
        QHeaderView::section {
            background-color: #363636;
            color: #e1e1e1;
            padding: 4px;
            border: 1px solid #505050;
        }
        QTextEdit {
            background-color: #262626;
            border: 1px solid #555;
            color: #e1e1e1;
        }
        QLabel {
            color: #e1e1e1;
        }
        QPushButton {
            background-color: #383838;
            border: 1px solid #555;
            border-radius: 3px;
            padding: 5px 10px;
            color: #e1e1e1;
        }
        QPushButton:hover {
            background-color: #464646;
        }
        QPushButton:pressed {
            background-color: #2a82da;
        }
        QPushButton:disabled {
            background-color: #595959;
            color: #7a7a7a;
        }
        QDockWidget {
            color: #e1e1e1;
            titlebar-close-icon: url(close.png);
            titlebar-normal-icon: url(undock.png);
        }
        QDockWidget::title {
            background-color: #363636;
            padding-left: 5px;
        }
        QCheckBox {
            color: #e1e1e1;
        }
        QCheckBox::indicator {
            border: 1px solid #5f5f5f;
            background: #262626;
        }
        QCheckBox::indicator:checked {
            background-color: #2a82da;
        }
        QDateEdit {
            background-color: #262626;
            border: 1px solid #555;
            border-radius: 3px;
            padding: 2px;
            color: #e1e1e1;
        }
        QMenu {
            background-color: #2d2d2d;
            color: #e1e1e1;
            border: 1px solid #555;
        }
        QMenu::item:selected {
            background-color: #2a82da;
        }
        QMenuBar {
            background-color: #2d2d2d;
            color: #e1e1e1;
        }
        QMenuBar::item:selected {
            background-color: #363636;
        }
    """)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # Initialize the DictationManager
    DictationManager.initialize()
    
    # Apply dark theme
    set_dark_theme(app)
    
    # Create and show the main window
    win = MainWindow()
    win.show()
    
    sys.exit(app.exec())
