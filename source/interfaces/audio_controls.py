"""
Enhanced Audio Control Widget for ZorOS

This module provides a comprehensive audio playback widget with:
- Play/Pause/Stop controls
- Seek bar with position control
- Skip forward/backward (15 seconds)
- Time display (current/total)
- Volume control

Author: ZorOS Claude Code
Date: 2025-07-05
"""

import sys
from pathlib import Path
from typing import Optional, Callable
import logging

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from PySide6.QtCore import Qt, QTimer, Signal, QUrl, QObject
    from PySide6.QtWidgets import (
        QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QSlider, 
        QLabel, QFrame, QSizePolicy, QApplication
    )
    from PySide6.QtGui import QIcon, QPixmap
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

logger = logging.getLogger(__name__)


class AudioControlWidget(QWidget):
    """Enhanced audio playback controls with seek, skip, and time display."""
    
    # Signals
    positionChanged = Signal(int)
    durationChanged = Signal(int) 
    playbackStateChanged = Signal(int)
    volumeChanged = Signal(float)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Media player setup
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        
        # Connect media player signals
        self.media_player.positionChanged.connect(self._on_position_changed)
        self.media_player.durationChanged.connect(self._on_duration_changed)
        self.media_player.playbackStateChanged.connect(self._on_playback_state_changed)
        
        # Timer for position updates
        self.position_timer = QTimer()
        self.position_timer.timeout.connect(self._update_position)
        self.position_timer.setInterval(100)  # Update every 100ms
        
        # State tracking
        self.duration = 0
        self.current_position = 0
        self.is_seeking = False
        self.audio_file_path = None
        
        # Initialize UI
        self.setup_ui()
        
        # Set initial state
        self.set_enabled(False)
    
    def setup_ui(self):
        """Set up the user interface."""
        self.setFixedHeight(120)
        self.setMinimumWidth(500)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)
        
        # Create sections
        self.create_control_section(main_layout)
        self.create_seek_section(main_layout)
        self.create_time_section(main_layout)
    
    def create_control_section(self, parent_layout):
        """Create the main control buttons section."""
        control_frame = QFrame()
        control_layout = QHBoxLayout(control_frame)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(5)
        
        # Skip backward button
        self.skip_back_btn = QPushButton("⏮ -15s")
        self.skip_back_btn.setFixedSize(70, 35)
        self.skip_back_btn.setToolTip("Skip backward 15 seconds")
        self.skip_back_btn.clicked.connect(lambda: self.skip_seconds(-15))
        
        # Play/Pause button
        self.play_pause_btn = QPushButton("▶")
        self.play_pause_btn.setFixedSize(50, 35)
        self.play_pause_btn.setToolTip("Play/Pause")
        self.play_pause_btn.clicked.connect(self.toggle_playback)
        
        # Stop button
        self.stop_btn = QPushButton("⏹")
        self.stop_btn.setFixedSize(35, 35)
        self.stop_btn.setToolTip("Stop")
        self.stop_btn.clicked.connect(self.stop)
        
        # Skip forward button
        self.skip_forward_btn = QPushButton("+15s ⏭")
        self.skip_forward_btn.setFixedSize(70, 35)
        self.skip_forward_btn.setToolTip("Skip forward 15 seconds")
        self.skip_forward_btn.clicked.connect(lambda: self.skip_seconds(15))
        
        # Volume control
        volume_label = QLabel("🔊")
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.setToolTip("Volume")
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        
        # Add to layout
        control_layout.addWidget(self.skip_back_btn)
        control_layout.addWidget(self.play_pause_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addWidget(self.skip_forward_btn)
        control_layout.addStretch()
        control_layout.addWidget(volume_label)
        control_layout.addWidget(self.volume_slider)
        
        parent_layout.addWidget(control_frame)
    
    def create_seek_section(self, parent_layout):
        """Create the seek bar section."""
        seek_frame = QFrame()
        seek_layout = QHBoxLayout(seek_frame)
        seek_layout.setContentsMargins(0, 0, 0, 0)
        
        # Seek slider
        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 1000)  # Use 1000 for fine granularity
        self.seek_slider.setValue(0)
        self.seek_slider.setToolTip("Seek position")
        
        # Connect seek slider signals
        self.seek_slider.sliderPressed.connect(self._on_seek_start)
        self.seek_slider.sliderReleased.connect(self._on_seek_end)
        self.seek_slider.valueChanged.connect(self._on_seek_changed)
        
        seek_layout.addWidget(self.seek_slider)
        parent_layout.addWidget(seek_frame)
    
    def create_time_section(self, parent_layout):
        """Create the time display section."""
        time_frame = QFrame()
        time_layout = QHBoxLayout(time_frame)
        time_layout.setContentsMargins(0, 0, 0, 0)
        
        # Time labels
        self.current_time_label = QLabel("00:00")
        self.current_time_label.setMinimumWidth(45)
        
        separator_label = QLabel("/")
        
        self.total_time_label = QLabel("00:00")
        self.total_time_label.setMinimumWidth(45)
        
        # File name label
        self.file_name_label = QLabel("No audio file loaded")
        self.file_name_label.setStyleSheet("QLabel { color: #666; font-style: italic; }")
        
        # Add to layout
        time_layout.addWidget(self.current_time_label)
        time_layout.addWidget(separator_label)
        time_layout.addWidget(self.total_time_label)
        time_layout.addStretch()
        time_layout.addWidget(self.file_name_label)
        
        parent_layout.addWidget(time_frame)
    
    def load_audio_file(self, file_path: str) -> bool:
        """Load an audio file for playback."""
        try:
            audio_path = Path(file_path)
            if not audio_path.exists():
                logger.error(f"Audio file not found: {file_path}")
                return False
            
            # Set media source
            media_source = QUrl.fromLocalFile(str(audio_path.absolute()))
            self.media_player.setSource(media_source)
            
            # Update state
            self.audio_file_path = str(audio_path)
            self.file_name_label.setText(audio_path.name)
            
            # Enable controls
            self.set_enabled(True)
            
            logger.info(f"Loaded audio file: {audio_path.name}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading audio file {file_path}: {e}")
            return False
    
    def play(self):
        """Start playback."""
        if self.audio_file_path:
            self.media_player.play()
            self.position_timer.start()
    
    def pause(self):
        """Pause playback."""
        self.media_player.pause()
        self.position_timer.stop()
    
    def stop(self):
        """Stop playback."""
        self.media_player.stop()
        self.position_timer.stop()
        self.current_position = 0
        self._update_ui_position(0)
    
    def toggle_playback(self):
        """Toggle between play and pause."""
        if self.media_player.playbackState() == QMediaPlayer.PlayingState:
            self.pause()
        else:
            self.play()
    
    def skip_seconds(self, seconds: int):
        """Skip forward or backward by specified seconds."""
        if not self.audio_file_path:
            return
        
        current_pos = self.media_player.position()
        new_position = max(0, min(current_pos + (seconds * 1000), self.duration))
        
        self.media_player.setPosition(new_position)
        logger.debug(f"Skipped {seconds}s to position {new_position/1000:.1f}s")
    
    def set_position(self, position_ms: int):
        """Set playback position in milliseconds."""
        if self.audio_file_path:
            position_ms = max(0, min(position_ms, self.duration))
            self.media_player.setPosition(position_ms)
    
    def set_volume(self, volume: float):
        """Set volume (0.0 to 1.0)."""
        self.audio_output.setVolume(volume)
        self.volume_slider.setValue(int(volume * 100))
    
    def set_enabled(self, enabled: bool):
        """Enable or disable all controls."""
        self.play_pause_btn.setEnabled(enabled)
        self.stop_btn.setEnabled(enabled)
        self.skip_back_btn.setEnabled(enabled)
        self.skip_forward_btn.setEnabled(enabled)
        self.seek_slider.setEnabled(enabled)
        self.volume_slider.setEnabled(enabled)
        
        if not enabled:
            self.file_name_label.setText("No audio file loaded")
            self.current_time_label.setText("00:00")
            self.total_time_label.setText("00:00")
            self.seek_slider.setValue(0)
    
    def _on_position_changed(self, position: int):
        """Handle media player position changes."""
        if not self.is_seeking:
            self.current_position = position
            self._update_ui_position(position)
        
        self.positionChanged.emit(position)
    
    def _on_duration_changed(self, duration: int):
        """Handle media player duration changes."""
        self.duration = duration
        self.total_time_label.setText(self._format_time(duration))
        self.durationChanged.emit(duration)
    
    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState):
        """Handle playback state changes."""
        if state == QMediaPlayer.PlayingState:
            self.play_pause_btn.setText("⏸")
            self.play_pause_btn.setToolTip("Pause")
            self.position_timer.start()
        else:
            self.play_pause_btn.setText("▶")
            self.play_pause_btn.setToolTip("Play")
            if state == QMediaPlayer.StoppedState:
                self.position_timer.stop()
        
        self.playbackStateChanged.emit(state)
    
    def _on_volume_changed(self, value: int):
        """Handle volume slider changes."""
        volume = value / 100.0
        self.audio_output.setVolume(volume)
        self.volumeChanged.emit(volume)
    
    def _on_seek_start(self):
        """Handle seek slider press."""
        self.is_seeking = True
    
    def _on_seek_end(self):
        """Handle seek slider release."""
        if self.duration > 0:
            # Calculate position from slider value
            slider_value = self.seek_slider.value()
            new_position = int((slider_value / 1000.0) * self.duration)
            self.media_player.setPosition(new_position)
        
        self.is_seeking = False
    
    def _on_seek_changed(self, value: int):
        """Handle seek slider value changes."""
        if self.is_seeking and self.duration > 0:
            # Update time display during seeking
            position = int((value / 1000.0) * self.duration)
            self.current_time_label.setText(self._format_time(position))
    
    def _update_position(self):
        """Update position from media player."""
        if not self.is_seeking:
            position = self.media_player.position()
            self._update_ui_position(position)
    
    def _update_ui_position(self, position: int):
        """Update UI elements with current position."""
        self.current_time_label.setText(self._format_time(position))
        
        if self.duration > 0:
            # Update seek slider
            slider_value = int((position / self.duration) * 1000)
            self.seek_slider.setValue(slider_value)
    
    def _format_time(self, milliseconds: int) -> str:
        """Format time in milliseconds as MM:SS."""
        seconds = milliseconds // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"


