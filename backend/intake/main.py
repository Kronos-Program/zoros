"""
Service-first Intake UI entrypoint.

Spec: docs/specs/dictation_service_spec.md#api-surface
Tasks: docs/tasks/TASK-091_dictation-module-modernization.md, docs/tasks/TASK-092_dictation-service-hardening.md
Architecture: docs/zoros_architecture.md
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Optional
import json

# Reduce macOS Qt layer spam and verbose drawing logs
os.environ.setdefault("QT_MAC_WANTS_LAYER", "1")
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.drawing.debug=false")

try:  # optional PySide6 imports
    from PySide6.QtCore import Qt, QTimer, Signal
    from PySide6.QtGui import QKeySequence, QShortcut, QIcon
    from PySide6.QtWidgets import (
        QApplication,
        QLabel,
        QMainWindow,
        QPushButton,
        QTextEdit,
        QVBoxLayout,
        QWidget,
        QHBoxLayout,
        QComboBox,
        QStatusBar,
        QDialog,
        QCheckBox,
        QLineEdit,
    )
except Exception:  # pragma: no cover - missing Qt
    import types

    class _Dummy:
        def __init__(self, *args, **kwargs):
            pass

        def __call__(self, *args, **kwargs):
            return self

        def __getattr__(self, _name):
            return self

        def hide(self):
            pass

        def show(self):
            pass

        def setEnabled(self, _enabled):
            pass

        def setText(self, _text):
            pass

        def setLayout(self, _layout):
            pass

        def addWidget(self, _widget):
            pass

        def addLayout(self, _layout):
            pass

        def currentIndex(self):
            return 0

        def itemData(self, _idx):
            return None

        def addItem(self, *_args, **_kwargs):
            pass

        def currentText(self):
            return ""

        def append(self, *_args, **_kwargs):
            pass

        def start(self):
            pass

        def stop(self):
            pass

        def timeout(self):
            return self

        def connect(self, *_args, **_kwargs):
            pass

        def setSingleShot(self, *_args, **_kwargs):
            pass

        def setInterval(self, *_args, **_kwargs):
            pass

        def isActive(self):
            return False

        def windowFlags(self):
            return 0

        def setWindowFlags(self, _flags):
            pass

        def setWindowTitle(self, _title):
            pass

    Qt = QTimer = Signal = QApplication = QLabel = QMainWindow = QPushButton = QTextEdit = QVBoxLayout = QWidget = QHBoxLayout = QComboBox = QStatusBar = _Dummy  # type: ignore

from backend.interfaces.intake.controller import (
    IntakeController,
    PersistenceAdapter,
    RecordingAdapter,
    ServiceAdapter,
    TranscriptionOutcome,
)
from backend.interfaces.intake.persistence import (
    DB_PATH,
    insert_intake,
    list_intake_records,
    update_intake_submission,
)
from backend.interfaces.intake.service_client import DictationServiceClient
from backend.intake.recorder import Recorder

logger = logging.getLogger(__name__)

# Circuit breaker state (legacy compatibility)
_backend_failure_counts: Dict[str, int] = {}
_backend_last_failure: Dict[str, float] = {}

DEFAULT_SETTINGS = {
    "PersistentAudioStream": False,
    "SelectedAudioDevice": None,
    "WhisperBackend": "mock",
    "WhisperModel": "mock",
    "UseDictationService": True,
    "AutoCopy": False,
    "ExposeData": False,
    "DebugLog": False,
    "RecordHotkey": "Ctrl+R",
}
CONFIG_PATH = Path("config") / "intake_settings.json"


def load_settings() -> dict:
    """Load intake settings with service-first defaults."""
    try:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        else:
            data = {}
    except Exception:
        data = {}
    for key, val in DEFAULT_SETTINGS.items():
        data.setdefault(key, val)
    return data


def save_settings(data: dict) -> None:
    """Persist intake settings."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _should_skip_backend(backend: str) -> bool:
    """Circuit breaker to skip flaky backends (legacy compatibility)."""
    import time

    failure_count = _backend_failure_counts.get(backend, 0)
    last_failure = _backend_last_failure.get(backend, 0)
    if failure_count >= 3 and (time.time() - last_failure) < 300:
        return True
    if (time.time() - last_failure) > 300:
        _backend_failure_counts[backend] = 0
    return False


