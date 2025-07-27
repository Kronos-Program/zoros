"""
ZorOS Intake UI - Voice Recording and Transcription Interface

This module provides a PySide6-based user interface for capturing voice notes
and free-form text, with real-time transcription using various Whisper backends.
The content is stored as "intake fibers" in a local SQLite database for later
processing and management.

Specification: docs/requirements/dictation_requirements.md#ui-workflow
Architecture: docs/zoros_architecture.md#ui-blueprint
Tests: tests/test_intake_pipeline.py
Database: source/interfaces/intake/main.py#_ensure_db
Configuration: source/interfaces/intake/main.py#load_settings

Related Modules:
- source/interfaces/intake/dictation_library.py - Dictation management interface
- source/dictation_backends/ - Transcription backend implementations
- docs/dictation_library.md - Library documentation
- docs/dictation.md - Workflow documentation

Dependencies:
- External libraries: PySide6, sounddevice, soundfile, numpy
- Internal modules: source.dictation_backends
- Configuration: config/intake_settings.json

Example usage:
    python -m source.interfaces.intake.main
"""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import threading
import uuid
from uuid import UUID
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import time
from time import perf_counter
from pathlib import Path
import logging
from zoros.logger import get_logger
import shutil
from typing import Optional, Callable, List, Dict, Any
import argparse

import numpy as np
try:  # optional at import time
    import sounddevice as sd
except Exception:  # pragma: no cover - missing PortAudio
    sd = None  # type: ignore
import soundfile as sf
try:  # optional requests
    import requests  # type: ignore
except Exception:  # pragma: no cover - fallback
    requests = None
from backend.services.dictation import (
    get_backend_class,
    get_available_backends,
    is_backend_available,
    check_backend,
)
from backend.services.hotkey_service import get_hotkey_service
# Optional imports for specialized backends - these will be loaded via registry
try:
    from backend.services.dictation.live_chunk_processor import LiveChunkProcessor
    LIVE_CHUNK_PROCESSOR_AVAILABLE = True
except ImportError:
    LIVE_CHUNK_PROCESSOR_AVAILABLE = False
from backend.core.models.fiber import Fiber
try:
    from backend.interfaces.dictation_stability import get_stability_manager
    STABILITY_AVAILABLE = True
except ImportError:
    STABILITY_AVAILABLE = False
try:  # optional PySide6 imports
    from PySide6.QtCore import Qt, QTimer, Signal
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import (
        QApplication,
        QLabel,
        QMainWindow,
        QPushButton,
        QTextEdit,
        QVBoxLayout,
        QWidget,
        QHBoxLayout,
        QCheckBox,
        QStatusBar,
        QComboBox,
        QDialog,
        QFormLayout,
        QMessageBox,
    )
except Exception:  # pragma: no cover - missing Qt
    import sys
    import types

    class _Dummy:  # minimal stand-in for Qt classes
        def __init__(self, *args, **kwargs):
            pass

        def __call__(self, *args, **kwargs):
            return self

        def __getattr__(self, name):
            return _Dummy()

        def windowFlags(self):
            return 0

        def __ge__(self, other):
            return True

        def __lt__(self, other):
            return False

        def __getitem__(self, key):
            return _Dummy()

        def get(self, key, default=None):
            return default

        def addItem(self, *args, **kwargs):
            pass

        def findData(self, data):
            return 0

        def setCurrentIndex(self, index):
            pass

        def setCurrentText(self, text):
            pass

        def addItems(self, items):
            pass

        def setChecked(self, checked):
            pass

        def isChecked(self):
            return False

        def addRow(self, *args, **kwargs):
            pass

        def addWidget(self, widget):
            pass

        def addLayout(self, layout):
            pass

        def setLayout(self, layout):
            pass

        def setFixedWidth(self, width):
            pass

        def setCentralWidget(self, widget):
            pass

        def setStatusBar(self, statusbar):
            pass

        def setWindowTitle(self, title):
            pass

        def setWindowFlags(self, flags):
            pass

        def windowFlags(self):
            return 0

        def setInterval(self, interval):
            pass

        def setSingleShot(self, single_shot):
            pass

        def timeout(self):
            return _Dummy()

        def connect(self, signal, slot):
            pass

        def start(self):
            pass

        def stop(self):
            pass

        def hide(self):
            pass

        def show(self):
            pass

        def setEnabled(self, enabled):
            pass

        def isEnabled(self):
            return True

        def setStyleSheet(self, stylesheet):
            pass

        def setText(self, text):
            pass

        def toPlainText(self):
            return ""

        def clear(self):
            pass

        def setPlainText(self, text):
            pass

        def currentMessage(self):
            return ""

        def clearMessage(self):
            pass

        def showMessage(self, message, timeout=0):
            pass

        def setStyleSheet(self, stylesheet):
            pass

        def instance(self):
            return _Dummy()

        def clipboard(self):
            return _Dummy()

        def setText(self, text):
            pass

        def exec(self):
            return 0

        def get_values(self):
            return {}

        def accept(self):
            pass

        def reject(self):
            pass

        def information(self, parent, title, text):
            pass

        def DialogCode(self):
            return _Dummy()

        def Accepted(self):
            return 0

        def WindowType(self):
            return _Dummy()

        def WindowStaysOnTopHint(self):
            return 0

    _Dummy.WindowStaysOnTopHint = 0

    Qt = QTimer = Signal = QIcon = QApplication = QLabel = QMainWindow = QPushButton = QTextEdit = _Dummy  # type: ignore
    QVBoxLayout = QWidget = QHBoxLayout = QCheckBox = QStatusBar = QComboBox = QDialog = QFormLayout = QMessageBox = _Dummy  # type: ignore

    # provide stub modules so unittest.mock.patch can resolve them
    base = types.ModuleType("PySide6")
    sys.modules.setdefault("PySide6", base)
    for name in ["QtWebEngineWidgets"]:
        mod = types.ModuleType(f"PySide6.{name}")
        setattr(mod, "QWebEngineView", _Dummy)
        sys.modules.setdefault(f"PySide6.{name}", mod)


logger = get_logger(__name__)

DB_PATH = Path("zoros_intake.db")
# Folder for persisted intake audio files
AUDIO_DIR = Path("audio") / "intake"
# Exposed dictation directory for debug/export
DICTATIONS_DIR = Path("data") / "dictations"

# Configuration defaults and path
ROOT_DIR = Path(__file__).resolve().parents[3]
CONFIG_PATH = ROOT_DIR / "config" / "intake_settings.json"

DEFAULT_SETTINGS = {
    "PersistentAudioStream": False,
    "SelectedAudioDevice": None,
    "WhisperBackend": "StandardWhisper",
    "WhisperModel": "small",
    "AutoCopy": False,
    "ExposeData": False,
    "DebugLog": False,
}


class ResourceMonitor:
    """Monitor system resources for leak detection."""
    
    def __init__(self):
        self.initial_memory = _mem_usage_mb()
        self.initial_threads = threading.active_count()
        # Adjust thresholds for ML models (MLX Whisper can use 1-3GB)
        self.max_memory_increase = 3000  # MB threshold - accommodate ML models
        self.max_thread_increase = 15  # Thread threshold
        
    def check_leaks(self) -> Dict[str, Any]:
        """Check for resource leaks and return status."""
        current_memory = _mem_usage_mb()
        current_threads = threading.active_count()
        
        memory_increase = current_memory - self.initial_memory
        thread_increase = current_threads - self.initial_threads
        
        status = {
            'memory_leak': memory_increase > self.max_memory_increase,
            'thread_leak': thread_increase > self.max_thread_increase,
            'memory_usage': current_memory,
            'memory_increase': memory_increase,
            'thread_count': current_threads,
            'thread_increase': thread_increase,
            'timestamp': time.time()
        }
        
        if status['memory_leak'] or status['thread_leak']:
            print(f"LEAK DETECTED: Memory +{memory_increase:.1f}MB, Threads +{thread_increase}")
            
        return status


class SemaphoreTracker:
    """Track semaphore and lock usage for leak detection."""
    
    def __init__(self):
        self.active_semaphores = set()
        self.semaphore_count = 0
        self.max_semaphores = 50  # Reasonable limit
        
    def register_semaphore(self, semaphore_id: str) -> None:
        """Register a new semaphore."""
        self.active_semaphores.add(semaphore_id)
        self.semaphore_count += 1
        print(f"SEMAPHORE: Registered {semaphore_id} (total: {len(self.active_semaphores)})")
        
        if len(self.active_semaphores) > self.max_semaphores:
            print(f"WARNING: Semaphore leak detected - {len(self.active_semaphores)} active")
            
    def unregister_semaphore(self, semaphore_id: str) -> None:
        """Unregister a semaphore."""
        if semaphore_id in self.active_semaphores:
            self.active_semaphores.remove(semaphore_id)
            print(f"SEMAPHORE: Unregistered {semaphore_id} (total: {len(self.active_semaphores)})")
        else:
            print(f"WARNING: Attempted to unregister unknown semaphore {semaphore_id}")
            
    def force_cleanup(self) -> None:
        """Force cleanup of all tracked semaphores."""
        print(f"EMERGENCY: Force cleaning {len(self.active_semaphores)} semaphores")
        self.active_semaphores.clear()
        
    def get_status(self) -> Dict[str, Any]:
        """Get current semaphore status."""
        return {
            'active_count': len(self.active_semaphores),
            'total_created': self.semaphore_count,
            'active_ids': list(self.active_semaphores),
            'leak_detected': len(self.active_semaphores) > self.max_semaphores
        }


def _mem_usage_mb() -> float:
    """Return current process memory in MB.

    Spec: docs/requirements/dictation_requirements.md#audio-recording
    Tests: tests/test_intake_pipeline.py#test_memory_usage
    """
    try:  # use psutil if available
        import psutil  # type: ignore

        return psutil.Process().memory_info().rss / 1024 / 1024
    except Exception:  # pragma: no cover - optional
        import resource
        import sys

        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform == "darwin":
            rss /= 1024 * 1024
        else:
            rss /= 1024
        return float(rss)


def init_logging(debug: bool) -> None:
    """Configure application logging.

    Args:
        debug: Enable debug level logging when ``True``.

    Spec: docs/requirements/dictation_requirements.md#configuration
    Tests: tests/test_intake_pipeline.py#test_debug_logging
    """
    if debug:
        logger.setLevel(logging.DEBUG)

def _ensure_db(db: Path = DB_PATH) -> None:
    """Create the intake table if it does not exist.
    
    This function ensures the SQLite database has the correct schema for
    storing intake fibers. It creates the table if it doesn't exist and
    adds missing columns if the table exists but is missing required fields.
    
    Args:
        db: Path to the SQLite database file
        
    Spec: docs/requirements/dictation_requirements.md#data-model
    Tests: tests/test_intake_pipeline.py#test_insert_intake
    Integration: source/interfaces/intake/dictation_library.py#DictationLibraryWindow
    """
    with sqlite3.connect(db) as conn:
        # Check if table exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='intake'")
        table_exists = cursor.fetchone() is not None
        
        if not table_exists:
            # Create new table with all columns
            conn.execute(
                """
                CREATE TABLE intake (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT,
                    content TEXT,
                    audio_path TEXT,
                    correction TEXT,
                    fiber_type TEXT,
                    submitted INTEGER DEFAULT 1
                )
                """
            )
            print(f"DEBUG: Created new intake table with all columns")
        else:
            # Check if correction column exists
            cursor = conn.execute("PRAGMA table_info(intake)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'correction' not in columns:
                print(f"DEBUG: Adding missing 'correction' column to intake table")
                conn.execute("ALTER TABLE intake ADD COLUMN correction TEXT")
            
            if 'fiber_type' not in columns:
                print(f"DEBUG: Adding missing 'fiber_type' column to intake table")
                conn.execute("ALTER TABLE intake ADD COLUMN fiber_type TEXT")
            
            if 'submitted' not in columns:
                print(f"DEBUG: Adding missing 'submitted' column to intake table")
                conn.execute("ALTER TABLE intake ADD COLUMN submitted INTEGER DEFAULT 1")
        
        conn.commit()


def insert_intake(
    content: str,
    audio_path: Optional[str],
    correction: Optional[str] = None,
    fiber_type: str = "dictation",
    db: Path = DB_PATH,
    *,
    fiber_id: str | None = None,
    submitted: bool = True,
) -> str:
    """Insert a new intake fiber row and return its ID.
    
    This function creates a new dictation record in the database with the
    provided content, audio path, and metadata. It handles both submitted
    and draft dictations, with proper timestamp and ID generation.
    
    Args:
        content: The transcription or text content
        audio_path: Optional path to the associated audio file
        correction: Optional corrected version of the content
        fiber_type: Type of fiber ("dictation" or "free_text")
        db: Database path to use
        fiber_id: Optional custom ID, generates UUID if not provided
        submitted: Whether the dictation is submitted or draft
        
    Returns:
        The fiber ID (UUID string)
        
    Spec: docs/requirements/dictation_requirements.md#data-model
    Tests: tests/test_intake_pipeline.py#test_insert_intake
    Integration: source/interfaces/intake/dictation_library.py#load_dictations
    """
    _ensure_db(db)
    fid = fiber_id or str(uuid.uuid4())
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO intake (id, timestamp, content, audio_path, correction, fiber_type, submitted) VALUES (?,?,?,?,?,?,?)",
            (
                fid,
                datetime.utcnow().isoformat(),
                content,
                audio_path,
                correction,
                fiber_type,
                1 if submitted else 0,
            ),
        )
        conn.commit()
    return fid


def create_fiber_from_intake(fid: str, db: Path = DB_PATH) -> Fiber:
    """Return a :class:`Fiber` object for the given intake record."""
    _ensure_db(db)
    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT id, content, audio_path FROM intake WHERE id = ?",
            (fid,),
        ).fetchone()
    if not row:
        raise KeyError(fid)
    fiber_type = "audio" if row[2] else "text"
    return Fiber(
        id=UUID(row[0]),
        content=row[1],
        type=fiber_type,
        metadata={},
        revision_count=0,
        created_at=datetime.utcnow(),
        source="intake",
    )


_LOAD_ERROR = False

def load_settings() -> dict:
    """Load settings from ``CONFIG_PATH`` or return defaults.

    Returns:
        Mapping of configuration keys to values.

    Spec: docs/requirements/dictation_requirements.md#configuration
    Tests: tests/test_intake_pipeline.py#test_settings_dialog
    """
    global _LOAD_ERROR
    _LOAD_ERROR = False
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key, val in DEFAULT_SETTINGS.items():
            data.setdefault(key, val)
        return data
    except FileNotFoundError:
        return DEFAULT_SETTINGS.copy()
    except Exception:
        _LOAD_ERROR = True
        print("Error parsing settings; using defaults.")
        return DEFAULT_SETTINGS.copy()


def save_settings(data: dict) -> None:
    """Persist settings to ``CONFIG_PATH``.

    Args:
        data: Settings mapping to persist.

    Spec: docs/requirements/dictation_requirements.md#configuration
    Tests: tests/test_intake_pipeline.py#test_settings_dialog
    """
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