class SimpleAudioControlWidget(QWidget):
    """Simplified audio control widget for basic play/pause functionality."""
    
    playRequested = Signal()
    pauseRequested = Signal()
    stopRequested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.audio_file_path = None
        self.setup_simple_ui()
    
    def setup_simple_ui(self):
        """Set up simplified UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.play_btn = QPushButton("Play")
        self.play_btn.setEnabled(False)
        self.play_btn.clicked.connect(self.playRequested.emit)
        
        self.file_label = QLabel("No audio file")
        self.file_label.setStyleSheet("QLabel { color: #666; }")
        
        layout.addWidget(self.play_btn)
        layout.addWidget(self.file_label)
        layout.addStretch()
    
    def set_audio_file(self, file_path: str):
        """Set audio file path."""
        self.audio_file_path = file_path
        if file_path and Path(file_path).exists():
            self.play_btn.setEnabled(True)
            self.file_label.setText(Path(file_path).name)
        else:
            self.play_btn.setEnabled(False)
            self.file_label.setText("No audio file")


# Factory function for easy integration
def create_audio_widget(enhanced: bool = True, parent=None) -> QWidget:
    """Create an audio control widget."""
    if not QT_AVAILABLE:
        # Return dummy widget if Qt not available
        widget = QWidget(parent)
        layout = QHBoxLayout(widget)
        layout.addWidget(QLabel("Audio controls not available"))
        return widget
    
    if enhanced:
        return AudioControlWidget(parent)
    else:
        return SimpleAudioControlWidget(parent)


if __name__ == "__main__":
    # Demo application
    app = QApplication(sys.argv)
    
    # Create test window
    window = QWidget()
    window.setWindowTitle("ZorOS Audio Controls Demo")
    window.setFixedSize(600, 200)
    
    layout = QVBoxLayout(window)
    
    # Create audio widget
    audio_widget = AudioControlWidget()
    layout.addWidget(audio_widget)
    
    # Add test button
    test_btn = QPushButton("Load Test Audio")
    def load_test_audio():
        # You can replace this with a real audio file path for testing
        test_file = "/System/Library/Sounds/Glass.aiff"  # macOS system sound
        if Path(test_file).exists():
            audio_widget.load_audio_file(test_file)
        else:
            print("Test audio file not found")
    
    test_btn.clicked.connect(load_test_audio)
    layout.addWidget(test_btn)
    
    window.show()
    sys.exit(app.exec())