def _record_backend_failure(backend: str) -> None:
    """Record a backend failure for circuit breaker pattern."""
    import time

    _backend_failure_counts[backend] = _backend_failure_counts.get(backend, 0) + 1
    _backend_last_failure[backend] = time.time()


class IntakeWindow(QMainWindow):
    """Thin PySide window that delegates to the dictation service."""

    service_result_signal = Signal(object)

    def __init__(self, db_path: Path = DB_PATH) -> None:
        super().__init__()
        self.setWindowTitle("Zoros Intake (Service)")
        self.db_path = db_path
        self.settings = load_settings()

        # Core components
        self.recorder = Recorder()
        self.dictation_client = DictationServiceClient(db_path=self.db_path)
        self.recording_adapter = RecordingAdapter(self.recorder)
        self.service_adapter = ServiceAdapter(self.dictation_client)
        self.persistence_adapter = PersistenceAdapter(
            insert_intake,
            db_path=self.db_path,
            expose_data=False,
        )
        # Avoid implicit mock fallback unless user configures it
        self.dictation_client.engine_config.fallback_backends = []
        self.controller = IntakeController(
            recording=self.recording_adapter,
            service=self.service_adapter,
            persistence=self.persistence_adapter,
        )
        self.executor = ThreadPoolExecutor(max_workers=1)

        self.current_fiber_id: Optional[str] = None
        self.latest_metadata: Dict[str, Any] = {}
        self.recording_start_time: Optional[float] = None
        self.hotkey_sequence = self.settings.get("RecordHotkey", "Ctrl+R")
        self.intake_records: list[Dict[str, Any]] = []
        self.current_record_index: int = -1  # -1 represents "New"

        # UI
        central = QWidget()
        layout = QVBoxLayout(central)

        controls = QHBoxLayout()
        self.record_btn = QPushButton("🎙️")
        self.record_btn.clicked.connect(self.toggle_record)
        self.record_btn.setToolTip("Start/stop recording")
        controls.addWidget(self.record_btn)

        self.warm_btn = QPushButton("⚪")
        self.warm_btn.clicked.connect(self.warm_models)
        self.warm_btn.setToolTip("Warm/unmount models")
        controls.addWidget(self.warm_btn)

        self.settings_btn = QPushButton("⚙️")
        self.settings_btn.clicked.connect(self.show_settings)
        self.settings_btn.setToolTip("Settings")
        controls.addWidget(self.settings_btn)

        self.dictation_library_btn = QPushButton("📚")
        self.dictation_library_btn.setToolTip("Open dictation library")
        self.dictation_library_btn.clicked.connect(self.open_dictation_library)
        controls.addWidget(self.dictation_library_btn)
        self.fiberizer_btn = QPushButton("🧬")
        self.fiberizer_btn.setToolTip("Open fiberizer")
        self.fiberizer_btn.clicked.connect(self.open_fiberizer)
        controls.addWidget(self.fiberizer_btn)
        self.experiments_btn = QPushButton("🧪")
        self.experiments_btn.setToolTip("Experiments / other UIs")
        self.experiments_btn.clicked.connect(self.open_experiments)
        controls.addWidget(self.experiments_btn)

        layout.addLayout(controls)

        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Transcript will appear here...")
        layout.addWidget(self.notes)

        action_row = QHBoxLayout()
        self.new_btn = QPushButton("🆕")
        self.new_btn.clicked.connect(self.new_transcript)
        self.new_btn.setToolTip("New transcript")
        self.copy_btn = QPushButton("📋")
        self.copy_btn.setToolTip("Copy transcript")
        self.copy_btn.clicked.connect(self.copy_notes)
        self.submit_btn = QPushButton("📨")
        self.submit_btn.clicked.connect(self.on_submit)
        self.submit_btn.setToolTip("Submit transcript")
        action_row.addWidget(self.new_btn)
        action_row.addWidget(self.copy_btn)
        action_row.addWidget(self.submit_btn)
        action_row.addStretch()
        self.prev_btn = QPushButton("◀")
        self.prev_btn.clicked.connect(self.load_previous_record)
        self.history_label = QLabel("0 of 0")
        self.next_btn = QPushButton("▶")
        self.next_btn.clicked.connect(self.load_next_record)
        self.prev_btn.setToolTip("Previous record (New when at start)")
        self.next_btn.setToolTip("Next record")
        action_row.addWidget(self.prev_btn)
        action_row.addWidget(self.history_label)
        action_row.addWidget(self.next_btn)
        layout.addLayout(action_row)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.service_state_label = QLabel("Ready")
        self.status.addPermanentWidget(self.service_state_label)

        self.setCentralWidget(central)

        # Timers and signals
        self.progress_timer = QTimer()
        self.progress_timer.setInterval(1000)
        self.progress_timer.timeout.connect(self._update_progress)
        try:
            app = QApplication.instance()
            if app:
                self.progress_timer.moveToThread(app.thread())
        except Exception:
            pass
        self.progress_dots = 0
        self.service_result_signal.connect(self._handle_service_result)
        self.future_poll_timer = QTimer()
        self.future_poll_timer.setInterval(200)
        self.future_poll_timer.timeout.connect(self._poll_future)

        # Hotkey for record/stop
        try:
            self._bind_hotkey(self.hotkey_sequence)
        except Exception:
            pass

        # Always on top
        try:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        except Exception:
            pass

        # Tray icon (best effort) and window icon
        try:
            from PySide6.QtWidgets import QSystemTrayIcon

            icon_path = Path("assets/icon.png")
            if icon_path.exists():
                icon = QIcon(str(icon_path))
                self.setWindowIcon(icon)
                tray = QSystemTrayIcon(icon, self)
                tray.setToolTip("Zoros Intake")
                tray.show()
                self.tray_icon = tray
        except Exception:
            pass

    def toggle_record(self) -> None:
        if self.record_btn.text().startswith("🎙️"):
            self.start_record()
        else:
            # allow a second stop click to cancel/kill processing
            if getattr(self, "current_future", None) and not self.current_future.done():
                self.current_future.cancel()
                try:
                    self.progress_timer.stop()
                    self.future_poll_timer.stop()
                except Exception:
                    pass
                self.record_btn.setText("🎙️")
                self.record_btn.setEnabled(True)
                self.service_state_label.setText("Cancelled")
                self.show_status("Transcription cancelled", error=True)
            else:
                self.stop_record()

    def start_record(self) -> None:
        try:
            self.controller.start_recording(device=self.recorder.device)
            self.recording_start_time = perf_counter()
            self.record_btn.setText("⏺️")
            self.record_btn.setEnabled(True)
            self.show_status("Recording...")
            self.service_state_label.setText("Recording")
            # Warm in the background; do not block recording
            if self.warm_btn.text() != "🟢":
                def _warm():
                    try:
                        self.dictation_client.warm_engine()
                        return True
                    except Exception as exc:  # pragma: no cover - best effort
                        logger.debug("Background warm failed: %s", exc)
                        return False

                warm_future = self.executor.submit(_warm)

                def _flip(_):
                    try:
                        if warm_future.done():
                            # Flip to warm as long as warm task completed (even if warm_engine returns None)
                            self.warm_btn.setText("🟢")
                    except Exception as exc:  # pragma: no cover - defensive
                        logger.debug("Warm flip failed: %s", exc)

                warm_future.add_done_callback(lambda fut: QTimer.singleShot(0, lambda: _flip(fut)))
        except Exception as exc:
            logger.error("Failed to start recording: %s", exc)
            self.show_status("Failed to start recording", error=True)

    def stop_record(self) -> None:
        """Stop recording and dispatch transcription via controller in a worker thread."""
        self.record_btn.setEnabled(False)
        self.progress_dots = 0
        self.progress_timer.start()
        self.show_status("Processing...")
        self.service_state_label.setText("Processing")
        logger.info("Submitting transcription task from UI")

        def _run():
            logger.info("Controller stop_and_transcribe start")
            result = self.controller.stop_and_transcribe(
                notes=self.notes.toPlainText() or None,
                metadata={"source": "intake_ui"},
                keep_stream=False,
            )
            logger.info("Controller stop_and_transcribe finished")
            return result

        future = self.executor.submit(_run)
        self.current_future = future
        self.future_poll_timer.start()
        future.add_done_callback(lambda f: self._on_future_done(f))

    def _on_future_done(self, future) -> None:
        def _emit_result(outcome: Optional[TranscriptionOutcome], error: Optional[str] = None) -> None:
            if error:
                self.show_status(error, error=True)
                self.record_btn.setText("🎙️")
                self.record_btn.setEnabled(True)
                try:
                    self.progress_timer.stop()
                except Exception:
                    pass
                self.service_state_label.setText("Error")
            elif outcome:
                if isinstance(outcome, TranscriptionOutcome):
                    self.service_result_signal.emit(outcome)
                else:
                    # Defensive: if the future returned something unexpected, reset UI
                    self.show_status("Transcription returned invalid result", error=True)
                    self.record_btn.setText("🎙️")
                    self.record_btn.setEnabled(True)
                    self.service_state_label.setText("Error")
            self.current_future = None

        try:
            outcome = future.result()
            # If the worker returned raw data (e.g., DictationJob), coerce to a minimal outcome to unblock UI
            if not isinstance(outcome, TranscriptionOutcome):
                class _MinimalOutcome:
                    def __init__(self, job):
                        self.job = job
                        self.transcript = "\n".join(getattr(job, "segments", [])) if hasattr(job, "segments") else ""
                        self.metadata = getattr(job, "metadata", {})
                        self.fiber_id = None
                outcome = _MinimalOutcome(outcome)
            QTimer.singleShot(0, lambda: _emit_result(outcome, None))
        except Exception as exc:
            logger.error("Transcription failed: %s", exc)
            QTimer.singleShot(0, lambda: _emit_result(None, "Transcription failed"))

    def _poll_future(self) -> None:
        """Poll the current future and finalize UI when it completes."""
        future = getattr(self, "current_future", None)
        if future is None:
            return
        if future.done():
            self.future_poll_timer.stop()
            self._on_future_done(future)

    def _handle_service_result(self, outcome: TranscriptionOutcome) -> None:
        try:
            self.progress_timer.stop()
        except Exception:
            pass
        transcript = getattr(outcome, "transcript", "") or ""
        self.latest_metadata = getattr(outcome, "metadata", {}) or {}
        self.current_fiber_id = getattr(outcome, "fiber_id", None)
        self.notes.setPlainText(transcript)
        if self.settings.get("AutoCopy") and transcript:
            app = QApplication.instance()
            if app and app.clipboard():
                app.clipboard().setText(transcript)
        self.record_btn.setText("🎙️")
        self.record_btn.setEnabled(True)
        self.record_btn.setStyleSheet("")
        self.service_state_label.setText("Ready")
        self.current_future = None
        try:
            self.future_poll_timer.stop()
        except Exception:
            pass

        job = getattr(outcome, "job", None)
        if job:
            segments = len(getattr(job, "segments", []))
            engines = job.metadata.get("engine_chain") if job.metadata else None
            parts = [f"Segments: {segments}"]
            if engines:
                parts.append(f"Engines: {engines}")
            self.show_status(" | ".join(parts))
        if self.current_fiber_id:
            logger.info("Dictation complete (fiber_id=%s)", self.current_fiber_id)
        # Mark warmed after a successful completion
        self.warm_btn.setText("🟢")

    def _update_progress(self) -> None:
        self.progress_dots = (self.progress_dots + 1) % 4
        dots = "." * self.progress_dots
        elapsed = 0.0
        if self.recording_start_time:
            elapsed = perf_counter() - self.recording_start_time
        # Display left message and right state
        self.show_status(f"Processing{dots} ({elapsed:.1f}s)")
        self.service_state_label.setText(f"Processing {elapsed:.1f}s")

    def on_submit(self) -> None:
        text = self.notes.toPlainText().strip()
        if not text:
            self.show_status("Nothing to submit", error=True)
            return
        try:
            if self.current_fiber_id:
                update_intake_submission(
                    self.current_fiber_id,
                    content=text,
                    correction=text,
                    submitted=True,
                    db=self.db_path,
                )
                logger.info("Dictation submitted (fiber_id=%s)", self.current_fiber_id)
            else:
                self.current_fiber_id = insert_intake(
                    text,
                    audio_path=None,
                    correction=text,
                    fiber_type="dictation",
                    db=self.db_path,
                    submitted=True,
                )
                logger.info("Dictation submitted (fiber_id=%s)", self.current_fiber_id)
            self.show_status("Submitted")
            self.new_transcript()
        except Exception as exc:
            logger.error("Submit failed: %s", exc)
            self.show_status("Submit failed", error=True)

    def show_status(self, text: str, *, error: bool = False) -> None:
        if self.status:
            self.status.setStyleSheet("color: red;" if error else "")
            self.status.showMessage(text, 4000)

    def copy_notes(self) -> None:
        text = self.notes.toPlainText()
        if not text:
            self.show_status("Nothing to copy", error=True)
            return
        app = QApplication.instance()
        if app and app.clipboard():
            app.clipboard().setText(text)
            self.show_status("Copied transcript")

    def show_settings(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Settings")
        layout = QVBoxLayout(dlg)
        self.autocopy_cb = QCheckBox("Copy on complete")
        self.autocopy_cb.setChecked(bool(self.settings.get("AutoCopy", False)))
        layout.addWidget(self.autocopy_cb)
        # Audio device selection
        device_combo = QComboBox()
        device_combo.addItem("Default", userData=None)
        try:
            import sounddevice as sd  # type: ignore

            for idx, dev in enumerate(sd.query_devices()):
                if dev.get("max_input_channels", 0) > 0:
                    name = dev.get("name", f"Device {idx}")
                    device_combo.addItem(name, userData=idx)
        except Exception:
            pass
        selected_device = self.settings.get("SelectedAudioDevice")
        if selected_device is not None:
            for i in range(device_combo.count()):
                if device_combo.itemData(i) == selected_device:
                    device_combo.setCurrentIndex(i)
                    break
        layout.addWidget(QLabel("Audio device"))
        layout.addWidget(device_combo)

        backend_combo = QComboBox()
        for b in ["mlx_whisper", "faster_whisper", "mock"]:
            backend_combo.addItem(b)
        backend_combo.setCurrentText(self.settings.get("WhisperBackend", "mlx_whisper"))
        model_combo = QComboBox()
        for m in ["large-v3-turbo", "large-v3", "small"]:
            model_combo.addItem(m)
        model_combo.setCurrentText(self.settings.get("WhisperModel", "large-v3-turbo"))
        layout.addWidget(QLabel("Backend"))
        layout.addWidget(backend_combo)
        layout.addWidget(QLabel("Model"))
        layout.addWidget(model_combo)

        layout.addWidget(QLabel("Record hotkey (e.g., Ctrl+R)"))
        hotkey_edit = QLineEdit(self.hotkey_sequence)
        layout.addWidget(hotkey_edit)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

        def _save():
            self.settings["AutoCopy"] = self.autocopy_cb.isChecked()
            self.settings["SelectedAudioDevice"] = device_combo.currentData()
            self.settings["WhisperBackend"] = backend_combo.currentText()
            self.settings["WhisperModel"] = model_combo.currentText()
            self.settings["RecordHotkey"] = hotkey_edit.text().strip() or "Ctrl+R"
            self.hotkey_sequence = self.settings["RecordHotkey"]
            self._bind_hotkey(self.hotkey_sequence)
            self.dictation_client.configure(
                backend=self.settings["WhisperBackend"],
                model=self.settings["WhisperModel"],
                fallback_backends=["faster_whisper", "mock"],
            )
            if self.settings["SelectedAudioDevice"] is not None:
                try:
                    self.recorder.device = int(self.settings["SelectedAudioDevice"])
                except Exception:
                    self.recorder.device = None
            save_settings(self.settings)
            dlg.accept()

        save_btn.clicked.connect(_save)
        cancel_btn.clicked.connect(dlg.reject)
        dlg.exec()

    def warm_models(self) -> None:
        try:
            warming = self.warm_btn.text().startswith("⚪")
            if warming:
                try:
                    self.dictation_client.warm_engine()
                    self.warm_btn.setText("🟢")
                    self.show_status("Model warmed")
                except Exception as exc:
                    self.show_status(f"Warm failed: {exc}", error=True)
            else:
                self.dictation_client.reset_engines()
                self.warm_btn.setText("⚪")
                self.show_status("Models cleared")
        except Exception as exc:
            logger.error("Warm/unmount failed: %s", exc)
            self.show_status("Warm/unmount failed", error=True)

    def open_dictation_library(self) -> None:
        try:
            from backend.intake import dictation_library as lib

            window = lib.DictationLibraryWindow(db_path=self.db_path)
            window.show()
        except Exception as exc:
            logger.error("Failed to open dictation library: %s", exc)
            self.show_status("Dictation library unavailable", error=True)

    def open_fiberizer(self) -> None:
        try:
            from backend.interfaces.streamlit.feature_tour import main as fiberizer_main

            fiberizer_main()
        except Exception:
            self.show_status("Fiberizer unavailable", error=True)

    def open_experiments(self) -> None:
        """Placeholder experiments launcher (stub list of windows)."""
        try:
            dlg = QDialog(self)
            dlg.setWindowTitle("Experiments")
            layout = QVBoxLayout(dlg)
            layout.addWidget(QLabel("Launch external experiment UIs:"))
            buttons = QHBoxLayout()
            react_btn = QPushButton("React UI")
            react_btn.clicked.connect(lambda: self.show_status("Launch React UI (stub)"))
            streamlit_btn = QPushButton("Streamlit Tools")
            streamlit_btn.clicked.connect(lambda: self.show_status("Launch Streamlit (stub)"))
            buttons.addWidget(react_btn)
            buttons.addWidget(streamlit_btn)
            layout.addLayout(buttons)
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(dlg.accept)
            layout.addWidget(close_btn)
            dlg.exec()
        except Exception as exc:
            logger.error("Experiments launcher failed: %s", exc)
            self.show_status("Experiments launcher failed", error=True)

    def _bind_hotkey(self, sequence: str) -> None:
        try:
            if hasattr(self, "record_shortcut"):
                self.record_shortcut.setKey(QKeySequence(sequence))
            else:
                self.record_shortcut = QShortcut(QKeySequence(sequence), self)
                self.record_shortcut.activated.connect(self.toggle_record)
        except Exception:
            pass

    # History navigation
    def refresh_history(self) -> None:
        try:
            self.intake_records = list_intake_records(self.db_path)
            self.current_record_index = -1
            self._update_history_label()
        except Exception as exc:
            logger.error("Failed to load history: %s", exc)

    def _update_history_label(self) -> None:
        total = len(self.intake_records)
        current_display = 0 if self.current_record_index < 0 else self.current_record_index + 1
        self.history_label.setText(f"{current_display} of {total}")
        # Allow left move from first record to "New"
        self.prev_btn.setEnabled(total > 0 and self.current_record_index >= 0)
        self.next_btn.setEnabled(total > 0 and self.current_record_index < total - 1)

    def load_previous_record(self) -> None:
        if self.current_record_index <= 0:
            self.current_record_index = -1  # go to "New"
        else:
            self.current_record_index -= 1
        self.load_current_record()

    def load_next_record(self) -> None:
        if self.current_record_index < len(self.intake_records) - 1:
            self.current_record_index += 1
            self.load_current_record()

    def load_current_record(self) -> None:
        if self.current_record_index < 0:
            self.new_transcript()
            return
        if self.current_record_index >= len(self.intake_records):
            return
        rec = self.intake_records[self.current_record_index]
        content = rec.get("correction") or rec.get("content", "")
        self.notes.setPlainText(content)
        self.current_fiber_id = rec["id"]
        self._update_history_label()
        ts = rec.get("timestamp", "")[:19] if rec.get("timestamp") else ""
        self.show_status(f"{ts} | {rec.get('fiber_type','dictation')}")

    def new_transcript(self) -> None:
        self.current_record_index = -1
        self.current_fiber_id = None
        self.notes.clear()
        self.show_status("New transcript")
        self._update_history_label()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true", help="Run without display")
    args = parser.parse_args()

    if args.headless:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app = QApplication([])
    win = IntakeWindow()
    win.refresh_history()
    win.show()
    app.exec()


if __name__ == "__main__":
    main()

# Backward-compatible exports for tests expecting helpers from legacy module.
__all__ = [
    "main",
    "IntakeWindow",
    "_should_skip_backend",
    "_record_backend_failure",
    "load_settings",
]
