# See architecture: docs/zoros_architecture.md#component-overview
import os
import sys
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QPushButton, QHBoxLayout
from PySide6.QtCore import Signal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ui.base_window import BaseWindow

class MainWindow(BaseWindow):
    openSettings = Signal()
    startRecording = Signal()
    stopRecording = Signal()
    closeApp = Signal()

    def __init__(self):
        """
        Initialize the main window.
        """
        super().__init__('WhisperWriter', 320, 180)
        self.recording = False
        self.initMainUI()

    def initMainUI(self):
        """
        Initialize the main user interface.
        """
        self.start_btn = QPushButton('Start')
        self.start_btn.setFont(QFont('Segoe UI', 10))
        self.start_btn.setFixedSize(120, 60)
        self.start_btn.clicked.connect(self.toggleRecording)

        settings_btn = QPushButton('Settings')
        settings_btn.setFont(QFont('Segoe UI', 10))
        settings_btn.setFixedSize(120, 60)
        settings_btn.clicked.connect(self.openSettings.emit)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(settings_btn)
        button_layout.addStretch(1)

        self.main_layout.addStretch(1)
        self.main_layout.addLayout(button_layout)
        self.main_layout.addStretch(1)

    def closeEvent(self, event):
        """
        Close the application when the main window is closed.
        """
        self.closeApp.emit()

    def toggleRecording(self):
        """Toggle recording on or off."""
        if not self.recording:
            self.startRecording.emit()
            self.start_btn.setText('Stop')
            self.recording = True
        else:
            self.stopRecording.emit()
            self.start_btn.setText('Start')
            self.recording = False

    def update_recording_state(self, recording: bool):
        """Update button text based on recording state."""
        self.recording = recording
        self.start_btn.setText('Stop' if recording else 'Start')

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