class SettingsDialog(QDialog):
    """Modal window for adjusting intake settings.
    
    This dialog provides a user interface for configuring dictation settings
    including audio device selection, Whisper backend configuration, and
    general application preferences.
    
    Spec: docs/requirements/dictation_requirements.md#configuration
    Tests: tests/test_intake_pipeline.py#test_settings_dialog
    Usage: source/interfaces/intake/main.py#show_settings
    
    Dependencies:
    - PySide6.QtWidgets for UI components
    - sounddevice for audio device enumeration
    """

    def __init__(
        self,
        settings: dict,
        available_backends: list[str],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Intake Settings")
        
        # Set window icon
        icon_path = Path(__file__).resolve().parents[3] / "assets" / "icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
            
        layout = QFormLayout(self)

        self.persistent_cb = QCheckBox("Persistent Audio Stream")
        self.persistent_cb.setChecked(settings.get("PersistentAudioStream", False))
        self.toggle_btn = QPushButton("Disable" if self.persistent_cb.isChecked() else "Enable")
        self.toggle_btn.clicked.connect(self._toggle_persistent)
        layout.addRow(self.persistent_cb, self.toggle_btn)

        # Audio device selection with refresh capability
        device_layout = QHBoxLayout()
        self.device_box = QComboBox()
        self._populate_audio_devices(settings)
        device_layout.addWidget(self.device_box)
        
        refresh_devices_btn = QPushButton("🔄")
        refresh_devices_btn.setToolTip("Refresh audio device list")
        refresh_devices_btn.setMaximumWidth(30)
        refresh_devices_btn.clicked.connect(self._refresh_audio_devices)
        device_layout.addWidget(refresh_devices_btn)
        
        layout.addRow("Audio Device", device_layout)

        # Foldable backend section
        self.backend_section_toggle = QPushButton("▼ Backend Configuration")
        self.backend_section_toggle.setCheckable(True)
        self.backend_section_toggle.setChecked(True)
        self.backend_section_toggle.clicked.connect(self._toggle_backend_section)
        layout.addRow(self.backend_section_toggle)

        # Backend configuration section
        self.backend_section = QWidget()
        backend_layout = QFormLayout(self.backend_section)
        
        # Backend selection with prioritization controls
        backend_selection_layout = QHBoxLayout()
        
        self.backend_box = QComboBox()
        self.available_backends = available_backends.copy()  # Make a copy to allow reordering
        
        # Load saved backend priority if available
        saved_priority = settings.get("BackendPriority", [])
        if saved_priority and set(saved_priority) == set(self.available_backends):
            self.available_backends = saved_priority
        
        # Add backend box to layout first
        backend_selection_layout.addWidget(self.backend_box)
        
        # Backend promotion buttons
        self.promote_btn = QPushButton("⬆️")
        self.promote_btn.setToolTip("Move backend up in priority")
        self.promote_btn.clicked.connect(self._promote_backend)
        backend_selection_layout.addWidget(self.promote_btn)
        
        self.demote_btn = QPushButton("⬇️")
        self.demote_btn.setToolTip("Move backend down in priority")
        self.demote_btn.clicked.connect(self._demote_backend)
        backend_selection_layout.addWidget(self.demote_btn)
        
        # Now populate the backend box after buttons are created
        self._populate_backend_box()
        current_backend = settings.get("WhisperBackend", available_backends[0] if available_backends else "StandardOpenAIWhisper")
        self.backend_box.setCurrentText(current_backend)
        self.backend_box.currentIndexChanged.connect(self._update_promotion_buttons)
        
        backend_widget = QWidget()
        backend_widget.setLayout(backend_selection_layout)
        backend_layout.addRow("Whisper Backend", backend_widget)

        self.model_box = QComboBox()
        self.model_box.addItems(["small", "medium", "large", "large-v3-turbo"])
        self.model_box.setCurrentText(settings.get("WhisperModel", "small"))
        backend_layout.addRow("Whisper Model", self.model_box)
        
        layout.addRow(self.backend_section)

        self.autocopy_cb = QCheckBox("Auto copy transcript")
        self.autocopy_cb.setChecked(settings.get("AutoCopy", False))
        layout.addRow(self.autocopy_cb)

        self.debug_cb = QCheckBox("Debug Log")
        self.debug_cb.setChecked(settings.get("DebugLog", False))
        layout.addRow(self.debug_cb)

        self.expose_cb = QCheckBox("Expose Data")
        self.expose_cb.setChecked(settings.get("ExposeData", False))
        layout.addRow(self.expose_cb)

        btn_layout = QHBoxLayout()
        
        # Add hotkey settings button
        hotkey_settings_btn = QPushButton("🎹 Hotkey Settings")
        hotkey_settings_btn.clicked.connect(self._open_hotkey_settings)
        btn_layout.addWidget(hotkey_settings_btn)
        
        btn_layout.addStretch()  # Add space between hotkey button and other buttons
        
        save = QPushButton("Save")
        cancel = QPushButton("Cancel")
        test = QPushButton("Test")
        save.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        test.clicked.connect(self._run_test)
        btn_layout.addWidget(save)
        btn_layout.addWidget(cancel)
        btn_layout.addWidget(test)
        layout.addRow(btn_layout)

    def _toggle_persistent(self) -> None:
        self.persistent_cb.setChecked(not self.persistent_cb.isChecked())
        self.toggle_btn.setText(
            "Disable" if self.persistent_cb.isChecked() else "Enable"
        )

    def _run_test(self) -> None:
        from source.dictation_backends import check_backend

        backend = self.backend_box.currentText()
        device = self.device_box.currentData()
        
        print(f"DEBUG: Testing backend: {backend}")
        print(f"DEBUG: Testing device: {device}")
        
        # Test backend
        backend_ok = check_backend(backend)
        print(f"DEBUG: Backend test result: {backend_ok}")
        
        # Test microphone with detailed info
        mic_ok = test_audio_device(device)
        print(f"DEBUG: Microphone test result: {mic_ok}")
        
        # Get device info
        device_info = "Unknown"
        if device is not None:
            try:
                devices = sd.query_devices()
                if device < len(devices):
                    dev = devices[device]
                    device_info = f"{dev['name']} (channels: {dev['max_input_channels']})"
            except Exception as e:
                device_info = f"Error getting device info: {e}"
        else:
            device_info = "Default device"
        
        # Create detailed test message
        msg = QMessageBox(self)
        msg.setWindowTitle("Device and Backend Test")
        
        text = f"Device: {device_info}\n"
        text += f"Backend: {backend}\n\n"
        text += f"Backend: {'✓ OK' if backend_ok else '✗ Unavailable'}\n"
        text += f"Microphone: {'✓ OK' if mic_ok else '✗ No audio signal'}\n\n"
        
        if not mic_ok:
            text += "Microphone issues:\n"
            text += "- Check if microphone is connected\n"
            text += "- Check system audio permissions\n"
            text += "- Try a different audio device\n"
            text += "- Speak louder during test\n"
        
        msg.setText(text)
        msg.setDetailedText(f"Backend test: {backend_ok}\nMicrophone test: {mic_ok}\nDevice: {device_info}")
        msg.exec()

    def _toggle_backend_section(self) -> None:
        """Toggle the visibility of the backend configuration section."""
        if self.backend_section_toggle.isChecked():
            self.backend_section.show()
            self.backend_section_toggle.setText("▼ Backend Configuration")
        else:
            self.backend_section.hide()
            self.backend_section_toggle.setText("▶ Backend Configuration")
    
    def _populate_backend_box(self) -> None:
        """Populate the backend combo box with descriptions and current order."""
        self.backend_box.clear()
        
        for b in self.available_backends:
            # Add descriptions for special backends
            if b == "StreamingMLXWhisper":
                self.backend_box.addItem(f"{b} (Parallel Processing - CRASH RISK)")
            elif b == "RealtimeStreamingMLXWhisper":
                self.backend_box.addItem(f"{b} (Live Streaming - CRASH RISK)")
            elif b == "MLXWhisper":
                self.backend_box.addItem(f"{b} (Apple Silicon Optimized)")
            elif b == "FasterWhisper":
                self.backend_box.addItem(f"{b} (GPU Accelerated)")
            elif b == "OpenAIAPI":
                self.backend_box.addItem(f"{b} (Cloud Service)")
            else:
                self.backend_box.addItem(b)
        
        self._update_promotion_buttons()
    
    def _update_promotion_buttons(self) -> None:
        """Update the state of promotion/demotion buttons based on current selection."""
        current_index = self.backend_box.currentIndex()
        self.promote_btn.setEnabled(current_index > 0)
        self.demote_btn.setEnabled(current_index < len(self.available_backends) - 1)
    
    def _promote_backend(self) -> None:
        """Move the currently selected backend up in priority (earlier in list)."""
        current_index = self.backend_box.currentIndex()
        if current_index > 0:
            # Swap with previous item
            backend = self.available_backends[current_index]
            self.available_backends[current_index] = self.available_backends[current_index - 1]
            self.available_backends[current_index - 1] = backend
            
            # Repopulate and select the moved item
            self._populate_backend_box()
            self.backend_box.setCurrentIndex(current_index - 1)
    
    def _demote_backend(self) -> None:
        """Move the currently selected backend down in priority (later in list)."""
        current_index = self.backend_box.currentIndex()
        if current_index < len(self.available_backends) - 1:
            # Swap with next item
            backend = self.available_backends[current_index]
            self.available_backends[current_index] = self.available_backends[current_index + 1]
            self.available_backends[current_index + 1] = backend
            
            # Repopulate and select the moved item
            self._populate_backend_box()
            self.backend_box.setCurrentIndex(current_index + 1)

    def _populate_audio_devices(self, settings: dict):
        """Populate the audio device combo box."""
        self.device_box.clear()
        self.device_box.addItem("Default", None)
        
        try:
            devices = sd.query_devices()
            for idx, dev in enumerate(devices):
                if isinstance(dev, dict) and dev.get("max_input_channels", 0) > 0:
                    self.device_box.addItem(dev["name"], idx)
        except Exception as e:
            logger.error(f"Error querying audio devices: {e}")
            # Add a fallback option
            self.device_box.addItem("Error - No devices detected", None)
        
        # Restore previous selection
        sel = settings.get("SelectedAudioDevice")
        if sel is not None:
            pos = self.device_box.findData(sel)
            if pos >= 0:
                self.device_box.setCurrentIndex(pos)
    
    def _refresh_audio_devices(self):
        """Refresh the audio device list."""
        current_selection = self.device_box.currentData()
        current_settings = {"SelectedAudioDevice": current_selection}
        
        # Store current selection text for feedback
        old_count = self.device_box.count()
        
        # Repopulate devices
        self._populate_audio_devices(current_settings)
        
        new_count = self.device_box.count()
        
        # Show feedback to user
        if new_count > old_count:
            QMessageBox.information(
                self, "Devices Refreshed", 
                f"Found {new_count - old_count} new audio device(s)!"
            )
        elif new_count < old_count:
            QMessageBox.information(
                self, "Devices Refreshed",
                f"Removed {old_count - new_count} unavailable device(s)."
            )
        else:
            QMessageBox.information(
                self, "Devices Refreshed",
                "Audio device list refreshed. No changes detected."
            )

    def _open_hotkey_settings(self):
        """Open the hotkey settings dialog."""
        try:
            from .hotkey_settings import HotkeySettingsDialog
            dialog = HotkeySettingsDialog(self)
            dialog.exec()
        except Exception as e:
            logger.error(f"Error opening hotkey settings: {e}")
            QMessageBox.critical(self, "Error", f"Failed to open hotkey settings: {e}")

    def get_values(self) -> dict:
        return {
            "PersistentAudioStream": self.persistent_cb.isChecked(),
            "SelectedAudioDevice": self.device_box.currentData(),
            "WhisperBackend": self.backend_box.currentText().split(" (")[0],  # Remove description
            "WhisperModel": self.model_box.currentText(),
            "AutoCopy": self.autocopy_cb.isChecked(),
            "DebugLog": self.debug_cb.isChecked(),
            "ExposeData": self.expose_cb.isChecked(),
            "BackendPriority": self.available_backends,  # Save the reordered list
        }


class Recorder:
    """Simple microphone recorder accumulating frames.
    
    This class handles real-time audio recording from the microphone,
    accumulating audio frames and providing level monitoring for
    visual feedback during recording. Supports real-time streaming
    for immediate transcription feedback.
    
    Spec: docs/requirements/dictation_requirements.md#audio-recording
    Tests: tests/test_intake_pipeline.py#test_recorder_class
    Usage: source/interfaces/intake/main.py#IntakeWindow
    
    Dependencies:
    - sounddevice for audio capture
    - numpy for audio data processing
    - RealtimeStreamingBackend for real-time transcription
    """

    def __init__(self, sample_rate: int = 16000) -> None:
        self.sample_rate = sample_rate
        self.stream: Optional[sd.InputStream] = None
        self.frames: list[np.ndarray] = []
        self.level: float = 0.0
        self.device: Optional[int] = None
        
        # Recording state
        self.recording_start_time: Optional[float] = None
        

    def _callback(self, indata, frames, time, status) -> None:  # pragma: no cover - passthrough
        # Only print debug info occasionally to avoid spam
        if len(self.frames) % 100 == 0:  # Every 100 frames
            print(f"DEBUG: Audio callback - frames: {len(self.frames)}, level: {self.level:.6f}")
        
        self.frames.append(indata.copy())
        self.level = float(np.abs(indata).mean())

    def start(self, device: Optional[int] = None) -> None:
        print(f"DEBUG: Recorder.start() called")
        print(f"DEBUG: Device: {device}")
        print(f"DEBUG: Sample rate: {self.sample_rate}")
        
        self.frames = []
        self.level = 0.0
        self.recording_start_time = perf_counter()  # Use perf_counter for consistency
        
        if device is not None:
            self.device = device
            print(f"DEBUG: Set device to: {self.device}")
        
        print(f"DEBUG: Creating sounddevice InputStream")
        try:
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                callback=self._callback,
                device=self.device,
            )
            print(f"DEBUG: InputStream created successfully")
            
            print(f"DEBUG: Starting InputStream")
            self.stream.start()
            print(f"DEBUG: InputStream started successfully")
        except Exception as e:
            print(f"DEBUG: Error creating/starting InputStream: {e}")
            import traceback
            traceback.print_exc()
            raise

    def stop(self, path: Path, keep_stream: bool = False) -> None:
        """Stop recording and save audio file.
        
        Args:
            path: Path to save the complete audio file
            keep_stream: Whether to keep the audio stream open
        """
        print(f"DEBUG: Recorder.stop() called with keep_stream={keep_stream}")
        
        if not self.stream:
            print(f"DEBUG: No stream to stop")
            return
        
        try:
            # Always stop the stream to prevent callbacks
            print(f"DEBUG: Stopping stream...")
            self.stream.stop()
            print(f"DEBUG: Stream stopped successfully")
            
            # CRITICAL FIX: Always close the stream to prevent semaphore leaks
            # The keep_stream parameter is causing semaphore leaks in persistent mode
            print(f"DEBUG: Closing stream (was keep_stream={keep_stream}, now always closing)")
            self.stream.close()
            self.stream = None
            print(f"DEBUG: Stream closed and set to None")
            
            self.level = 0.0
            
            if self.frames:
                print(f"DEBUG: Saving {len(self.frames)} audio frames to {path}")
                audio = np.concatenate(self.frames)
                sf.write(str(path), audio, self.sample_rate)
                print(f"DEBUG: Audio saved successfully")
            else:
                print(f"DEBUG: No frames to save")
                
        except Exception as e:
            print(f"DEBUG: Error in recorder stop: {e}")
            import traceback
            traceback.print_exc()
            
            # Force cleanup on error
            try:
                if self.stream:
                    self.stream.close()
                self.stream = None
                print(f"DEBUG: Forced stream cleanup completed")
            except Exception as cleanup_error:
                print(f"DEBUG: Error in forced cleanup: {cleanup_error}")
                
            raise


def get_backend_map() -> dict[str, Callable[[str], object]]:
    """Get available backend classes using the registry system."""
    backend_map = {}
    available_backends = get_available_backends()
    
    for backend_name in available_backends:
        try:
            backend_class = get_backend_class(backend_name)
            backend_map[backend_name] = backend_class
        except Exception as e:
            logger.warning(f"Failed to load backend {backend_name}: {e}")
    
    return backend_map


def test_audio_device(device: Optional[int] = None) -> bool:
    """Return True if audio device produces a detectable signal."""
    try:
        frames = sd.rec(int(0.5 * 16000), samplerate=16000, channels=1, device=device)
        sd.wait()
        level = float(np.abs(frames).mean())
        print(f"DEBUG: Audio device test level: {level}")
        # Lower threshold to detect very quiet microphones
        return level > 0.00001  # Much lower threshold
    except Exception as err:  # pragma: no cover - passthrough
        logger.error("Audio device test failed: %s", err)
        return False


