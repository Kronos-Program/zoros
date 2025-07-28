"""
Standalone Dictation Backend Tester

This module provides a standalone interface for testing different dictation
backends without interfering with the main ZorOS intake application. It runs
in a separate process to avoid memory conflicts and allows users to choose
their own backend for testing.

Spec: docs/requirements/dictation_requirements.md#backend-testing
Tests: tests/test_dictation_tester.py
Integration: source/interfaces/window_manager.py

Features:
- Standalone backend testing
- Process isolation for memory management
- Multiple backend support
- Performance benchmarking
- Audio file testing
"""

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QTextEdit, QProgressBar,
    QFileDialog, QMessageBox, QGroupBox, QFormLayout, QSpinBox,
    QDoubleSpinBox, QCheckBox, QTabWidget
)

# Add source to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from source.dictation_backends import get_available_backends
from source.dictation_backends import (
    MLXWhisperBackend, ParallelMLXWhisperBackend, 
    QueueBasedStreamingBackend, RealtimeStreamingBackend
)
from scripts.audio_file_manager import AudioFileManager

logger = logging.getLogger(__name__)


class TranscriptionWorker(QThread):
    """Worker thread for transcription to avoid blocking the UI."""
    
    progress_updated = Signal(str)
    transcription_complete = Signal(str, float, str)  # text, duration, error
    progress_percentage = Signal(int)
    
    def __init__(self, backend_name: str, model: str, audio_file: str):
        super().__init__()
        self.backend_name = backend_name
        self.model = model
        self.audio_file = audio_file
        
    def run(self):
        """Run transcription in background thread."""
        try:
            self.progress_updated.emit(f"Initializing {self.backend_name} backend...")
            self.progress_percentage.emit(10)
            
            # Initialize backend
            if self.backend_name == "MLXWhisper":
                backend = MLXWhisperBackend(self.model)
            elif self.backend_name == "ParallelMLXWhisper":
                backend = ParallelMLXWhisperBackend(self.model)
            elif self.backend_name == "QueueBasedStreamingMLXWhisper":
                backend = QueueBasedStreamingBackend(self.model)
            elif self.backend_name == "RealtimeStreamingMLXWhisper":
                backend = RealtimeStreamingBackend(self.model)
            else:
                raise ValueError(f"Unknown backend: {self.backend_name}")
            
            self.progress_updated.emit("Backend initialized, starting transcription...")
            self.progress_percentage.emit(30)
            
            # Transcribe
            start_time = time.time()
            result = backend.transcribe(self.audio_file)
            duration = time.time() - start_time
            
            self.progress_updated.emit("Transcription completed!")
            self.progress_percentage.emit(100)
            
            self.transcription_complete.emit(result, duration, "")
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Transcription failed: {error_msg}")
            self.progress_updated.emit(f"Error: {error_msg}")
            self.transcription_complete.emit("", 0.0, error_msg)


