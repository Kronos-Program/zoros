from __future__ import annotations

import io
import struct
import wave

import pytest

fastapi = pytest.importorskip("fastapi")
if not hasattr(fastapi, "testclient"):
    pytest.skip("fastapi package unavailable", allow_module_level=True)
from fastapi.testclient import TestClient

whisper_webui = pytest.importorskip("whisper_webui")
app = whisper_webui.app
from whisper.backends.whisper_cpp_backend import WhisperCppBackend
from whisper.models.dictation import Dictation


def _dummy_wav() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        frames = struct.pack("<" + "h" * 44100, *([0] * 44100))
        w.writeframes(frames)
    return buf.getvalue()


def test_transcribe_endpoint(monkeypatch):
    client = TestClient(app)

    def fake_transcribe(self, path: str) -> str:
        return "hello world"

    saved = {}

    def fake_save(cls, text: str, backend: str):
        saved["text"] = text
        return Dictation(text=text, backend=backend, id="123", timestamp="0")

    monkeypatch.setattr(WhisperCppBackend, "transcribe", fake_transcribe)
    monkeypatch.setattr(Dictation, "save", classmethod(fake_save))

    resp = client.post("/api/transcribe", data=_dummy_wav())
    assert resp.status_code == 200
    data = resp.json()
    assert data["text"] == "hello world"
    assert saved["text"] == "hello world"