def transcribe_audio(wav_path: str, backend: str = "StandardWhisper", model: str = "small") -> str:
    """Transcribe audio file using specified backend and model.
    
    This function provides transcription capabilities using various Whisper backends.
    It includes detailed timing measurements for performance analysis.
    
    Args:
        wav_path: Path to the audio file to transcribe
        backend: Whisper backend to use (MLXWhisper, FasterWhisper, etc.)
        model: Model size/type to use (small, medium, large, large-v3-turbo)
        
    Returns:
        Transcribed text as string
        
    Spec: docs/requirements/dictation_requirements.md#transcription-requirements
    Tests: tests/test_transcription_performance.py#test_transcription_backend_performance
    Integration: source/dictation_backends/ for backend implementations
    """
    import time
    from pathlib import Path
    
    # Initialize timing measurements
    timing_data = {
        'total_start': time.time(),
        'audio_validation': 0,
        'backend_initialization': 0,
        'model_loading': 0,
        'transcription_core': 0,
        'result_processing': 0,
        'total_end': 0
    }
    
    # Step 1: Audio file validation
    validation_start = time.time()
    audio_path = Path(wav_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {wav_path}")
    
    # Get audio file info for analysis
    audio_size = audio_path.stat().st_size
    timing_data['audio_validation'] = time.time() - validation_start
    
    print(f"DEBUG: Attempting transcription with backend: {backend}, model: {model}")
    print(f"DEBUG: Audio file path: {wav_path}")
    print(f"DEBUG: Audio file size: {audio_size / 1024:.1f} KB")
    
    try:
        # Step 2: Backend initialization
        init_start = time.time()
        if backend == "MLXWhisper":
            print("DEBUG: Trying MLXWhisper backend with bus error protection...")
            try:
                # Bus error protection for MLX operations
                import signal
                import sys
                
                def bus_error_handler(signum, frame):
                    print("EMERGENCY: Bus error detected in MLX operation!")
                    print("DEBUG: MLX backend crashed - this is a known issue")
                    raise RuntimeError("MLX backend bus error - falling back to alternative")
                
                # Set up bus error handler
                original_handler = signal.signal(signal.SIGBUS, bus_error_handler)
                
                try:
                    backend_instance = MLXWhisperBackend(model)
                    timing_data['backend_initialization'] = time.time() - init_start
                    
                    # Step 3: Model loading (for MLXWhisper, this happens during first transcription)
                    model_start = time.time()
                    result = backend_instance.transcribe(wav_path)
                    model_time = time.time() - model_start
                    
                finally:
                    # Restore original handler
                    signal.signal(signal.SIGBUS, original_handler)
                    
            except (RuntimeError, OSError, Exception) as mlx_error:
                print(f"DEBUG: MLX backend failed with bus error protection: {mlx_error}")
                # Force fallback to safer backend
                print("DEBUG: Falling back to FasterWhisper due to MLX instability")
                backend = "FasterWhisper"
                
                # Try FasterWhisper as emergency fallback
                try:
                    from faster_whisper import WhisperModel
                    model_start = time.time()
                    wm = WhisperModel(model)
                    timing_data['model_loading'] = time.time() - model_start
                    timing_data['backend_initialization'] = time.time() - init_start
                    
                    transcribe_start = time.time()
                    segments, _ = wm.transcribe(wav_path)
                    result = " ".join(seg.text for seg in segments).strip()
                    model_time = time.time() - transcribe_start
                    
                    print(f"DEBUG: Emergency FasterWhisper fallback result: {result[:100]}...")
                except Exception as fallback_error:
                    print(f"DEBUG: Emergency fallback also failed: {fallback_error}")
                    raise RuntimeError(f"Both MLX and FasterWhisper failed: {mlx_error}, {fallback_error}")
            
            # For MLXWhisper, we can't easily separate model loading from transcription
            # So we'll estimate based on typical model loading times
            if "large-v3-turbo" in model:
                estimated_model_load = 2.0  # seconds for large model
                timing_data['model_loading'] = estimated_model_load
                timing_data['transcription_core'] = model_time - estimated_model_load
            else:
                estimated_model_load = 0.5  # seconds for smaller models
                timing_data['model_loading'] = estimated_model_load
                timing_data['transcription_core'] = model_time - estimated_model_load
            
            print(f"DEBUG: MLXWhisper result: {result[:100]}...")
            
        elif backend == "ParallelMLXWhisper":
            print("DEBUG: Trying ParallelMLXWhisper backend with bus error protection...")
            try:
                # Bus error protection for MLX operations
                import signal
                
                def bus_error_handler(signum, frame):
                    print("EMERGENCY: Bus error detected in ParallelMLX operation!")
                    raise RuntimeError("ParallelMLX backend bus error - falling back to alternative")
                
                original_handler = signal.signal(signal.SIGBUS, bus_error_handler)
                
                try:
                    from source.dictation_backends.parallel_mlx_whisper_backend import ParallelMLXWhisperBackend
                    backend_instance = ParallelMLXWhisperBackend(model)
                    timing_data['backend_initialization'] = time.time() - init_start
                    
                    transcribe_start = time.time()
                    result = backend_instance.transcribe(wav_path)
                    timing_data['transcription_core'] = time.time() - transcribe_start
                    
                    print(f"DEBUG: ParallelMLXWhisper result: {result[:100]}...")
                    
                finally:
                    signal.signal(signal.SIGBUS, original_handler)
                    
            except (RuntimeError, OSError, Exception) as mlx_error:
                print(f"DEBUG: ParallelMLX backend failed: {mlx_error}")
                print("DEBUG: Falling back to standard MLXWhisper")
                
                # Fallback to standard MLX backend
                try:
                    backend_instance = MLXWhisperBackend(model)
                    timing_data['backend_initialization'] = time.time() - init_start
                    
                    transcribe_start = time.time()
                    result = backend_instance.transcribe(wav_path)
                    timing_data['transcription_core'] = time.time() - transcribe_start
                    
                    print(f"DEBUG: MLX fallback result: {result[:100]}...")
                except Exception as fallback_error:
                    print(f"DEBUG: MLX fallback also failed: {fallback_error}")
                    raise RuntimeError(f"Both ParallelMLX and MLX failed: {mlx_error}, {fallback_error}")
            
        elif backend == "QueueBasedStreamingMLXWhisper":
            print("DEBUG: Trying QueueBasedStreamingMLXWhisper backend...")
            from source.dictation_backends.queue_based_streaming_backend import QueueBasedStreamingBackend
            backend_instance = QueueBasedStreamingBackend(model)
            timing_data['backend_initialization'] = time.time() - init_start
            
            transcribe_start = time.time()
            result = backend_instance.transcribe(wav_path)
            timing_data['transcription_core'] = time.time() - transcribe_start
            
            print(f"DEBUG: QueueBasedStreamingMLXWhisper result: {result[:100]}...")
            
        elif backend == "OpenAIAPI":
            print("DEBUG: Trying OpenAIAPI backend...")
            OpenAIAPIBackend = get_backend_class("OpenAIAPI")
            fb = OpenAIAPIBackend(model)
            timing_data['backend_initialization'] = time.time() - init_start
            
            transcribe_start = time.time()
            result = fb.transcribe(wav_path)
            timing_data['transcription_core'] = time.time() - transcribe_start
            
            print(f"DEBUG: OpenAIAPI result: {result[:100]}...")
            
        elif backend == "FasterWhisper":
            print("DEBUG: Trying FasterWhisper backend...")
            from faster_whisper import WhisperModel  # type: ignore
            
            model_start = time.time()
            wm = WhisperModel(model)
            timing_data['model_loading'] = time.time() - model_start
            timing_data['backend_initialization'] = time.time() - init_start
            
            transcribe_start = time.time()
            segments, _ = wm.transcribe(wav_path)
            result = " ".join(seg.text for seg in segments).strip()
            timing_data['transcription_core'] = time.time() - transcribe_start
            
            print(f"DEBUG: FasterWhisper result: {result[:100]}...")
            
        elif backend == "WhisperCPP":
            print("DEBUG: Trying WhisperCPP backend...")
            WhisperCPPBackend = get_backend_class("WhisperCPP")
            backend_instance = WhisperCPPBackend(model)
            timing_data['backend_initialization'] = time.time() - init_start
            
            transcribe_start = time.time()
            result = backend_instance.transcribe(wav_path)
            timing_data['transcription_core'] = time.time() - transcribe_start
            
            print(f"DEBUG: WhisperCPP result: {result[:100]}...")
            
        elif backend == "Mock":
            print("DEBUG: Using Mock backend...")
            MockBackend = get_backend_class("Mock")
            backend_instance = MockBackend(model)
            timing_data['backend_initialization'] = time.time() - init_start
            
            transcribe_start = time.time()
            result = backend_instance.transcribe(wav_path)
            timing_data['transcription_core'] = time.time() - transcribe_start
            
        else:
            raise ValueError(f"Unknown backend: {backend}")
            
    except Exception as e:
        print(f"DEBUG: {backend} failed with error: {e}")
        import traceback
        traceback.print_exc()
        print(f"{backend} not detected; using StandardWhisper.")
        
        # Fallback to StandardWhisper
        try:
            print("DEBUG: Trying StandardWhisper...")
            import whisper  # type: ignore
            
            model_start = time.time()
            wmodel = whisper.load_model(model)
            timing_data['model_loading'] = time.time() - model_start
            
            transcribe_start = time.time()
            result = wmodel.transcribe(wav_path)
            text_result = result.get("text", "").strip()
            timing_data['transcription_core'] = time.time() - transcribe_start
            
            print(f"DEBUG: StandardWhisper result: {text_result[:100]}...")
            result = text_result
            
        except Exception as e:
            print(f"DEBUG: StandardWhisper failed: {e}")
            try:
                print("DEBUG: Trying StandardOpenAIWhisperBackend...")
                fb = StandardOpenAIWhisperBackend(model)
                timing_data['backend_initialization'] = time.time() - init_start
                
                transcribe_start = time.time()
                result = fb.transcribe(wav_path)
                timing_data['transcription_core'] = time.time() - transcribe_start
                
                print(f"DEBUG: StandardOpenAIWhisperBackend result: {result[:100]}...")
                
            except Exception as err2:
                logging.error("StandardWhisper failed: %s", err2)
                print(f"DEBUG: All backends failed. Final error: {err2}")
                result = ""
    
    # Step 4: Result processing
    processing_start = time.time()
    if result:
        result = result.strip()
    timing_data['result_processing'] = time.time() - processing_start
    timing_data['total_end'] = time.time()
    
    # Calculate total time and percentages
    total_time = timing_data['total_end'] - timing_data['total_start']
    
    # Get audio duration for ratio calculation
    try:
        import soundfile as sf
        audio_info = sf.info(wav_path)
        audio_duration = audio_info.duration
        wav_to_transcription_ratio = audio_duration / total_time if total_time > 0 else 0
    except Exception:
        audio_duration = None
        wav_to_transcription_ratio = None
    
    # Print detailed timing analysis
    print(f"\n=== TRANSCRIPTION PIPELINE TIMING ANALYSIS ===")
    print(f"Audio file: {audio_path.name}")
    print(f"Audio size: {audio_size / 1024:.1f} KB")
    if audio_duration:
        print(f"Audio duration: {audio_duration:.2f}s")
        print(f"WAV time to transcription time ratio: {wav_to_transcription_ratio:.2f}x")
    print(f"Backend: {backend}")
    print(f"Model: {model}")
    print(f"Total time: {total_time:.3f}s")
    print(f"\nComponent breakdown:")
    print(f"  Audio validation: {timing_data['audio_validation']:.3f}s ({timing_data['audio_validation']/total_time*100:.1f}%)")
    print(f"  Backend initialization: {timing_data['backend_initialization']:.3f}s ({timing_data['backend_initialization']/total_time*100:.1f}%)")
    print(f"  Model loading: {timing_data['model_loading']:.3f}s ({timing_data['model_loading']/total_time*100:.1f}%)")
    print(f"  Transcription core: {timing_data['transcription_core']:.3f}s ({timing_data['transcription_core']/total_time*100:.1f}%)")
    print(f"  Result processing: {timing_data['result_processing']:.3f}s ({timing_data['result_processing']/total_time*100:.1f}%)")
    print(f"  Transcription efficiency: {len(result.split()) / total_time:.1f} words/second")
    
    # Save timing data for analysis
    timing_report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'audio_file': str(audio_path),
        'audio_size_kb': audio_size / 1024,
        'audio_duration': audio_duration,
        'backend': backend,
        'model': model,
        'wav_to_transcription_ratio': wav_to_transcription_ratio,
        'total_time': total_time,
        'timing_breakdown': timing_data,
        'result_length': len(result),
        'words_per_second': len(result.split()) / total_time if total_time > 0 else 0,
        'transcript_preview': result[:200] + "..." if len(result) > 200 else result
    }
    
    # Save to artifacts directory
    artifacts_dir = Path("artifacts")
    artifacts_dir.mkdir(exist_ok=True)
    
    timing_file = artifacts_dir / f"transcription_timing_{backend}_{model}_{int(time.time())}.json"
    with open(timing_file, 'w') as f:
        import json
        json.dump(timing_report, f, indent=2)
    
    print(f"Detailed timing report saved to: {timing_file}")
    print("=" * 50)
    
    return result