class DictationTesterWindow(QMainWindow):
    """Standalone dictation backend tester window."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ZorOS Dictation Backend Tester")
        self.setMinimumSize(800, 600)
        
        self.audio_manager = AudioFileManager()
        self.worker: Optional[TranscriptionWorker] = None
        
        self._build_ui()
        self._load_available_backends()
    
    def _build_ui(self):
        """Build the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create tabs
        tabs = QTabWidget()
        
        # Main testing tab
        testing_tab = self._create_testing_tab()
        tabs.addTab(testing_tab, "Backend Testing")
        
        # Benchmarking tab
        benchmark_tab = self._create_benchmark_tab()
        tabs.addTab(benchmark_tab, "Performance Benchmark")
        
        # Audio management tab
        audio_tab = self._create_audio_tab()
        tabs.addTab(audio_tab, "Audio Management")
        
        layout.addWidget(tabs)
        
        # Status bar
        self.status_bar = self.statusBar()
    
    def _create_testing_tab(self) -> QWidget:
        """Create the main testing tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Backend selection
        backend_group = QGroupBox("Backend Configuration")
        backend_layout = QFormLayout(backend_group)
        
        self.backend_combo = QComboBox()
        backend_layout.addRow("Backend:", self.backend_combo)
        
        self.model_combo = QComboBox()
        self.model_combo.addItems(["tiny", "small", "medium", "large", "large-v3-turbo"])
        self.model_combo.setCurrentText("small")
        backend_layout.addRow("Model:", self.model_combo)
        
        layout.addWidget(backend_group)
        
        # Audio file selection
        audio_group = QGroupBox("Audio File")
        audio_layout = QHBoxLayout(audio_group)
        
        self.audio_path_label = QLabel("No file selected")
        audio_layout.addWidget(self.audio_path_label)
        
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.browse_audio_file)
        audio_layout.addWidget(self.browse_btn)
        
        layout.addWidget(audio_group)
        
        # Progress
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_label = QLabel("Ready")
        progress_layout.addWidget(self.progress_label)
        
        layout.addWidget(progress_group)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.test_btn = QPushButton("🧪 Test Backend")
        self.test_btn.clicked.connect(self.test_backend)
        button_layout.addWidget(self.test_btn)
        
        self.stop_btn = QPushButton("⏹️ Stop")
        self.stop_btn.clicked.connect(self.stop_test)
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.stop_btn)
        
        layout.addLayout(button_layout)
        
        # Results
        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout(results_group)
        
        self.results_text = QTextEdit()
        self.results_text.setPlaceholderText("Transcription results will appear here...")
        results_layout.addWidget(self.results_text)
        
        layout.addWidget(results_group)
        
        return tab
    
    def _create_benchmark_tab(self) -> QWidget:
        """Create the benchmarking tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Benchmark configuration
        config_group = QGroupBox("Benchmark Configuration")
        config_layout = QFormLayout(config_group)
        
        self.benchmark_backend_combo = QComboBox()
        config_layout.addRow("Backend:", self.benchmark_backend_combo)
        
        self.benchmark_model_combo = QComboBox()
        self.benchmark_model_combo.addItems(["tiny", "small", "medium", "large"])
        self.benchmark_model_combo.setCurrentText("small")
        config_layout.addRow("Model:", self.benchmark_model_combo)
        
        self.iterations_spin = QSpinBox()
        self.iterations_spin.setRange(1, 10)
        self.iterations_spin.setValue(3)
        config_layout.addRow("Iterations:", self.iterations_spin)
        
        layout.addWidget(config_group)
        
        # Benchmark controls
        benchmark_layout = QHBoxLayout()
        
        self.benchmark_btn = QPushButton("📊 Run Benchmark")
        self.benchmark_btn.clicked.connect(self.run_benchmark)
        benchmark_layout.addWidget(self.benchmark_btn)
        
        layout.addLayout(benchmark_layout)
        
        # Benchmark results
        benchmark_results_group = QGroupBox("Benchmark Results")
        benchmark_results_layout = QVBoxLayout(benchmark_results_group)
        
        self.benchmark_results_text = QTextEdit()
        self.benchmark_results_text.setPlaceholderText("Benchmark results will appear here...")
        benchmark_results_layout.addWidget(self.benchmark_results_text)
        
        layout.addWidget(benchmark_results_group)
        
        return tab
    
    def _create_audio_tab(self) -> QWidget:
        """Create the audio management tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Audio file management
        audio_group = QGroupBox("Audio File Management")
        audio_layout = QVBoxLayout(audio_group)
        
        # Generate test audio
        generate_layout = QHBoxLayout()
        generate_layout.addWidget(QLabel("Generate test audio:"))
        
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(5, 120)
        self.duration_spin.setValue(30)
        generate_layout.addWidget(self.duration_spin)
        
        generate_layout.addWidget(QLabel("seconds"))
        
        self.generate_btn = QPushButton("🎵 Generate")
        self.generate_btn.clicked.connect(self.generate_test_audio)
        generate_layout.addWidget(self.generate_btn)
        
        audio_layout.addLayout(generate_layout)
        
        # List available files
        self.list_files_btn = QPushButton("📁 List Available Files")
        self.list_files_btn.clicked.connect(self.list_available_files)
        audio_layout.addWidget(self.list_files_btn)
        
        layout.addWidget(audio_group)
        
        # File list
        files_group = QGroupBox("Available Audio Files")
        files_layout = QVBoxLayout(files_group)
        
        self.files_text = QTextEdit()
        self.files_text.setPlaceholderText("Available audio files will appear here...")
        files_layout.addWidget(self.files_text)
        
        layout.addWidget(files_group)
        
        return tab
    
    def _load_available_backends(self):
        """Load available backends into combo boxes."""
        backends = get_available_backends()
        
        for combo in [self.backend_combo, self.benchmark_backend_combo]:
            combo.clear()
            combo.addItems(backends)
    
    def browse_audio_file(self):
        """Browse for an audio file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Audio File", "", 
            "Audio Files (*.wav *.mp3 *.m4a *.flac);;All Files (*)"
        )
        
        if file_path:
            self.audio_path_label.setText(Path(file_path).name)
            self.current_audio_file = file_path
    
    def test_backend(self):
        """Test the selected backend."""
        if not hasattr(self, 'current_audio_file'):
            QMessageBox.warning(self, "No Audio File", "Please select an audio file first.")
            return
        
        backend = self.backend_combo.currentText()
        model = self.model_combo.currentText()
        
        # Update UI
        self.test_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Starting...")
        self.results_text.clear()
        
        # Start worker
        self.worker = TranscriptionWorker(backend, model, self.current_audio_file)
        self.worker.progress_updated.connect(self.progress_label.setText)
        self.worker.progress_percentage.connect(self.progress_bar.setValue)
        self.worker.transcription_complete.connect(self.on_transcription_complete)
        self.worker.start()
    
    def stop_test(self):
        """Stop the current test."""
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
        
        self.test_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_label.setText("Stopped")
    
    def on_transcription_complete(self, text: str, duration: float, error: str):
        """Handle transcription completion."""
        self.test_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
        if error:
            self.results_text.setText(f"Error: {error}")
            self.status_bar.showMessage(f"Test failed: {error}")
        else:
            result_text = f"Transcription completed in {duration:.2f} seconds\n\n"
            result_text += f"Result:\n{text}"
            self.results_text.setText(result_text)
            self.status_bar.showMessage(f"Test completed in {duration:.2f}s")
    
    def run_benchmark(self):
        """Run performance benchmark."""
        backend = self.benchmark_backend_combo.currentText()
        model = self.benchmark_model_combo.currentText()
        iterations = self.iterations_spin.value()
        
        if not hasattr(self, 'current_audio_file'):
            QMessageBox.warning(self, "No Audio File", "Please select an audio file first.")
            return
        
        self.benchmark_results_text.clear()
        self.benchmark_results_text.append(f"Running benchmark for {backend} ({model})...")
        self.benchmark_results_text.append(f"Iterations: {iterations}")
        self.benchmark_results_text.append("=" * 50)
        
        times = []
        for i in range(iterations):
            self.benchmark_results_text.append(f"Iteration {i+1}: Starting...")
            QApplication.processEvents()
            
            try:
                start_time = time.time()
                
                if backend == "MLXWhisper":
                    backend_instance = MLXWhisperBackend(model)
                elif backend == "ParallelMLXWhisper":
                    backend_instance = ParallelMLXWhisperBackend(model)
                elif backend == "QueueBasedStreamingMLXWhisper":
                    backend_instance = QueueBasedStreamingBackend(model)
                else:
                    raise ValueError(f"Unknown backend: {backend}")
                
                result = backend_instance.transcribe(self.current_audio_file)
                duration = time.time() - start_time
                times.append(duration)
                
                self.benchmark_results_text.append(f"Iteration {i+1}: {duration:.2f}s")
                
            except Exception as e:
                self.benchmark_results_text.append(f"Iteration {i+1}: Error - {e}")
        
        # Calculate statistics
        if times:
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            
            self.benchmark_results_text.append("=" * 50)
            self.benchmark_results_text.append(f"Results:")
            self.benchmark_results_text.append(f"Average: {avg_time:.2f}s")
            self.benchmark_results_text.append(f"Min: {min_time:.2f}s")
            self.benchmark_results_text.append(f"Max: {max_time:.2f}s")
        
        self.status_bar.showMessage("Benchmark completed")
    
    def generate_test_audio(self):
        """Generate test audio file."""
        duration = self.duration_spin.value()
        
        try:
            file_path = self.audio_manager.generate_test_audio(duration)
            if file_path:
                self.current_audio_file = str(file_path)
                self.audio_path_label.setText(file_path.name)
                self.status_bar.showMessage(f"Generated {duration}s test audio: {file_path.name}")
            else:
                self.status_bar.showMessage("Failed to generate test audio")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to generate test audio: {e}")
    
    def list_available_files(self):
        """List available audio files."""
        try:
            files = self.audio_manager.list_available_files()
            self.files_text.setText(files)
            self.status_bar.showMessage("Listed available files")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to list files: {e}")


def main():
    """Main function for the dictation tester."""
    parser = argparse.ArgumentParser(description="ZorOS Dictation Backend Tester")
    parser.add_argument("--backend", help="Default backend to use")
    parser.add_argument("--model", default="small", help="Default model to use")
    parser.add_argument("--audio-file", help="Default audio file to use")
    
    args = parser.parse_args()
    
    app = QApplication(sys.argv)
    app.setApplicationName("ZorOS Dictation Tester")
    
    window = DictationTesterWindow()
    
    # Set defaults from command line
    if args.backend:
        index = window.backend_combo.findText(args.backend)
        if index >= 0:
            window.backend_combo.setCurrentIndex(index)
    
    if args.model:
        index = window.model_combo.findText(args.model)
        if index >= 0:
            window.model_combo.setCurrentIndex(index)
    
    if args.audio_file:
        window.current_audio_file = args.audio_file
        window.audio_path_label.setText(Path(args.audio_file).name)
    
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main() 