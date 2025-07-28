import os
import sys
import types
import sqlite3
import json
from pathlib import Path

import pytest

# Skip tests if PySide6 is unavailable
pytest.importorskip("PySide6.QtWidgets")

# Fake audio deps so import does not require native libs
sys.modules.setdefault("sounddevice", types.ModuleType("sounddevice"))
sys.modules.setdefault("soundfile", types.ModuleType("soundfile"))
numpy_mock = types.ModuleType("numpy")
numpy_mock.ndarray = type('ndarray', (), {})
sys.modules.setdefault("numpy", numpy_mock)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from zoros.intake import main as intake


@pytest.fixture
def window(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    win = intake.IntakeWindow(db)
    yield win


def test_record_toggle(window, monkeypatch):
    started = False
    stopped = False

    monkeypatch.setattr(window.recorder, "start", lambda *a, **k: globals().__setitem__("started", True))
    monkeypatch.setattr(window.recorder, "stop", lambda path, keep_stream=False: (globals().__setitem__("stopped", True), path.touch()))

    window.toggle_record()
    assert started
    assert window.record_btn.text() == "Stop"

    window.toggle_record()
    assert stopped
    assert window.record_btn.text() == "Record"


def test_notes_persist(window):
    txt = "hello"
    window.notes.setPlainText(txt)
    assert window.notes.toPlainText() == txt


def test_stop_record_creates_fiber(window, tmp_path, monkeypatch):

    monkeypatch.setattr(window.recorder, "start", lambda *a, **k: None)
    monkeypatch.setattr(window.recorder, "stop", lambda path, keep_stream=False: path.write_text("a"))
    monkeypatch.setattr(intake, "transcribe_audio", lambda *args: "voice")

    class FakeFuture:
        def add_done_callback(self, cb):
            class R:
                def result(self_inner):
                    return "voice"
            cb(R())

    monkeypatch.setattr(window.executor, "submit", lambda func, arg: FakeFuture())
    monkeypatch.setattr(intake.QTimer, "singleShot", lambda ms, func: func())

    window.start_record()
    window.stop_record()

    with sqlite3.connect(window.db_path) as conn:
        cur = conn.execute("SELECT id, content, audio_path FROM intake")
        row = cur.fetchone()
        assert row[1] == "voice"
        assert Path(row[2]).exists()
    expected = f"Transcription saved to {window.db_path}#{row[0]}"
    assert window.status.currentMessage() == expected


def test_submit_inserts_row(window, tmp_path, monkeypatch):
    window.notes.setPlainText("note")
    window.on_submit()

    with sqlite3.connect(window.db_path) as conn:
        cur = conn.execute("SELECT id, content, audio_path FROM intake")
        row = cur.fetchone()
        assert row[1] == "note"
        assert row[2] is None
    assert window.notes.toPlainText() == ""
    expected = f"Saved to {window.db_path}#{row[0]}"
    assert window.status.currentMessage() == expected


def test_exposed_data(tmp_path: Path, monkeypatch):
    settings = {
        "PersistentAudioStream": False,
        "SelectedAudioDevice": None,
        "WhisperBackend": "StandardWhisper",
        "WhisperModel": "small",
        "AutoCopy": False,
        "ExposeData": True,
        "DebugLog": False,
    }
    monkeypatch.setattr(intake, "load_settings", lambda: settings)
    monkeypatch.setattr(intake, "DICTATIONS_DIR", tmp_path / "dict")
    win = intake.IntakeWindow(tmp_path / "db.sqlite")

    monkeypatch.setattr(win.recorder, "start", lambda *a, **k: None)
    monkeypatch.setattr(win.recorder, "stop", lambda path, keep_stream=False: path.write_text("a"))
    monkeypatch.setattr(intake, "transcribe_audio", lambda *args: "voice")

    class FakeFuture:
        def add_done_callback(self, cb):
            class R:
                def result(self_inner):
                    return "voice"
            cb(R())

    monkeypatch.setattr(win.executor, "submit", lambda func, arg: FakeFuture())
    monkeypatch.setattr(intake.QTimer, "singleShot", lambda ms, func: func())

    win.start_record()
    win.stop_record()

    with sqlite3.connect(win.db_path) as conn:
        fid = conn.execute("SELECT id FROM intake").fetchone()[0]

    folder = tmp_path / "dict" / fid
    assert (folder / "audio.wav").exists()
    data = json.loads((folder / "transcript.json").read_text())
    assert data["transcript"] == "voice"


def test_load_unload(window, monkeypatch):
    class FakeBackend:
        def __init__(self, model: str) -> None:
            self.model = model
        def transcribe(self, path: str) -> str:
            return "ok"

    monkeypatch.setitem(intake.BACKEND_MAP, "Mock", FakeBackend)
    window.whisper_backend = "Mock"
    window.whisper_model = "tiny"

    window.toggle_model()
    assert isinstance(window.backend_instance, FakeBackend)
    assert window.load_btn.text() == "Unload Model"
    window.toggle_model()
    assert window.backend_instance is None
    assert window.load_btn.text() == "Load Model"