class IntakeWindow(QMainWindow):
    """Main intake UI window.
    
    This is the primary user interface for the ZorOS dictation system,
    providing recording controls, transcription display, and integration
    with the dictation library. It manages the complete workflow from
    audio recording to database storage.
    
    Spec: docs/requirements/dictation_requirements.md#ui-workflow
    Tests: tests/test_intake_pipeline.py#test_recording_simulation
    Integration: source/interfaces/intake/dictation_library.py#DictationLibraryWindow
    
    Dependencies:
    - PySide6 for UI components
    - source.dictation_backends for transcription
    - SQLite for data persistence
    """
    
    # Signal to stop timeout timer from main thread
    stop_timeout_signal = Signal()
    # Signal to finish transcription from main thread
    finish_transcription_signal = Signal(str)
    # Signal for thread-safe live transcript updates
    live_transcript_update_signal = Signal(str)

    def __init__(self, db_path: Path = DB_PATH, *, unified: bool = False) -> None:
        super().__init__()
        self.setWindowTitle("Zoros Intake")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        # Track window creation time for debugging premature closes
        self._window_creation_time = time.time()
        
        # Set window icon with enhanced Mac compatibility
        self._setup_window_icon()
        self.db_path = db_path
        self.unified = unified

        if self.unified:
            self._init_unified_ui()
            return
        self.recorder = Recorder()
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.audio_path: Optional[Path] = None
        self.backend_instance: Optional[object] = None
        self.current_future: Optional[object] = None
        
        # Live transcription components
        self.live_backend = None
        self.live_transcription_enabled = False  # Disabled by default to keep stable
        self.model_loaded_time = 0.0
        self.transcribe_start = 0.0
        self.elapsed = 0
        self.model_cache = {}  # Cache for loaded models
        self.current_backend = None
        self.current_model = None
        
        # Emergency robustness components
        self._recording_lock = threading.RLock()
        self._recording_stuck_detected = False
        self._resource_monitor = ResourceMonitor()
        self._semaphore_tracker = SemaphoreTracker()
        self._initial_thread_count = threading.active_count()
        
        # Start resource monitoring
        self._start_resource_monitoring()

        central = QWidget()
        layout = QVBoxLayout(central)

        # Top bar with settings gear and audio test panel
        top = QHBoxLayout()
        top.addWidget(QLabel("🎤 Intake"))
        top.addStretch()
        
        # Window management controls
        self.always_on_top_btn = QPushButton("📌 Always On Top")
        self.always_on_top_btn.setCheckable(True)
        self.always_on_top_btn.setChecked(True)  # Default state
        self.always_on_top_btn.clicked.connect(self.toggle_always_on_top)
        top.addWidget(self.always_on_top_btn)
        
        self.hide_btn = QPushButton("👁️ Hide")
        self.hide_btn.clicked.connect(self.hide_window)
        top.addWidget(self.hide_btn)
        
        # Audio test panel button
        self.audio_test_btn = QPushButton("🧪 Audio Test")
        self.audio_test_btn.clicked.connect(self.show_audio_test_panel)
        top.addWidget(self.audio_test_btn)
        
        # Settings button with emoji
        self.settings_btn = QPushButton("⚙️ Settings")
        self.settings_btn.clicked.connect(self.show_settings)
        top.addWidget(self.settings_btn)
        layout.addLayout(top)

        self.settings_panel = QWidget()
        sp_layout = QVBoxLayout(self.settings_panel)
        self.settings = load_settings()
        init_logging(bool(self.settings.get("DebugLog", False)))
        self.available_backends = get_available_backends() or ["StandardOpenAIWhisper"]
        print(f"DEBUG: Available backends: {self.available_backends}")
        print(f"DEBUG: Settings WhisperBackend: {self.settings.get('WhisperBackend')}")

        sp_layout.addWidget(QLabel("Whisper Backend"))
        self.backend_combo = QComboBox()
        for b in self.available_backends:
            self.backend_combo.addItem(b)
        if self.settings.get("WhisperBackend") in self.available_backends:
            self.backend_combo.setCurrentText(self.settings["WhisperBackend"])
        sp_layout.addWidget(self.backend_combo)

        sp_layout.addWidget(QLabel("Whisper Model"))
        self.model_combo = QComboBox()
        for m in ["small", "medium", "large"]:
            self.model_combo.addItem(m)
        self.model_combo.setCurrentText(self.settings.get("WhisperModel", "small"))
        sp_layout.addWidget(self.model_combo)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_settings)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.settings_panel.hide)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        sp_layout.addLayout(btn_row)
        self.settings_panel.hide()
        layout.addWidget(self.settings_panel)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.clear_timer = QTimer(self)
        self.clear_timer.setSingleShot(True)
        self.clear_timer.timeout.connect(lambda: self.status.clearMessage())
        app = QApplication.instance()
        self.clipboard = app.clipboard() if app else None

        self.record_btn = QPushButton("🔴 Record")
        self.record_btn.clicked.connect(self.toggle_record)
        rec_layout = QHBoxLayout()
        rec_layout.addWidget(self.record_btn)
        self.load_btn = QPushButton("📥 Load Model")
        self.load_btn.clicked.connect(self.toggle_model)
        rec_layout.addWidget(self.load_btn)
        self.clear_cache_btn = QPushButton("🗑️ Clear Cache")
        self.clear_cache_btn.clicked.connect(self.clear_model_cache)
        rec_layout.addWidget(self.clear_cache_btn)
        
        # Robust transcription toggle
        if STABILITY_AVAILABLE:
            self.robust_mode_cb = QCheckBox("🛡️ Robust Mode")
            self.robust_mode_cb.setToolTip("Enable intelligent retries and backend fallbacks")
            self.robust_mode_cb.setChecked(True)  # Default enabled
            rec_layout.addWidget(self.robust_mode_cb)
        
        self.timer_label = QLabel("0 s")
        self.timer_label.hide()
        rec_layout.addWidget(self.timer_label)
        self.wave_label = QLabel("")
        self.wave_label.hide()
        rec_layout.addWidget(self.wave_label)
        layout.addLayout(rec_layout)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._update_timer)

        self.wave_timer = QTimer(self)
        self.wave_timer.setInterval(100)
        self.wave_timer.timeout.connect(self._update_wave)

        layout.addWidget(QLabel("Transcription / Manual Input"))
        self.notes = QTextEdit()
        layout.addWidget(self.notes)

        # Navigation controls for browsing old intake fibers
        nav_layout = QHBoxLayout()
        
        self.prev_btn = QPushButton("◀️ Previous")
        self.prev_btn.clicked.connect(self.load_previous_record)
        nav_layout.addWidget(self.prev_btn)
        
        self.record_counter = QLabel("No records")
        self.record_counter.setStyleSheet("font-weight: bold; padding: 5px;")
        nav_layout.addWidget(self.record_counter)
        
        self.next_btn = QPushButton("Next ▶️")
        self.next_btn.clicked.connect(self.load_next_record)
        nav_layout.addWidget(self.next_btn)
        
        nav_layout.addStretch()
        
        self.refresh_records_btn = QPushButton("🔄 Refresh")
        self.refresh_records_btn.clicked.connect(self.refresh_records)
        nav_layout.addWidget(self.refresh_records_btn)
        
        layout.addLayout(nav_layout)

        # Initialize navigation state
        self.current_record_index = -1
        self.intake_records = []
        
        btn_row2 = QHBoxLayout()
        self.submit_btn = QPushButton("✅ Submit")
        self.submit_btn.clicked.connect(self.on_submit)
        btn_row2.addWidget(self.submit_btn)
        self.copy_btn = QPushButton("📋 Copy")
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        btn_row2.addWidget(self.copy_btn)
        clear = QPushButton("🗑️ Clear")
        clear.clicked.connect(self.notes.clear)
        btn_row2.addWidget(clear)
        self.library_btn = QPushButton("📚 Dictation Library")
        self.library_btn.clicked.connect(self.open_dictation_library)
        btn_row2.addWidget(self.library_btn)
        
        # Fiberizer button
        self.fiberizer_btn = QPushButton("🧬 Fiberizer")
        self.fiberizer_btn.clicked.connect(self.open_fiberizer)
        btn_row2.addWidget(self.fiberizer_btn)
        
        # Window management button
        self.window_manager_btn = QPushButton("🪟 Window Manager")
        self.window_manager_btn.clicked.connect(self.show_window_manager)
        btn_row2.addWidget(self.window_manager_btn)
        layout.addLayout(btn_row2)

        self.setCentralWidget(central)

        # Connect the signals
        self.stop_timeout_signal.connect(self._stop_timeout_timer)
        self.finish_transcription_signal.connect(self._finish_transcription)
        self.live_transcript_update_signal.connect(self._handle_live_transcript_update)
        
        # Register with window manager
        try:
            from ..window_manager import register_window
            self.window_id = register_window(self, "intake")
            logger.info(f"Registered intake window: {self.window_id}")
        except Exception as e:
            logger.warning(f"Could not register with window manager: {e}")
            self.window_id = None

        try:
            devices = sd.query_devices()
            input_devices = [d for d in devices if d.get("max_input_channels", 0) > 0]
            if not input_devices:
                raise RuntimeError("No input devices found")
            print(f"DEBUG: Found {len(input_devices)} input devices")
            for i, dev in enumerate(input_devices):
                print(f"DEBUG: Input device {i}: {dev['name']} (channels: {dev['max_input_channels']})")
        except Exception as e:
            print(f"DEBUG: Audio device detection error: {e}")
            self.record_btn.setEnabled(False)
            self.show_status("No microphone detected", error=True)

        self.apply_settings()
        
        # Initialize global hotkey service
        self._setup_hotkey_service()
        
        # Initialize navigation with existing records
        self.refresh_records()
        
        # Auto-preload model for maximum speed
        self._auto_preload_model()
        
        # Setup device monitoring - check for new devices every 30 seconds
        self._setup_device_monitoring()
    
    def _setup_device_monitoring(self) -> None:
        """Setup periodic monitoring for new audio devices."""
        self._device_monitoring_timer = QTimer(self)
        self._device_monitoring_timer.setInterval(30000)  # Check every 30 seconds
        self._device_monitoring_timer.timeout.connect(self._check_for_new_devices)
        self._device_monitoring_timer.start()
        
        # Keep track of known devices
        self._known_devices = set()
        try:
            devices = sd.query_devices()
            for idx, dev in enumerate(devices):
                if isinstance(dev, dict) and dev.get("max_input_channels", 0) > 0:
                    self._known_devices.add(dev["name"])
        except Exception as e:
            logger.debug(f"Error initializing device list: {e}")
        
        logger.info(f"Device monitoring started - tracking {len(self._known_devices)} input devices")
    
    def _check_for_new_devices(self) -> None:
        """Check for newly connected audio devices."""
        try:
            current_devices = set()
            devices = sd.query_devices()
            for idx, dev in enumerate(devices):
                if isinstance(dev, dict) and dev.get("max_input_channels", 0) > 0:
                    current_devices.add(dev["name"])
            
            # Check for new devices
            new_devices = current_devices - self._known_devices
            if new_devices:
                logger.info(f"New audio devices detected: {', '.join(new_devices)}")
                self._known_devices = current_devices
                # Optionally show a subtle notification
                self.show_status(f"New audio device detected: {list(new_devices)[0]}")
            
            # Check for removed devices
            removed_devices = self._known_devices - current_devices
            if removed_devices:
                logger.info(f"Audio devices removed: {', '.join(removed_devices)}")
                self._known_devices = current_devices
                
        except Exception as e:
            logger.debug(f"Error checking for new devices: {e}")

    def _start_resource_monitoring(self) -> None:
        """Start continuous resource monitoring for leak detection."""
        print(f"MONITOR: Starting resource monitoring")
        
        # Create resource monitoring timer
        self._resource_timer = QTimer(self)
        self._resource_timer.setInterval(30000)  # Check every 30 seconds
        self._resource_timer.timeout.connect(self._check_resources)
        self._resource_timer.start()
        
        # Create emergency detection timer
        self._emergency_timer = QTimer(self)
        self._emergency_timer.setInterval(5000)  # Emergency checks every 5 seconds
        self._emergency_timer.timeout.connect(self._emergency_health_check)
        self._emergency_timer.start()
        
        print(f"MONITOR: Resource monitoring started - threads: {threading.active_count()}, memory: {_mem_usage_mb():.1f}MB")
    
    def _check_resources(self) -> None:
        """Periodic resource leak check."""
        try:
            status = self._resource_monitor.check_leaks()
            semaphore_status = self._semaphore_tracker.get_status()
            
            if status['memory_leak'] or status['thread_leak'] or semaphore_status['leak_detected']:
                print(f"LEAK WARNING: Memory: {status['memory_usage']:.1f}MB (+{status['memory_increase']:.1f}), "
                      f"Threads: {status['thread_count']} (+{status['thread_increase']}), "
                      f"Semaphores: {semaphore_status['active_count']}")
                
                # Show warning in UI
                self.show_status(f"Resource leak detected - see console", error=True)
                
                # Trigger automatic cleanup if severe
                if status['memory_increase'] > 1000 or status['thread_increase'] > 20:
                    print(f"EMERGENCY: Severe resource leak - triggering cleanup")
                    self._force_recording_recovery()
                    
        except Exception as e:
            print(f"ERROR in resource check: {e}")
    
    def _emergency_health_check(self) -> None:
        """Emergency health check for critical issues."""
        try:
            # Check for hung recording states - use consistent timing
            if (hasattr(self, 'recording_start_time') and 
                self.record_btn.text() == "Stop" and 
                self.recording_start_time is not None):
                
                # Use perf_counter for consistency with UI timing
                current_duration = perf_counter() - self.recording_start_time
                print(f"DEBUG: Recording duration check: {current_duration:.1f}s")
                
                # Only trigger emergency after 5 minutes (300 seconds)
                if current_duration > 300:
                    print(f"EMERGENCY: Recording hung for >{current_duration:.1f}s - forcing recovery")
                    self._recording_stuck_detected = True
                    self._force_recording_recovery()
            
            # Check for stuck transcription
            if (hasattr(self, 'transcribe_start') and 
                hasattr(self, 'current_future') and self.current_future and
                not self.current_future.done() and
                (time.time() - self.transcribe_start) > 600):  # 10 minutes
                print(f"EMERGENCY: Transcription hung for >10 minutes - forcing cleanup")
                self._force_recording_recovery()
                
        except Exception as e:
            print(f"ERROR in emergency health check: {e}")

    def _setup_window_icon(self) -> None:
        """Setup window icon with Mac compatibility enhancements."""
        try:
            # Multiple icon paths to try
            icon_paths = [
                Path(__file__).resolve().parents[3] / "assets" / "icon.png",
                Path(__file__).resolve().parents[3] / "assets" / "zoros_icon.png",
                Path(__file__).resolve().parent / "icon.png",
            ]
            
            icon_set = False
            for icon_path in icon_paths:
                if icon_path.exists():
                    try:
                        icon = QIcon(str(icon_path))
                        if not icon.isNull():
                            self.setWindowIcon(icon)
                            
                            # Mac-specific: Also set application icon
                            if hasattr(QApplication, 'setWindowIcon'):
                                QApplication.instance().setWindowIcon(icon)
                            
                            print(f"DEBUG: Icon loaded successfully from: {icon_path}")
                            icon_set = True
                            break
                    except Exception as e:
                        print(f"DEBUG: Error loading icon from {icon_path}: {e}")
                        continue
            
            if not icon_set:
                # Fallback: Create a simple icon from text/shape
                print("DEBUG: No icon file found, using fallback")
                from PySide6.QtGui import QPixmap, QPainter, QFont, QColor
                
                # Create a simple 64x64 icon with "Z" text
                pixmap = QPixmap(64, 64)
                pixmap.fill(QColor(50, 150, 200))  # Blue background
                
                painter = QPainter(pixmap)
                painter.setPen(QColor(255, 255, 255))  # White text
                font = QFont("Arial", 32, QFont.Bold)
                painter.setFont(font)
                painter.drawText(pixmap.rect(), Qt.AlignCenter, "Z")
                painter.end()
                
                fallback_icon = QIcon(pixmap)
                self.setWindowIcon(fallback_icon)
                
                # Mac-specific: Also set application icon
                if hasattr(QApplication, 'setWindowIcon'):
                    QApplication.instance().setWindowIcon(fallback_icon)
                
                print("DEBUG: Fallback icon created and set")
                
        except Exception as e:
            print(f"DEBUG: Error setting up window icon: {e}")

    def _init_unified_ui(self) -> None:
        """Initialize the embedded React web UI."""
        from PySide6.QtWebEngineWidgets import QWebEngineView

        central = QWidget()
        layout = QHBoxLayout(central)

        sidebar_layout = QVBoxLayout()
        for page in ["intake", "inbox", "threads"]:
            btn = QPushButton(page.capitalize())
            btn.clicked.connect(lambda _, p=page: self.load_page(p))
            sidebar_layout.addWidget(btn)
        sidebar_layout.addStretch()

        sidebar = QWidget()
        sidebar.setLayout(sidebar_layout)
        sidebar.setFixedWidth(120)
        layout.addWidget(sidebar)

        self.webview = QWebEngineView()
        layout.addWidget(self.webview, 1)
        self.setCentralWidget(central)

        if self._react_available():
            self.load_page("intake")
        else:
            self.webview.setHtml(
                "<h3>React UI not found. Please start `npm run dev` in zoros-frontend.</h3>"
            )

    def _react_available(self) -> bool:
        """Return True if the React dev server is reachable."""
        try:
            import requests

            resp = requests.get("http://localhost:3000/status", timeout=2)
            return resp.status_code == 200
        except Exception:
            return False

    def load_page(self, page: str) -> None:
        """Navigate the embedded web view to the given page."""
        from PySide6.QtCore import QUrl

        self.webview.setUrl(QUrl(f"http://localhost:3000/{page}"))

    def apply_settings(self) -> None:
        """Apply loaded settings to recorder and backend."""
        device = self.settings.get("SelectedAudioDevice")
        if device is not None:
            try:
                sd.check_input_settings(device=device)
            except Exception:
                self.show_status("Selected device not found; using default.", error=True)
                device = None
        self.recorder.device = device
        self.persistent = bool(self.settings.get("PersistentAudioStream", False))
        self.whisper_backend = self.settings.get("WhisperBackend", "StandardWhisper")
        self.whisper_model = self.settings.get("WhisperModel", "small")
        self.auto_copy = bool(self.settings.get("AutoCopy", False))
        self.expose_data = bool(self.settings.get("ExposeData", False))
        init_logging(bool(self.settings.get("DebugLog", False)))
        print(f"DEBUG: Applied settings - backend: {self.whisper_backend}, model: {self.whisper_model}")

    # ------------------- Recording -------------------
    def toggle_record(self) -> None:
        """Toggle recording with enhanced robustness and error recovery."""
        print(f"DEBUG: toggle_record() called - button text: '{self.record_btn.text()}'")
        print(f"DEBUG: Button enabled: {self.record_btn.isEnabled()}")
        print(f"DEBUG: Active threads: {threading.active_count()}")
        
        # EMERGENCY PROTECTION: Always ensure button is enabled for user interaction
        if not self.record_btn.isEnabled():
            print(f"EMERGENCY: Button was disabled - re-enabling for user interaction")
            self.record_btn.setEnabled(True)
        
        # EMERGENCY PROTECTION: Check for stuck states
        if hasattr(self, '_recording_stuck_detected') and self._recording_stuck_detected:
            print(f"EMERGENCY: Stuck state detected - forcing recovery")
            self._force_recording_recovery()
            return
        
        # Thread-safe state protection
        with getattr(self, '_recording_lock', threading.RLock()):
            if not hasattr(self, '_recording_lock'):
                self._recording_lock = threading.RLock()
            
            try:
                if "Record" in self.record_btn.text():
                    print(f"DEBUG: Starting recording...")
                    self._safe_start_record()
                else:
                    print(f"DEBUG: Stopping recording...")
                    self._safe_stop_record()
            except Exception as e:
                print(f"EMERGENCY: Error in toggle_record: {e}")
                import traceback
                traceback.print_exc()
                self._force_recording_recovery()
    
    def _force_recording_recovery(self) -> None:
        """Emergency recovery for stuck recording states."""
        print(f"EMERGENCY: Forcing recording recovery...")
        
        try:
            # Force stop all timers
            for timer_name in ['timer', 'wave_timer', 'progress_timer', 'transcription_timeout', 'pipeline_health_timer']:
                if hasattr(self, timer_name):
                    timer = getattr(self, timer_name)
                    if timer and hasattr(timer, 'stop'):
                        timer.stop()
                        print(f"EMERGENCY: Stopped {timer_name}")
            
            # Force close audio streams
            if hasattr(self, 'recorder') and self.recorder:
                try:
                    if hasattr(self.recorder, 'stream') and self.recorder.stream:
                        self.recorder.stream.abort()  # Immediate abort
                        self.recorder.stream.close()
                        self.recorder.stream = None
                        print(f"EMERGENCY: Forced stream cleanup")
                except Exception as e:
                    print(f"EMERGENCY: Error in stream cleanup: {e}")
            
            # Cancel any running futures
            if hasattr(self, 'current_future') and self.current_future:
                try:
                    self.current_future.cancel()
                    self.current_future = None
                    print(f"EMERGENCY: Cancelled running future")
                except Exception as e:
                    print(f"EMERGENCY: Error canceling future: {e}")
            
            # Force UI reset
            self.record_btn.setText("🔴 Record")
            self.record_btn.setStyleSheet("")
            self.record_btn.setEnabled(True)
            self.timer_label.hide()
            self.wave_label.hide()
            
            # Clear stuck state
            self._recording_stuck_detected = False
            
            self.show_status("Emergency recovery completed", error=False)
            print(f"EMERGENCY: Recovery completed - Active threads: {threading.active_count()}")
            
        except Exception as e:
            print(f"EMERGENCY: Error in recovery: {e}")
            self.show_status("Emergency recovery failed - please restart", error=True)
    
    def _safe_start_record(self) -> None:
        """Start recording with enhanced error handling."""
        try:
            # Pre-flight checks
            if hasattr(self, 'current_future') and self.current_future and not self.current_future.done():
                print(f"WARNING: Previous transcription still running - forcing cleanup")
                self.current_future.cancel()
                self.current_future = None
            
            # Check for leaked streams
            if hasattr(self, 'recorder') and self.recorder and hasattr(self.recorder, 'stream') and self.recorder.stream:
                if not getattr(self.recorder.stream, 'closed', True):
                    print(f"WARNING: Stream leak detected - cleaning up")
                    try:
                        self.recorder.stream.close()
                    except:
                        pass
                    self.recorder.stream = None
            
            self.start_record()
            
            # Update hotkey service state
            if hasattr(self, 'hotkey_service') and self.hotkey_service:
                self.hotkey_service.set_recording_state(True)
            
        except Exception as e:
            print(f"ERROR in _safe_start_record: {e}")
            import traceback
            traceback.print_exc()
            self._handle_recording_error(f"Failed to start recording: {e}")
    
    def _safe_stop_record(self) -> None:
        """Stop recording with enhanced error handling."""
        try:
            # Add watchdog for stuck stop operations
            self._stop_watchdog_timer = QTimer(self)
            self._stop_watchdog_timer.setSingleShot(True)
            self._stop_watchdog_timer.timeout.connect(self._handle_stop_timeout)
            self._stop_watchdog_timer.start(10000)  # 10 second timeout
            
            self.stop_record()
            
            # Update hotkey service state
            if hasattr(self, 'hotkey_service') and self.hotkey_service:
                self.hotkey_service.set_recording_state(False)
            
            # Cancel watchdog if stop completed normally
            if hasattr(self, '_stop_watchdog_timer'):
                self._stop_watchdog_timer.stop()
                
        except Exception as e:
            print(f"ERROR in _safe_stop_record: {e}")
            import traceback
            traceback.print_exc()
            self._handle_recording_error(f"Failed to stop recording: {e}")
            
            # Ensure hotkey state is reset on error
            if hasattr(self, 'hotkey_service') and self.hotkey_service:
                self.hotkey_service.set_recording_state(False)
    
    def _handle_stop_timeout(self) -> None:
        """Handle timeout during stop operation."""
        print(f"EMERGENCY: Stop operation timed out - forcing recovery")
        self._recording_stuck_detected = True
        self._force_recording_recovery()

    def toggle_model(self) -> None:
        """Load or unload the selected model."""
        if self.backend_instance is None:
            self.load_model()
        else:
            self.unload_model()

    def load_model(self) -> None:
        start = perf_counter()
        mem_before = _mem_usage_mb()
        
        # Check if we already have the same model loaded
        cache_key = f"{self.whisper_backend}_{self.whisper_model}"
        if (self.current_backend == self.whisper_backend and 
            self.current_model == self.whisper_model and 
            self.backend_instance is not None):
            print(f"DEBUG: Model {cache_key} already loaded, skipping reload")
            self.show_status(f"Model {self.whisper_backend}/{self.whisper_model} already loaded")
            return
        
        # Check cache first
        if cache_key in self.model_cache:
            print(f"DEBUG: Loading {cache_key} from cache")
            self.backend_instance = self.model_cache[cache_key]
            self.current_backend = self.whisper_backend
            self.current_model = self.whisper_model
            self.model_loaded_time = 0.0  # No time spent loading from cache
            mem_after = _mem_usage_mb()
            self.load_btn.setText("Unload Model")
            msg = f"Loaded {self.whisper_backend}/{self.whisper_model} from cache ({mem_after - mem_before:.1f} MB)"
            print(msg)
            self.show_status(msg)
            return
        
        # Load new model
        try:
            backend_class = get_backend_class(self.whisper_backend)
        except (ImportError, ValueError) as e:
            self.show_status(f"Backend unavailable: {e}", error=True)
            return
        try:
            print(f"DEBUG: Loading new model {cache_key}")
            self.backend_instance = backend_class(self.whisper_model)
            # Cache the loaded model
            self.model_cache[cache_key] = self.backend_instance
            self.current_backend = self.whisper_backend
            self.current_model = self.whisper_model
        except Exception as exc:  # pragma: no cover - backend load failures
            self.show_status(f"Load failed: {exc}", error=True)
            return
        self.model_loaded_time = perf_counter() - start
        mem_after = _mem_usage_mb()
        self.load_btn.setText("Unload Model")
        msg = (
            f"Loaded {self.whisper_backend}/{self.whisper_model} in {self.model_loaded_time:.2f}s"
            f" ({mem_after - mem_before:.1f} MB)"
        )
        print(msg)
        self.show_status(msg)

    def unload_model(self) -> None:
        start = perf_counter()
        mem_before = _mem_usage_mb()
        
        # Clear current model but keep cache
        self.backend_instance = None
        self.current_backend = None
        self.current_model = None
        
        import gc
        gc.collect()
        duration = perf_counter() - start
        mem_after = _mem_usage_mb()
        self.load_btn.setText("Load Model")
        msg = f"Unloaded current model in {duration:.2f}s ({mem_before - mem_after:.1f} MB freed) - Cache preserved"
        print(msg)
        self.show_status(msg)
    
    def _auto_preload_model(self) -> None:
        """Auto-preload the default model on startup for maximum speed."""
        if not hasattr(self, 'auto_preload_enabled'):
            self.auto_preload_enabled = True  # Can be disabled in settings
        
        if not self.auto_preload_enabled:
            return
        
        # Use QTimer to preload after UI is fully initialized
        from PySide6.QtCore import QTimer
        def preload_delayed():
            logger.info("🚀 Auto-preloading model for maximum dictation speed...")
            self.show_status("Auto-preloading model for faster dictation...")
            try:
                # First create the backend instance
                self.load_model()
                
                # For MLX Whisper, we need to actually trigger model loading
                # by doing a dummy transcription with a small audio file
                if self.backend_instance and self.whisper_backend == "MLXWhisper":
                    print("DEBUG: Triggering actual MLX model loading...")
                    self.show_status("Downloading and loading model weights...")
                    
                    # Create a tiny dummy audio file for model loading
                    import tempfile
                    import soundfile as sf
                    import numpy as np
                    
                    dummy_audio = np.zeros(16000, dtype=np.float32)  # 1 second of silence
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                        sf.write(f.name, dummy_audio, 16000)
                        dummy_path = f.name
                    
                    # Trigger model loading with dummy transcription
                    _ = self.backend_instance.transcribe(dummy_path)
                    
                    # Clean up dummy file
                    import os
                    os.unlink(dummy_path)
                    
                    print("DEBUG: MLX model fully loaded and cached")
                
                logger.info("✅ Model auto-preloading complete")
                self.show_status("Model preloaded - dictation will be faster!")
            except Exception as e:
                logger.error(f"❌ Auto-preload failed: {e}")
                self.show_status(f"Auto-preload failed: {e}", error=True)
        
        QTimer.singleShot(1000, preload_delayed)  # Delay 1 second after startup
    
    def _start_live_transcription(self) -> None:
        """Start live transcription processing during recording."""
        print(f"DEBUG: _start_live_transcription called")
        print(f"DEBUG: live_transcription_enabled: {self.live_transcription_enabled}")
        print(f"DEBUG: backend_instance: {self.backend_instance}")
        
        if not self.live_transcription_enabled:
            print("DEBUG: Live transcription disabled (keeping stable)")
            return
        
        # Only use live transcription if explicitly enabled
        # This keeps the main MLX backend stable  
        print("DEBUG: Live transcription is experimental and disabled by default")
        return
    
    def _on_live_transcript_update(self, transcript: str) -> None:
        """Handle live transcript updates from background thread."""
        # Use signal to safely update UI from main thread
        if transcript and len(transcript) > 10:
            self.live_transcript_update_signal.emit(transcript)
    
    def _handle_live_transcript_update(self, transcript: str) -> None:
        """Handle live transcript updates in the main thread (thread-safe)."""
        # Update the text area with live transcript (in a different color/style)
        current_text = self.notes.toPlainText()
        if not current_text.startswith("🎙️ LIVE: "):
            self.notes.setPlainText(f"🎙️ LIVE: {transcript}")
            logger.info(f"📝 Live update: {len(transcript)} chars")
    
    def _hook_audio_feed(self) -> None:
        """Hook into the recorder to feed audio data to live processor."""
        # Disabled for stability
        pass
    
    def _stop_live_transcription(self) -> str:
        """Stop live transcription and return final result."""
        # Disabled for stability
        return ""
    
    def clear_model_cache(self) -> None:
        """Clear the model cache to free memory."""
        start = perf_counter()
        mem_before = _mem_usage_mb()
        
        cache_size = len(self.model_cache)
        self.model_cache.clear()
        self.backend_instance = None
        self.current_backend = None
        self.current_model = None
        
        import gc
        gc.collect()
        
        duration = perf_counter() - start
        mem_after = _mem_usage_mb()
        msg = f"Cleared {cache_size} cached models in {duration:.2f}s ({mem_before - mem_after:.1f} MB freed)"
        print(msg)
        self.show_status(msg)

    def start_record(self) -> None:
        print(f"DEBUG: start_record() called")
        print(f"DEBUG: Current backend: {self.whisper_backend}")
        print(f"DEBUG: Current model: {self.whisper_model}")
        print(f"DEBUG: Recorder device: {self.recorder.device}")
        print(f"DEBUG: Persistent stream: {self.persistent}")
        
        # Resource monitoring for semaphore leak detection
        print(f"DEBUG: Active threads before recording: {threading.active_count()}")
        if hasattr(self.recorder, 'stream') and self.recorder.stream:
            print(f"DEBUG: WARNING - Stream already exists before start: {self.recorder.stream}")
        else:
            print(f"DEBUG: No existing stream - clean start")
        
        self.audio_path = None
        self.original_transcript = None
        self.elapsed = 0
        self.recording_start_time = perf_counter()
        self.pipeline_start_time = None  # Will be set when transcription starts
        self.timer_label.setText("0 s")
        self.timer_label.show()
        self.wave_label.show()
        self.timer.start()
        self.wave_timer.start()
        
        try:
            device = self.recorder.device
            print(f"DEBUG: Starting recorder with device: {device}")
            if self.persistent and self.recorder.stream:
                print(f"DEBUG: Restarting persistent stream")
                self.recorder.frames = []
                self.recorder.stream.start()  # Restart the stopped stream
            else:
                print(f"DEBUG: Starting new recorder stream")
                self.recorder.start(device)
            
            status_msg = "Recording..."
            self.show_status(status_msg)
            self.record_btn.setText("Stop")
            self.record_btn.setStyleSheet("background-color: red; color: white;")
            # CRITICAL: Always keep button enabled during recording so user can stop
            self.record_btn.setEnabled(True)
            print(f"DEBUG: Recording started successfully - button enabled for stopping")
            
            # Initialize live transcription if enabled and model is loaded
            self._start_live_transcription()
        except Exception as e:
            print(f"DEBUG: Error starting recording: {e}")
            import traceback
            traceback.print_exc()
            self.show_status("No microphone detected", error=True)
            # Reset button to record state on error, but keep enabled
            self.record_btn.setText("Record")
            self.record_btn.setStyleSheet("")
            self.record_btn.setEnabled(True)
            print(f"DEBUG: Recording error - button reset to enabled Record state")

    def stop_record(self) -> None:
        """Stop recording and start transcription process.
        
        This method handles the transition from recording to transcription,
        including error recovery and state management.
        
        Spec: docs/requirements/dictation_requirements.md#ui-workflow
        Tests: tests/test_intake_pipeline.py#test_recording_simulation
        Integration: source/interfaces/intake/main.py#_finish_transcription
        """
        print(f"DEBUG: stop_record() called - current button text: {self.record_btn.text()}")
        print(f"DEBUG: Active threads before stop: {threading.active_count()}")
        print(f"DEBUG: Current thread: {threading.current_thread().name}")
        
        # Monitor stream state for leak detection
        if hasattr(self.recorder, 'stream') and self.recorder.stream:
            print(f"DEBUG: Stream exists: {self.recorder.stream}, active: {getattr(self.recorder.stream, 'active', 'unknown')}")
            print(f"DEBUG: Stream closed: {getattr(self.recorder.stream, 'closed', 'unknown')}")
        else:
            print(f"DEBUG: No stream to stop")
        
        # Check for existing transcription processes
        if hasattr(self, 'current_future') and self.current_future:
            print(f"DEBUG: WARNING - Current future still exists: {self.current_future}")
            print(f"DEBUG: Future done: {self.current_future.done()}")
            if self.current_future.done():
                print(f"DEBUG: Future cancelled: {self.current_future.cancelled()}")
        
        # Check for existing timers
        if hasattr(self, 'transcription_timeout') and self.transcription_timeout:
            print(f"DEBUG: Existing transcription timeout timer: {self.transcription_timeout.isActive()}")
        if hasattr(self, 'progress_timer') and self.progress_timer:
            print(f"DEBUG: Existing progress timer: {self.progress_timer.isActive()}")
        try:
            # Stop timers and hide UI elements
            self.timer.stop()
            self.wave_timer.stop()
            self.timer_label.hide()
            self.wave_label.hide()
            
            # Calculate recording duration
            recording_duration = perf_counter() - getattr(self, 'recording_start_time', 0.0)
            print(f"DEBUG: Recording duration: {recording_duration:.2f} seconds")
            
            # Create temporary audio file
            tmp = Path(tempfile.gettempdir()) / f"tmp_{uuid.uuid4()}.wav"
            print(f"DEBUG: Creating temp audio file: {tmp}")
            
            # Stop recording and save audio
            try:
                print(f"DEBUG: Calling recorder.stop() with keep_stream={self.persistent}")
                self.recorder.stop(tmp, keep_stream=self.persistent)
                print(f"DEBUG: Recorder stopped successfully")
                
                # Force verify stream is actually closed
                if hasattr(self.recorder, 'stream') and self.recorder.stream:
                    print(f"DEBUG: WARNING - Stream still exists after stop: {self.recorder.stream}")
                    print(f"DEBUG: Stream active: {getattr(self.recorder.stream, 'active', 'unknown')}")
                    print(f"DEBUG: Stream closed: {getattr(self.recorder.stream, 'closed', 'unknown')}")
                    
                    # Force cleanup if stream is still active
                    if not getattr(self.recorder.stream, 'closed', False):
                        print(f"DEBUG: FORCING stream cleanup")
                        try:
                            self.recorder.stream.close()
                            self.recorder.stream = None
                            print(f"DEBUG: Forced stream cleanup completed")
                        except Exception as cleanup_error:
                            print(f"DEBUG: Error in forced stream cleanup: {cleanup_error}")
                else:
                    print(f"DEBUG: Stream properly cleaned up")
                    
            except Exception as e:
                print(f"DEBUG: Error stopping recorder: {e}")
                import traceback
                traceback.print_exc()
                self._handle_recording_error("Failed to stop recording")
                return
            
            # Verify audio file was created
            self.audio_path = tmp if tmp.exists() else None
            if not self.audio_path:
                print(f"DEBUG: Audio file not created: {tmp}")
                self._handle_recording_error("No audio file created")
                return
            
            print(f"DEBUG: Audio file created: {self.audio_path} (size: {self.audio_path.stat().st_size} bytes)")
            
            # Try to get live transcription result first
            live_transcript = self._stop_live_transcription()
            
            # Start transcription process
            if self.audio_path:
                if live_transcript and len(live_transcript.strip()) > 10:
                    # We have a good live transcript, use it directly
                    logger.info(f"🚀 Using live transcript ({len(live_transcript)} chars)")
                    self.show_status("Using live transcription result...")
                    
                    # Use live result directly
                    pipeline_end_time = perf_counter()
                    pipeline_total_time = pipeline_end_time - self.recording_start_time
                    
                    # Process live result as final transcript
                    self._finish_transcription(live_transcript, use_live_result=True, 
                                             pipeline_time=pipeline_total_time)
                    return
                else:
                    # Fallback to traditional transcription
                    logger.info("📝 Falling back to traditional transcription")
                    self.show_status(f"Transcription in Progress... (Backend: {self.whisper_backend}, Model: {self.whisper_model})")
                print(f"DEBUG: Starting transcription with {self.whisper_backend} and model {self.whisper_model}")
                print(f"DEBUG: Audio file: {self.audio_path} (size: {self.audio_path.stat().st_size} bytes)")
                print(f"DEBUG: Recording duration: {recording_duration:.2f} seconds")
                
                # Start a progress timer to show the transcription is still working
                self.progress_timer = QTimer(self)
                self.progress_timer.setInterval(2000)  # Update every 2 seconds
                self.progress_dots = 0
                self.progress_timer.timeout.connect(self._update_progress)
                self.progress_timer.start()
                
                # CRITICAL: Add timeout for long transcriptions to prevent hanging
                self.transcription_timeout = QTimer(self)
                self.transcription_timeout.setSingleShot(True)
                # Scale timeout based on recording duration (minimum 30s, max 300s)
                timeout_ms = max(30000, min(300000, int(recording_duration * 10000)))
                self.transcription_timeout.setInterval(timeout_ms)
                self.transcription_timeout.timeout.connect(self._handle_transcription_timeout)
                self.transcription_timeout.start()
                print(f"DEBUG: Set transcription timeout to {timeout_ms/1000:.1f}s for {recording_duration:.1f}s recording")
                
                self.transcribe_start = perf_counter()
                self.pipeline_start_time = self.transcribe_start  # Mark pipeline start
                print(f"DEBUG: Pipeline start time: {self.pipeline_start_time}")
                
                if self.backend_instance is not None:
                    def _run(path: str) -> str:
                        print(f"DEBUG: Starting transcription in thread with backend instance")
                        transcription_start = perf_counter()
                        try:
                            # Type check to ensure backend_instance has transcribe method
                            if hasattr(self.backend_instance, 'transcribe'):
                                result = self.backend_instance.transcribe(path)
                                transcription_end = perf_counter()
                                transcription_duration = transcription_end - transcription_start
                                print(f"DEBUG: Transcription completed in thread: {result[:100]}...")
                                print(f"DEBUG: Pure transcription time: {transcription_duration:.2f}s")
                                return result
                            else:
                                raise AttributeError("Backend instance does not have transcribe method")
                        except Exception as e:
                            print(f"DEBUG: Transcription failed in thread: {e}")
                            import traceback
                            traceback.print_exc()
                            return ""

                    self.current_future = self.executor.submit(_run, str(self.audio_path))
                    future = self.current_future
                else:
                    def _run_fallback(path: str) -> str:
                        print(f"DEBUG: Starting fallback transcription in thread")
                        transcription_start = perf_counter()
                        try:
                            result = transcribe_audio(path, self.whisper_backend, self.whisper_model)
                            transcription_end = perf_counter()
                            transcription_duration = transcription_end - transcription_start
                            print(f"DEBUG: Fallback transcription completed: {result[:100]}...")
                            print(f"DEBUG: Pure transcription time: {transcription_duration:.2f}s")
                            return result
                        except Exception as e:
                            print(f"DEBUG: Fallback transcription failed: {e}")
                            import traceback
                            traceback.print_exc()
                            return ""
                    
                    self.current_future = self.executor.submit(_run_fallback, str(self.audio_path))
                    future = self.current_future
                
                def _callback_wrapper(future_result):
                    print(f"DEBUG: Future callback triggered - Thread: {threading.current_thread().name}")
                    print(f"DEBUG: Future callback - Active threads: {threading.active_count()}")
                    
                    # Emit signal to stop timeout timer from main thread
                    print(f"DEBUG: Emitting stop_timeout_signal")
                    self.stop_timeout_signal.emit()
                    print(f"DEBUG: stop_timeout_signal emitted")
                    
                    try:
                        print(f"DEBUG: Getting future result...")
                        result = future_result.result(timeout=5)  # Short timeout since we already have the result
                        print(f"DEBUG: Future result: {result[:100]}...")
                        print(f"DEBUG: Future result length: {len(result)} chars")
                        print(f"DEBUG: Emitting finish_transcription_signal")
                        self.finish_transcription_signal.emit(result)
                        print(f"DEBUG: finish_transcription_signal emitted successfully")
                    except Exception as e:
                        print(f"DEBUG: Future callback error: {e}")
                        import traceback
                        traceback.print_exc()
                        print(f"DEBUG: Emitting finish_transcription_signal with empty result")
                        self.finish_transcription_signal.emit("")
                        print(f"DEBUG: finish_transcription_signal emitted for error case")
                    finally:
                        # Clear the future reference to prevent resource leaks
                        self.current_future = None
                        print(f"DEBUG: Cleared current_future reference")
                        print(f"DEBUG: Future callback completed - Thread: {threading.current_thread().name}")
                
                future.add_done_callback(_callback_wrapper)
                print(f"DEBUG: Added done callback to future")
                
                # Add a timeout timer as backup
                self.transcription_timeout = QTimer(self)
                self.transcription_timeout.setSingleShot(True)
                self.transcription_timeout.setInterval(30000)  # 30 seconds
                self.transcription_timeout.timeout.connect(lambda: self._handle_transcription_timeout())
                self.transcription_timeout.start()
                print(f"DEBUG: Started transcription timeout timer (30s)")
                
                # Add a pipeline health check to detect if the pipeline stalls
                self.pipeline_health_timer = QTimer(self)
                self.pipeline_health_timer.setSingleShot(True)
                self.pipeline_health_timer.setInterval(60000)  # 60 seconds - longer than transcription timeout
                self.pipeline_health_timer.timeout.connect(lambda: self._handle_pipeline_stall())
                self.pipeline_health_timer.start()
                print(f"DEBUG: Started pipeline health timer (60s)")
            else:
                self.status.clearMessage()
                
        except Exception as e:
            print(f"DEBUG: Unexpected error in stop_record: {e}")
            import traceback
            traceback.print_exc()
            self._handle_recording_error(f"Unexpected error: {e}")
        finally:
            # Always reset the record button UI
            self.record_btn.setText("Record")
            self.record_btn.setStyleSheet("")
            self.record_btn.setEnabled(True)

    def _update_timer(self) -> None:
        self.elapsed += 1
        self.timer_label.setText(f"{self.elapsed} s")

    def _update_wave(self) -> None:
        bars = int(min(self.recorder.level * 20, 20))
        self.wave_label.setText("█" * bars)

    def _update_progress(self) -> None:
        """Update the progress indicator during transcription."""
        self.progress_dots = (self.progress_dots + 1) % 4
        dots = "." * self.progress_dots
        
        # Enhanced progress with elapsed time
        elapsed = perf_counter() - getattr(self, 'transcribe_start', perf_counter())
        self.show_status(f"Transcription in Progress{dots} ({elapsed:.1f}s elapsed - {self.whisper_backend})")
    
    def _handle_transcription_timeout(self) -> None:
        """Handle transcription timeout to prevent hanging."""
        print(f"DEBUG: Transcription timeout triggered!")
        
        # Cancel the current transcription future
        if hasattr(self, 'current_future') and self.current_future:
            print(f"DEBUG: Cancelling transcription future")
            self.current_future.cancel()
            self.current_future = None
        
        # Stop progress timers
        if hasattr(self, 'progress_timer'):
            self.progress_timer.stop()
        if hasattr(self, 'transcription_timeout'):
            self.transcription_timeout.stop()
        
        # Reset UI state
        self.record_btn.setText("🔴 Record")
        self.record_btn.setStyleSheet("")
        self.record_btn.setEnabled(True)
        
        # Show timeout error with recovery options
        error_msg = "Transcription timed out. Audio saved for recovery."
        self.show_status(error_msg, error=True)
        
        # Save the audio file to a recovery location
        if hasattr(self, 'audio_path') and self.audio_path and self.audio_path.exists():
            recovery_dir = Path.home() / ".zoros" / "recovery"
            recovery_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            recovery_path = recovery_dir / f"timeout_recovery_{timestamp}.wav"
            
            try:
                shutil.copy2(self.audio_path, recovery_path)
                print(f"DEBUG: Audio saved to recovery location: {recovery_path}")
                self.show_status(f"Timeout - Audio saved: {recovery_path.name}")
                
                # Add to recovery tracking
                recovery_info = {
                    "timestamp": timestamp,
                    "original_duration": getattr(self, 'recording_duration', 0),
                    "backend": self.whisper_backend,
                    "model": self.whisper_model,
                    "file_path": str(recovery_path),
                    "reason": "transcription_timeout"
                }
                
                recovery_log = recovery_dir / "recovery_log.json"
                if recovery_log.exists():
                    with open(recovery_log, 'r') as f:
                        log_data = json.load(f)
                else:
                    log_data = []
                
                log_data.append(recovery_info)
                with open(recovery_log, 'w') as f:
                    json.dump(log_data, f, indent=2)
                
            except Exception as e:
                print(f"DEBUG: Error saving recovery file: {e}")
        
        # Clean up temp file
        if hasattr(self, 'audio_path') and self.audio_path and self.audio_path.exists():
            try:
                self.audio_path.unlink()
            except:
                pass
        
        self.audio_path = None

    def _stop_timeout_timer(self) -> None:
        """Stop the transcription timeout timer from main thread."""
        if hasattr(self, 'transcription_timeout'):
            self.transcription_timeout.stop()
            print(f"DEBUG: Stopped transcription timeout timer from main thread")
    
    def _handle_pipeline_stall(self) -> None:
        """Handle pipeline stall by forcing cleanup and reset."""
        print(f"DEBUG: Pipeline stall detected - forcing recovery!")
        print(f"DEBUG: Active threads: {threading.active_count()}")
        
        # Check if we still have a future running
        if hasattr(self, 'current_future') and self.current_future:
            print(f"DEBUG: Current future still exists - canceling...")
            try:
                self.current_future.cancel()
                print(f"DEBUG: Future cancelled during pipeline stall")
            except Exception as e:
                print(f"DEBUG: Error canceling future during stall: {e}")
        
        # Force UI reset
        self.show_status("Pipeline recovered", error=False)
        self.record_btn.setText("Record")
        self.record_btn.setStyleSheet("")
        self.record_btn.setEnabled(True)
        
        # Force cleanup of all resources
        self._cleanup_transcription_resources()
        
        print(f"DEBUG: Pipeline stall recovery completed")
    
    def _cleanup_transcription_resources(self) -> None:
        """Clean up all transcription-related resources."""
        print(f"DEBUG: Cleaning up transcription resources...")
        
        # Clear future references
        if hasattr(self, 'current_future'):
            self.current_future = None
            print(f"DEBUG: Cleared current_future")
        
        # Stop all timers
        if hasattr(self, 'progress_timer') and self.progress_timer:
            self.progress_timer.stop()
            print(f"DEBUG: Stopped progress timer")
        
        if hasattr(self, 'transcription_timeout') and self.transcription_timeout:
            self.transcription_timeout.stop()
            print(f"DEBUG: Stopped transcription timeout")
        
        if hasattr(self, 'pipeline_health_timer') and self.pipeline_health_timer:
            self.pipeline_health_timer.stop()
            print(f"DEBUG: Stopped pipeline health timer")
        
        # Clean up temp audio file
        if hasattr(self, 'audio_path') and self.audio_path and self.audio_path.exists():
            try:
                self.audio_path.unlink()
                print(f"DEBUG: Cleaned up temp audio file")
            except Exception as e:
                print(f"DEBUG: Error cleaning up temp audio file: {e}")
        
        self.audio_path = None
        print(f"DEBUG: Resource cleanup completed")

    def _handle_transcription_timeout(self) -> None:
        """Handle transcription timeout."""
        print("DEBUG: Transcription timeout occurred")
        
        # Cancel the current future if it exists
        if hasattr(self, 'current_future') and self.current_future:
            print("DEBUG: Cancelling timed out transcription future")
            self.current_future.cancel()
            self.current_future = None
        
        if hasattr(self, 'progress_timer'):
            self.progress_timer.stop()
        
        self.show_status("Transcription timed out. Please try again.", error=True)
        self.audio_path = None
        
        # Reset button state
        self.record_btn.setText("Record")
        self.record_btn.setStyleSheet("")
        self.record_btn.setEnabled(True)

    def save_settings(self) -> None:
        self.settings["WhisperBackend"] = self.backend_combo.currentText()
        self.settings["WhisperModel"] = self.model_combo.currentText()
        # Note: autocopy_cb is not defined in this simplified settings panel
        # self.settings["AutoCopy"] = self.autocopy_cb.isChecked()
        save_settings(self.settings)
        self.settings_panel.hide()

    def toggle_settings(self) -> None:
        if self.settings_panel.isVisible():
            self.settings_panel.hide()
        else:
            self.settings_panel.show()
    def show_audio_test_panel(self) -> None:
        """Show the audio test panel for managing test files."""
        try:
            from .audio_test_panel import AudioTestPanel
            if not hasattr(self, 'audio_test_panel') or not self.audio_test_panel:
                self.audio_test_panel = AudioTestPanel()
            self.audio_test_panel.show()
            self.audio_test_panel.raise_()
            self.audio_test_panel.activateWindow()
            self.show_status("Audio Test Panel opened")
        except Exception as e:
            logger.error(f"Error opening audio test panel: {e}")
            self.show_status("Error opening audio test panel", error=True)

    def show_settings(self) -> None:
        dlg = SettingsDialog(self.settings, self.available_backends, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.settings = dlg.get_values()
            save_settings(self.settings)
            self.apply_settings()
            self.show_status("Settings Saved")

    def show_status(self, text: str, error: bool = False) -> None:
        """Display a status message for 5 seconds."""
        self.status.setStyleSheet("color: red;" if error else "")
        self.status.showMessage(text, 5000)
        self.clear_timer.start(5000)

    def copy_to_clipboard(self) -> None:
        text = self.notes.toPlainText()
        if text:
            self.clipboard.setText(text)
            self.show_status("Copied to clipboard")
    
    def open_dictation_library(self) -> None:
        """Open the dictation library window."""
        try:
            from .dictation_library import DictationLibraryWindow
            self.library_window = DictationLibraryWindow()
            self.library_window.show()
            self.show_status("Dictation Library opened")
        except Exception as e:
            logger.error(f"Error opening dictation library: {e}")
            self.show_status("Error opening dictation library", error=True)
    
    def open_fiberizer(self) -> None:
        """Open the fiberizer/language model playground window."""
        try:
            # Show dialog to choose between fiberizer and playground
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
            
            dialog = QDialog(self)
            dialog.setWindowTitle("Choose Interface")
            layout = QVBoxLayout(dialog)
            
            layout.addWidget(QLabel("Select the interface to open:"))
            
            btn_layout = QHBoxLayout()
            
            playground_btn = QPushButton("🧬 Language Playground")
            fiberizer_btn = QPushButton("📋 Fiberizer Review")
            cancel_btn = QPushButton("Cancel")
            
            btn_layout.addWidget(playground_btn)
            btn_layout.addWidget(fiberizer_btn)
            btn_layout.addWidget(cancel_btn)
            layout.addLayout(btn_layout)
            
            def open_playground():
                dialog.accept()
                self._launch_playground()
            
            def open_fiberizer():
                dialog.accept()
                self._launch_fiberizer()
            
            playground_btn.clicked.connect(open_playground)
            fiberizer_btn.clicked.connect(open_fiberizer)
            cancel_btn.clicked.connect(dialog.reject)
            
            dialog.exec()
            
        except Exception as e:
            logger.error(f"Error opening fiberizer dialog: {e}")
            self.show_status("Error opening fiberizer", error=True)
    
    def _launch_playground(self) -> None:
        """Launch the language model playground."""
        try:
            import subprocess
            import sys
            
            # Check if there's content to pass
            content = self.notes.toPlainText().strip()
            if content:
                # Save content to temp file
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                    f.write(content)
                    temp_path = f.name
                
                # Launch playground (it can detect and offer to import the temp file)
                subprocess.Popen([
                    sys.executable, "-m", "streamlit", "run", 
                    "source/interfaces/streamlit/language_playground.py"
                ])
                self.show_status(f"Language Playground launched (content ready for import)")
            else:
                # Launch empty playground
                subprocess.Popen([
                    sys.executable, "-m", "streamlit", "run", 
                    "source/interfaces/streamlit/language_playground.py"
                ])
                self.show_status("Language Playground launched")
        except Exception as e:
            logger.error(f"Error launching playground: {e}")
            self.show_status("Error launching playground", error=True)
    
    def _launch_fiberizer(self) -> None:
        """Launch the fiberizer review interface."""
        try:
            import subprocess
            import sys
            
            content = self.notes.toPlainText().strip()
            if content:
                # Save content to temp file for fiberizer
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                    f.write(content)
                    temp_path = f.name
                
                # Launch improved fiberizer interface
                subprocess.Popen([
                    sys.executable, "-m", "streamlit", "run", 
                    "source/interfaces/streamlit/fiberizer_review_improved.py"
                ])
                self.show_status("Fiberizer launched with current content")
            else:
                # Launch empty improved fiberizer
                subprocess.Popen([
                    sys.executable, "-m", "streamlit", "run", 
                    "source/interfaces/streamlit/fiberizer_review_improved.py"
                ])
                self.show_status("Fiberizer Review launched")
        except Exception as e:
            logger.error(f"Error launching fiberizer: {e}")
            self.show_status("Error launching fiberizer", error=True)
    
    def show_window_manager(self) -> None:
        """Show the window manager interface."""
        try:
            from ..window_manager import get_window_manager
            manager = get_window_manager()
            
            # Show window list
            windows = manager.get_window_list()
            if windows:
                window_list = "\n".join([f"• {title} ({wtype})" for wid, wtype, title in windows])
                QMessageBox.information(self, "ZorOS Windows", 
                                      f"Active ZorOS Windows:\n\n{window_list}")
            else:
                QMessageBox.information(self, "ZorOS Windows", 
                                      "No active ZorOS windows found.")
            
            self.show_status("Window Manager opened")
        except Exception as e:
            logger.error(f"Error opening window manager: {e}")
            self.show_status("Error opening window manager", error=True)
    
    def toggle_always_on_top(self) -> None:
        """Toggle the always-on-top window flag."""
        try:
            current_flags = self.windowFlags()
            
            if self.always_on_top_btn.isChecked():
                # Enable always-on-top
                new_flags = current_flags | Qt.WindowType.WindowStaysOnTopHint
                self.always_on_top_btn.setText("📌 Always On Top")
                self.show_status("Window set to always stay on top")
            else:
                # Disable always-on-top
                new_flags = current_flags & ~Qt.WindowType.WindowStaysOnTopHint
                self.always_on_top_btn.setText("📌 Normal")
                self.show_status("Window no longer stays on top")
            
            # Apply the new flags
            self.setWindowFlags(new_flags)
            self.show()  # Required to apply flag changes
            
        except Exception as e:
            logger.error(f"Error toggling always on top: {e}")
            self.show_status("Error changing window mode", error=True)
    
    def hide_window(self) -> None:
        """Hide the window and show a system tray notification if possible."""
        try:
            from PySide6.QtWidgets import QSystemTrayIcon
            from PySide6.QtGui import QIcon
            
            # Check if system tray is available
            if QSystemTrayIcon.isSystemTrayAvailable():
                # Create system tray icon if it doesn't exist
                if not hasattr(self, 'tray_icon'):
                    self.tray_icon = QSystemTrayIcon(self)
                    
                    # Set icon
                    icon_path = Path(__file__).resolve().parents[3] / "assets" / "icon.png"
                    if icon_path.exists():
                        self.tray_icon.setIcon(QIcon(str(icon_path)))
                    else:
                        # Fallback to a simple icon
                        self.tray_icon.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))
                    
                    self.tray_icon.setToolTip("ZorOS Intake - Click to restore")
                    self.tray_icon.activated.connect(self.restore_from_tray)
                
                # Show tray icon and hide window
                self.tray_icon.show()
                self.tray_icon.showMessage(
                    "ZorOS Intake", 
                    "Window hidden to system tray. Click the tray icon to restore.",
                    QSystemTrayIcon.MessageIcon.Information,
                    3000
                )
                self.hide()
                
            else:
                # No system tray available - just minimize
                self.showMinimized()
                self.show_status("Window minimized (no system tray available)")
                
        except Exception as e:
            logger.error(f"Error hiding window: {e}")
            # Fallback to simple minimize
            self.showMinimized()
            self.show_status("Window minimized")
    
    def restore_from_tray(self, reason) -> None:
        """Restore window from system tray."""
        try:
            from PySide6.QtWidgets import QSystemTrayIcon
            
            if reason == QSystemTrayIcon.ActivationReason.Trigger:
                # Show and raise the window
                self.show()
                self.raise_()
                self.activateWindow()
                
                # Hide the tray icon
                if hasattr(self, 'tray_icon'):
                    self.tray_icon.hide()
                
                self.show_status("Window restored from system tray")
                
        except Exception as e:
            logger.error(f"Error restoring from tray: {e}")
            # Fallback - just show the window
            self.show()
            self.raise_()
            self.activateWindow()

    # ------------------- Navigation Controls -------------------
    def load_intake_records(self) -> List[Dict[str, Any]]:
        """Load intake records from database for navigation."""
        try:
            _ensure_db(self.db_path)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT id, timestamp, content, audio_path, correction, fiber_type, submitted
                    FROM intake 
                    ORDER BY timestamp DESC
                """)
                
                records = []
                for row in cursor.fetchall():
                    records.append({
                        "id": row[0],
                        "timestamp": row[1],
                        "content": row[2],
                        "audio_path": row[3],
                        "correction": row[4],
                        "fiber_type": row[5] or "dictation",
                        "submitted": bool(row[6])
                    })
                
                return records
                
        except Exception as e:
            logger.error(f"Error loading intake records: {e}")
            self.show_status("Error loading records", error=True)
            return []
    
    def refresh_records(self) -> None:
        """Refresh the list of intake records and update navigation."""
        try:
            self.intake_records = self.load_intake_records()
            self.update_navigation_ui()
            self.show_status(f"Loaded {len(self.intake_records)} records")
        except Exception as e:
            logger.error(f"Error refreshing records: {e}")
            self.show_status("Error refreshing records", error=True)
    
    def update_navigation_ui(self) -> None:
        """Update navigation UI elements based on current state."""
        try:
            if not self.intake_records:
                self.record_counter.setText("No records")
                self.prev_btn.setEnabled(False)
                self.next_btn.setEnabled(False)
                return
            
            # Update counter
            if self.current_record_index >= 0:
                current_num = self.current_record_index + 1
                total_num = len(self.intake_records)
                self.record_counter.setText(f"{current_num} of {total_num}")
            else:
                self.record_counter.setText(f"0 of {len(self.intake_records)}")
            
            # Update button states
            self.prev_btn.setEnabled(self.current_record_index > 0)
            self.next_btn.setEnabled(self.current_record_index < len(self.intake_records) - 1)
            
        except Exception as e:
            logger.error(f"Error updating navigation UI: {e}")
    
    def load_previous_record(self) -> None:
        """Load the previous intake record."""
        try:
            if not self.intake_records:
                self.refresh_records()
                return
            
            if self.current_record_index > 0:
                self.current_record_index -= 1
                self.load_current_record()
            
        except Exception as e:
            logger.error(f"Error loading previous record: {e}")
            self.show_status("Error loading previous record", error=True)
    
    def load_next_record(self) -> None:
        """Load the next intake record."""
        try:
            if not self.intake_records:
                self.refresh_records()
                return
            
            if self.current_record_index < len(self.intake_records) - 1:
                self.current_record_index += 1
                self.load_current_record()
            
        except Exception as e:
            logger.error(f"Error loading next record: {e}")
            self.show_status("Error loading next record", error=True)
    
    def load_current_record(self) -> None:
        """Load the current record into the text area."""
        try:
            if (self.current_record_index < 0 or 
                self.current_record_index >= len(self.intake_records)):
                return
            
            record = self.intake_records[self.current_record_index]
            
            # Load content into text area
            content = record.get("correction") or record.get("content", "")
            self.notes.setPlainText(content)
            
            # Update current fiber ID for potential re-submission
            self.current_fiber_id = record["id"]
            
            # Update navigation UI
            self.update_navigation_ui()
            
            # Show record info in status
            timestamp = record["timestamp"][:19] if record["timestamp"] else "unknown"
            status_icon = "✅" if record["submitted"] else "📝"
            audio_icon = "🎵" if record["audio_path"] else ""
            self.show_status(f"{status_icon} {audio_icon} {record['fiber_type']} - {timestamp}")
            
        except Exception as e:
            logger.error(f"Error loading current record: {e}")
            self.show_status("Error loading record", error=True)

    # ------------------- Submission -------------------
    def on_submit(self) -> None:
        notes = self.notes.toPlainText().strip()
        if not notes:
            return
        try:
            if hasattr(self, "original_transcript") and self.original_transcript is not None:
                # Check if we have an unsubmitted dictation to update
                if hasattr(self, "current_fiber_id") and self.current_fiber_id:
                    # Update existing unsubmitted dictation
                    with sqlite3.connect(self.db_path) as conn:
                        conn.execute(
                            "UPDATE intake SET content = ?, correction = ?, submitted = 1 WHERE id = ?",
                            (notes, notes, self.current_fiber_id)
                        )
                        conn.commit()
                    fid = self.current_fiber_id
                    self.current_fiber_id = None
                else:
                    # Create new dictation
                    if notes == self.original_transcript:
                        fid = insert_intake(
                            notes,
                            str(self.audio_path) if self.audio_path else None,
                            correction=notes,
                            fiber_type="dictation",
                            db=self.db_path,
                            submitted=True,
                        )
                    else:
                        fid = insert_intake(
                            self.original_transcript,
                            str(self.audio_path) if self.audio_path else None,
                            correction=notes,
                            fiber_type="dictation",
                            db=self.db_path,
                            submitted=True,
                        )
                self.original_transcript = None
                if self.audio_path:
                    Path(self.audio_path).unlink(missing_ok=True)
                    self.audio_path = None
            else:
                fid = insert_intake(notes, None, fiber_type="free_text", db=self.db_path, submitted=True)
            self.notes.clear()
            path = f"{self.db_path}#{fid}"
            logger.info("DictationFiber saved at %s", path)
            self.show_status(f"Saved to {path}")
            if self.auto_copy:
                self.clipboard.setText(notes)
        except Exception as exc:
            logger.error("Failed to save DictationFiber: %s", exc)
            self.show_status("Error saving. Please try again.", error=True)

    def _finish_transcription(self, transcript: str, use_live_result: bool = False, pipeline_time: Optional[float] = None) -> None:
        print(f"DEBUG: _finish_transcription called with transcript: {transcript[:100]}...")
        print(f"DEBUG: _finish_transcription - Thread: {threading.current_thread().name}")
        print(f"DEBUG: _finish_transcription - Active threads: {threading.active_count()}")
        print(f"DEBUG: _finish_transcription - use_live_result: {use_live_result}")
        print(f"DEBUG: _finish_transcription - pipeline_time: {pipeline_time}")
        
        # Stop the progress timer and timeout timer
        print(f"DEBUG: Stopping progress timer...")
        if hasattr(self, 'progress_timer'):
            self.progress_timer.stop()
            print(f"DEBUG: Progress timer stopped")
        else:
            print(f"DEBUG: No progress timer to stop")
        print(f"DEBUG: Stopping transcription timeout timer...")
        if hasattr(self, 'transcription_timeout'):
            self.transcription_timeout.stop()
            print(f"DEBUG: Transcription timeout timer stopped")
        else:
            print(f"DEBUG: No transcription timeout timer to stop")
        print(f"DEBUG: Stopping pipeline health timer...")
        if hasattr(self, 'pipeline_health_timer'):
            self.pipeline_health_timer.stop()
            print(f"DEBUG: Pipeline health timer stopped")
        else:
            print(f"DEBUG: No pipeline health timer to stop")

        # Calculate all timing metrics
        pipeline_end_time = perf_counter()
        
        if use_live_result and pipeline_time:
            # Use provided pipeline time for live results
            pipeline_total_time = pipeline_time
            recording_duration = pipeline_time  # For live, recording and processing overlap
            print(f"DEBUG: Using live result timing - pipeline time: {pipeline_time:.2f}s")
        else:
            # Calculate traditional timing
            pipeline_start = getattr(self, 'pipeline_start_time', pipeline_end_time)
            recording_start = getattr(self, 'recording_start_time', pipeline_end_time)
            
            pipeline_total_time = pipeline_end_time - pipeline_start if pipeline_start else 0.0
            recording_duration = pipeline_start - recording_start if pipeline_start and recording_start else 0.0
        
        print(f"DEBUG: Transcription finished, result: {transcript[:100]}...")
        print(f"DEBUG: Recording duration: {recording_duration:.2f} seconds")
        print(f"DEBUG: Pipeline total time: {pipeline_total_time:.2f} seconds")
        
        # Calculate ratio
        if recording_duration > 0:
            ratio = pipeline_total_time / recording_duration
            print(f"DEBUG: Pipeline/Recording ratio: {ratio:.2f}x")
        else:
            ratio = 0.0
            print(f"DEBUG: Pipeline/Recording ratio: N/A (no recording time)")
        
        print(f"DEBUG: Processing audio file...")
        temp = Path(self.audio_path) if self.audio_path else None
        print(f"DEBUG: Temp audio path: {temp}")
        fiber_id = str(uuid.uuid4())
        print(f"DEBUG: Generated fiber_id: {fiber_id}")
        final_path: Path | None = None
        if temp and temp.exists():
            print(f"DEBUG: Creating AUDIO_DIR...")
            AUDIO_DIR.mkdir(parents=True, exist_ok=True)
            final_path = AUDIO_DIR / f"{fiber_id}.wav"
            print(f"DEBUG: Final path will be: {final_path}")
            try:
                print(f"DEBUG: Moving temp file to final location...")
                temp.replace(final_path)
                print(f"DEBUG: File moved successfully")
            except Exception as e:
                print(f"DEBUG: Error moving file: {e}")
                final_path = temp

        path = str(final_path) if final_path and final_path.exists() else None
        print(f"DEBUG: Audio path for database: {path}")
        exposed_audio: Path | None = None
        if self.expose_data and final_path and final_path.exists():
            print(f"DEBUG: Creating exposed audio directory...")
            exposed_audio = DICTATIONS_DIR / fiber_id / "audio.wav"
            exposed_audio.parent.mkdir(parents=True, exist_ok=True)
            try:
                print(f"DEBUG: Copying to exposed location...")
                shutil.copy(final_path, exposed_audio)
                print(f"DEBUG: Exposed audio copied successfully")
            except Exception as e:
                print(f"DEBUG: Error copying to exposed location: {e}")
                exposed_audio = None

        print(f"DEBUG: Checking if transcript exists...")
        if transcript:
            print(f"DEBUG: Transcript exists, processing...")
            try:
                print(f"DEBUG: Inserting into database...")
                insert_intake(
                    transcript,
                    str(exposed_audio) if exposed_audio else path,
                    correction=transcript,
                    fiber_type="dictation",
                    db=self.db_path,
                    fiber_id=fiber_id,
                    submitted=False,  # Start as unsubmitted, will be marked submitted when user clicks submit
                )
                print(f"DEBUG: Database insertion successful")
                full_path = f"{self.db_path}#{fiber_id}"
                logger.info("DictationFiber saved at %s", full_path)
                print(f"DEBUG: Full path: {full_path}")
                
                # Store the fiber_id for later submission
                self.current_fiber_id = fiber_id
                print(f"DEBUG: Stored current_fiber_id: {fiber_id}")
                
                # Set the transcript in the text field
                print(f"DEBUG: Setting transcript in text field...")
                self.notes.setPlainText(transcript)
                print(f"DEBUG: Text field updated")
                self.original_transcript = transcript
                print(f"DEBUG: Original transcript set")
                
                if self.auto_copy:
                    print(f"DEBUG: Auto-copying to clipboard...")
                    self.clipboard.setText(transcript)
                    print(f"DEBUG: Clipboard updated")
                    self.show_status(
                        f"Recording: {recording_duration:.1f}s | Pipeline: {pipeline_total_time:.1f}s | Ratio: {ratio:.1f}x | Copied"
                    )
                else:
                    print(f"DEBUG: Showing completion status...")
                    self.show_status(
                        f"Recording: {recording_duration:.1f}s | Pipeline: {pipeline_total_time:.1f}s | Ratio: {ratio:.1f}x"
                    )
                print(f"DEBUG: Status message shown")
                
                if self.expose_data and exposed_audio:
                    print(f"DEBUG: Writing transcript.json...")
                    with (exposed_audio.parent / "transcript.json").open("w", encoding="utf-8") as fh:
                        json.dump({"transcript": transcript}, fh, indent=2)
                    print(f"DEBUG: transcript.json written")
                print(f"DEBUG: Transcript processing completed successfully")
            except Exception as exc:
                print(f"DEBUG: Error in transcript processing: {exc}")
                import traceback
                traceback.print_exc()
                logger.error("Failed to save DictationFiber: %s", exc)
                self.show_status("Error saving. Please try again.", error=True)
        else:
            print(f"DEBUG: No transcript, showing failure status")
            self.show_status("Transcription Failed. Please retry.", error=True)
        
        print(f"DEBUG: Cleaning up temporary files...")
        if temp and temp.exists() and temp != final_path:
            try:
                print(f"DEBUG: Removing temp file: {temp}")
                temp.unlink(missing_ok=True)
                print(f"DEBUG: Temp file removed")
            except Exception as e:
                print(f"DEBUG: Error removing temp file: {e}")
                pass
        
        print(f"DEBUG: Clearing audio_path...")
        self.audio_path = None
        print(f"DEBUG: _finish_transcription completed")



    def _setup_hotkey_service(self) -> None:
        """Initialize and configure the global hotkey service."""
        try:
            # Only initialize if not in unified mode to avoid conflicts
            if getattr(self, 'unified', False):
                logger.info("Skipping hotkey setup in unified mode")
                return
                
            self.hotkey_service = get_hotkey_service()
            
            # Set callbacks for recording control
            self.hotkey_service.set_callbacks(
                start_callback=self._hotkey_start_recording,
                stop_callback=self._hotkey_stop_recording
            )
            
            # Connect Qt signals
            self.hotkey_service.start_recording.connect(self._hotkey_start_recording)
            self.hotkey_service.stop_recording.connect(self._hotkey_stop_recording)
            self.hotkey_service.hotkey_error.connect(self._hotkey_error)
            
            # Start hotkey monitoring with safer approach
            try:
                if self.hotkey_service.start_hotkeys():
                    logger.info("Global hotkeys initialized successfully")
                else:
                    logger.warning("Failed to initialize global hotkeys - continuing without them")
            except Exception as hotkey_error:
                logger.warning(f"Hotkey initialization failed: {hotkey_error} - continuing without hotkeys")
                
        except Exception as e:
            logger.warning(f"Error setting up hotkey service: {e} - continuing without hotkeys")
            self.hotkey_service = None
    
    def _hotkey_start_recording(self) -> None:
        """Handle hotkey-triggered recording start."""
        try:
            # Use QTimer.singleShot to ensure we're in the main thread
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self._do_hotkey_start)
        except Exception as e:
            logger.error(f"Error in hotkey start recording: {e}")
    
    def _hotkey_stop_recording(self) -> None:
        """Handle hotkey-triggered recording stop."""
        try:
            # Use QTimer.singleShot to ensure we're in the main thread
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self._do_hotkey_stop)
        except Exception as e:
            logger.error(f"Error in hotkey stop recording: {e}")
    
    def _do_hotkey_start(self) -> None:
        """Execute hotkey start in main thread."""
        try:
            # Only start if not already recording
            if "Record" in self.record_btn.text():
                logger.info("Hotkey triggered: Starting recording")
                self._safe_start_record()
        except Exception as e:
            logger.error(f"Error executing hotkey start: {e}")
    
    def _do_hotkey_stop(self) -> None:
        """Execute hotkey stop in main thread.""" 
        try:
            # Only stop if currently recording
            if "Stop" in self.record_btn.text():
                logger.info("Hotkey triggered: Stopping recording")
                self._safe_stop_record()
        except Exception as e:
            logger.error(f"Error executing hotkey stop: {e}")
    
    def _hotkey_error(self, error_msg: str) -> None:
        """Handle hotkey service errors."""
        logger.error(f"Hotkey service error: {error_msg}")
        self.show_status(f"Hotkey error: {error_msg}", error=True)

    def _handle_recording_error(self, error_message: str) -> None:
        """Handle recording errors and reset UI state.
        
        This method provides centralized error handling for recording
        failures and ensures the UI is properly reset.
        
        Args:
            error_message: Description of the error that occurred
            
        Spec: docs/requirements/dictation_requirements.md#error-detection
        Tests: tests/test_intake_pipeline.py#test_error_handling
        """
        print(f"DEBUG: Handling recording error: {error_message}")
        
        # Reset UI state
        self.record_btn.setText("Record")
        self.record_btn.setStyleSheet("")
        self.record_btn.setEnabled(True)
        
        # Stop timers
        if hasattr(self, 'timer'):
            self.timer.stop()
        if hasattr(self, 'wave_timer'):
            self.wave_timer.stop()
        if hasattr(self, 'progress_timer'):
            self.progress_timer.stop()
        if hasattr(self, 'transcription_timeout'):
            self.transcription_timeout.stop()
        
        # Hide UI elements
        self.timer_label.hide()
        self.wave_label.hide()
        
        # Clear audio path
        self.audio_path = None
        
        # Show error message
        self.show_status(error_message, error=True)
        
        print(f"DEBUG: Recording error handled, UI reset complete")

    def closeEvent(self, event) -> None:
        """Handle window close event with proper cleanup."""
        print(f"DEBUG: closeEvent called, cleaning up resources...")
        
        # Check if this is an immediate close (less than 5 seconds after window creation)
        if hasattr(self, '_window_creation_time'):
            elapsed = time.time() - self._window_creation_time
            if elapsed < 5.0:
                print(f"DEBUG: WARNING - Window closing too quickly ({elapsed:.1f}s), might be premature")
                # For debugging, we could ignore very quick closes
                # event.ignore()
                # return
        
        try:
            # Stop global hotkeys
            if hasattr(self, 'hotkey_service') and self.hotkey_service:
                print(f"DEBUG: Stopping global hotkeys")
                self.hotkey_service.stop_hotkeys()
            
            # Cancel any pending transcription
            if hasattr(self, 'current_future') and self.current_future:
                print(f"DEBUG: Cancelling pending transcription future")
                self.current_future.cancel()
                self.current_future = None
            
            # Stop and cleanup recorder
            if hasattr(self, 'recorder') and self.recorder.stream:
                print(f"DEBUG: Stopping recorder stream")
                try:
                    self.recorder.stream.stop()
                    self.recorder.stream.close()
                    self.recorder.stream = None
                except Exception as e:
                    print(f"DEBUG: Error stopping recorder: {e}")
            
            # Shutdown executor with timeout to prevent resource leaks
            if hasattr(self, 'executor'):
                print(f"DEBUG: Shutting down executor with timeout")
                try:
                    # Cancel any pending futures
                    if hasattr(self, 'current_future') and self.current_future:
                        self.current_future.cancel()
                    
                    # Shutdown with wait=True to ensure proper cleanup
                    # Note: timeout parameter requires Python 3.9+
                    import sys
                    if sys.version_info >= (3, 9):
                        self.executor.shutdown(wait=True, timeout=5.0)
                    else:
                        self.executor.shutdown(wait=True)
                    print(f"DEBUG: Executor shutdown completed")
                except Exception as e:
                    print(f"DEBUG: Error shutting down executor: {e}")
                    # Force shutdown if timeout fails
                    try:
                        self.executor.shutdown(wait=False)
                        print(f"DEBUG: Force executor shutdown completed")
                    except:
                        pass
            
            # Stop all timers
            for timer_name in ['timer', 'wave_timer', 'progress_timer', 'transcription_timeout', 'clear_timer', '_device_monitoring_timer', '_resource_timer']:
                if hasattr(self, timer_name):
                    timer = getattr(self, timer_name)
                    if timer and hasattr(timer, 'stop'):
                        timer.stop()
                        print(f"DEBUG: Stopped {timer_name}")
            
            print(f"DEBUG: Cleanup completed successfully")
            
        except Exception as e:
            print(f"DEBUG: Error during cleanup: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Accept the close event
            super().closeEvent(event)


def main() -> None:
    """Launch the intake UI application.

    Spec: docs/requirements/dictation_requirements.md#ui-workflow
    Tests: tests/test_intake_pipeline.py#test_complete_workflow

    Launch the Intake window.

    Pass ``--unified-ui`` to embed the React frontend within the PySide app.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--unified-ui",
        action="store_true",
        help="Embed React UI inside the PySide window",
    )
    parser.add_argument(
        "--light-theme",
        action="store_true",
        help="Use light theme instead of dark",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without display (for testing)",
    )
    args = parser.parse_args()

    # Import sys for platform detection (used throughout function)
    import sys

    # Set headless mode if requested
    if args.headless:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    else:
        # Force Qt to use the correct platform plugin for macOS
        if sys.platform == "darwin":
            # Ensure we're using the cocoa platform plugin on macOS
            os.environ.setdefault("QT_QPA_PLATFORM", "cocoa")
            # Remove any platform-specific settings that might interfere
            os.environ.pop("QT_QPA_PLATFORM_PLUGIN_PATH", None)
            print("DEBUG: Set Qt platform to 'cocoa' for macOS")

    app = QApplication([])
    
    # Debug Qt platform information
    print(f"DEBUG: Qt platform name: {app.platformName()}")
    print(f"DEBUG: QT_QPA_PLATFORM env: {os.environ.get('QT_QPA_PLATFORM', 'not set')}")
    
    # Check if we have proper platform support
    try:
        from PySide6.QtGui import QGuiApplication
        print(f"DEBUG: Primary screen: {QGuiApplication.primaryScreen()}")
        if hasattr(app, 'supportsMultipleWindows'):
            print(f"DEBUG: Supports multiple windows: {app.supportsMultipleWindows()}")
    except Exception as e:
        print(f"DEBUG: Platform info check failed: {e}")
    
    # macOS-specific: Ensure app can come to foreground
    if sys.platform == "darwin":
        try:
            # Set app name for macOS dock/menu
            app.setApplicationName("Zoros Intake")
            app.setApplicationDisplayName("Zoros Intake")
            
            # Request foreground activation
            from PySide6.QtCore import QTimer
            def activate_window():
                # QApplication doesn't have raise_() - only widgets do
                try:
                    if hasattr(win, 'raise_'):
                        win.raise_()
                    if hasattr(win, 'activateWindow'):
                        win.activateWindow()
                    # Try to bring to front using macOS specific calls
                    try:
                        import objc
                        from AppKit import NSApp, NSApplication, NSWorkspace
                        
                        # Check if NSApp is properly initialized
                        if NSApp is None:
                            print("DEBUG: NSApp is None, trying to initialize")
                            NSApp = NSApplication.sharedApplication()
                            
                        if NSApp and hasattr(NSApp, 'activateIgnoringOtherApps_'):
                            # First try to activate the entire application
                            NSApp.activateIgnoringOtherApps_(True)
                            print("DEBUG: macOS NSApp activation called")
                        else:
                            print("DEBUG: NSApp activation method not available")
                            
                        # Alternative: try to activate current process
                        import os
                        current_pid = os.getpid()
                        workspace = NSWorkspace.sharedWorkspace()
                        running_apps = workspace.runningApplications()
                        
                        for app in running_apps:
                            if app.processIdentifier() == current_pid:
                                if hasattr(app, 'activateWithOptions_'):
                                    app.activateWithOptions_(1)  # NSApplicationActivateIgnoringOtherApps
                                    print("DEBUG: Process activation via NSWorkspace called")
                                break
                        
                        # Try to get the native window handle and manipulate it
                        if hasattr(win, 'winId'):
                            window_id = win.winId()
                            print(f"DEBUG: Got window ID: {window_id}")
                            
                            # Try alternative method using Quartz
                            try:
                                import Quartz
                                # Get list of all windows
                                window_list = Quartz.CGWindowListCopyWindowInfo(
                                    Quartz.kCGWindowListOptionOnScreenOnly,
                                    Quartz.kCGNullWindowID
                                )
                                print(f"DEBUG: Found {len(window_list)} windows on screen")
                                
                                # Look for our window
                                for window_info in window_list:
                                    if 'Zoros' in str(window_info.get('kCGWindowName', '')):
                                        print(f"DEBUG: Found Zoros window: {window_info}")
                                        
                            except Exception as quartz_e:
                                print(f"DEBUG: Quartz window search failed: {quartz_e}")
                                
                    except Exception as e:
                        print(f"DEBUG: NSApp activation failed: {e}")
                        
                        # Final fallback - try using subprocess to activate
                        try:
                            import subprocess
                            subprocess.run(['osascript', '-e', 'tell application "System Events" to set frontmost of first process whose name contains "Python" to true'], 
                                         capture_output=True, timeout=2)
                            print("DEBUG: AppleScript activation attempted")
                        except Exception as script_e:
                            print(f"DEBUG: AppleScript activation failed: {script_e}")
                except Exception as e:
                    print(f"DEBUG: Window activation failed: {e}")
            
            # Store activation function for later use
            app._activate_window_func = activate_window
        except Exception as e:
            print(f"Warning: macOS activation failed: {e}")
    
    if not args.light_theme:
        theme_path = ROOT_DIR / "assets" / "style_dark.qss"
        if theme_path.exists():
            app.setStyleSheet(theme_path.read_text())
    
    # Test Qt window creation first on macOS
    if sys.platform == "darwin":
        try:
            # Create a simple test window to verify Qt windowing works
            from PySide6.QtWidgets import QWidget
            test_widget = QWidget()
            test_widget.setWindowTitle("Qt Test Window")
            test_widget.resize(200, 100)
            test_widget.move(50, 50)
            test_widget.show()
            
            print(f"DEBUG: Test window created - visible: {test_widget.isVisible()}")
            print(f"DEBUG: Test window geometry: {test_widget.geometry()}")
            
            # Clean up test window after a moment
            QTimer.singleShot(500, test_widget.close)
            
        except Exception as e:
            print(f"DEBUG: Test window creation failed: {e}")
    
    win = IntakeWindow(unified=args.unified_ui)
    
    # Center the window on screen and ensure visibility
    win.move(100, 100)  # Move to a visible position
    
    # macOS-specific: Ensure window is created in visible space
    if sys.platform == "darwin":
        try:
            # Try to position window on current desktop/space
            from PySide6.QtGui import QGuiApplication
            screen = QGuiApplication.primaryScreen()
            if screen:
                screen_geometry = screen.geometry()
                # Position window in upper-left quadrant of screen
                x = screen_geometry.width() // 4
                y = screen_geometry.height() // 4
                win.move(x, y)
                print(f"DEBUG: Positioned window at {x}, {y} on screen {screen_geometry.width()}x{screen_geometry.height()}")
        except Exception as e:
            print(f"DEBUG: Screen positioning failed: {e}")
    
    win.show()
    print(f"DEBUG: Window shown, geometry: {win.geometry()}, visible: {win.isVisible()}")
    
    # Additional macOS visibility fixes
    if sys.platform == "darwin":
        # Call the stored activation function with window available
        if hasattr(app, '_activate_window_func'):
            app._activate_window_func()
        
        # Set window level to ensure it appears
        try:
            print("DEBUG: Setting window flags for visibility")
            original_flags = win.windowFlags()
            
            # Try multiple Qt window attributes for macOS
            try:
                if hasattr(Qt, 'WA_MacFrameworkScaled'):
                    win.setAttribute(Qt.WA_MacFrameworkScaled, True)
                if hasattr(Qt, 'WA_NativeWindow'):
                    win.setAttribute(Qt.WA_NativeWindow, True)
                if hasattr(Qt, 'WA_ShowWithoutActivating'):
                    win.setAttribute(Qt.WA_ShowWithoutActivating, False)  # Ensure it activates
                print("DEBUG: Qt window attributes set successfully")
            except Exception as attr_e:
                print(f"DEBUG: Qt attributes failed: {attr_e}")
            
            # Set window flags to force it to appear (removed Qt.Tool as it can cause premature closing)
            new_flags = original_flags | Qt.WindowStaysOnTopHint
            win.setWindowFlags(new_flags)
            win.show()  # Re-show with new flags
            
            # Force window state changes
            win.setWindowState(Qt.WindowActive | Qt.WindowNoState)
            win.raise_()
            win.activateWindow()
            
            print(f"DEBUG: Window flags set - original: {original_flags}, new: {new_flags}")
            
            # Remove the hint after a delay so it doesn't stay on top forever
            def reset_flags():
                try:
                    # Don't reset flags immediately - wait longer to ensure window is stable
                    if win.isVisible():
                        win.setWindowFlags(original_flags)
                        win.show()
                        print("DEBUG: Window flags reset")
                        # Final status check
                        print(f"DEBUG: Final window state - visible: {win.isVisible()}, minimized: {win.isMinimized()}, active: {win.isActiveWindow()}")
                    else:
                        print("DEBUG: Window not visible, skipping flag reset")
                except Exception as e:
                    print(f"DEBUG: Flag reset failed: {e}")
            
            # Also add a timer to continuously debug window state
            def debug_window_state():
                print(f"DEBUG: Window state check - visible: {win.isVisible()}, minimized: {win.isMinimized()}, active: {win.isActiveWindow()}")
                print(f"DEBUG: Window geometry: {win.geometry()}")
                if hasattr(win, 'windowState'):
                    print(f"DEBUG: Window state flags: {win.windowState()}")
            
            QTimer.singleShot(1000, debug_window_state)
            QTimer.singleShot(5000, reset_flags)  # Wait longer before resetting flags
            QTimer.singleShot(6000, debug_window_state)
            print("DEBUG: Window visibility setup complete")
        except Exception as e:
            print(f"Warning: Window flags adjustment failed: {e}")
    else:
        # For non-macOS systems
        win.raise_()
        win.activateWindow()
    
    app.exec()


if __name__ == "__main__":
    main()
