from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List, Tuple

import numpy as np
import soundfile as sf
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.services.dictation_service.engines import EngineRegistry, TranscriptionEngine
from backend.services.dictation_service.models import EngineConfig, Segment
from backend.services.dictation_service.repository import DictationRepository
from backend.services.dictation_service.router import (
    get_dictation_service,
    router as dictation_router,
)
from backend.services.dictation_service.service import DictationService
from backend.services.dictation_service.vad import SegmentWindow, SileroVADSegmenter
from tests.fixtures.dictation_fixture_db import copy_dictation_fixture_db


def _write_audio(tmp_path: Path) -> Path:
    """Create a simple mono WAV file for testing."""
    sr = 16_000
    duration = 1.0
    t = np.linspace(0, duration, int(sr * duration), False)
    wave = 0.1 * np.sin(2 * np.pi * 440 * t)
    audio_path = tmp_path / "sample.wav"
    sf.write(audio_path, wave, sr)
    return audio_path


class DummySegmenter(SileroVADSegmenter):
    """Deterministic VAD segmenter for tests."""

    def __init__(self, *_args, **_kwargs):
        self.config = None

    def segment(self, _audio_path: str) -> List[SegmentWindow]:
        return [SegmentWindow(0.0, 1.0)]


class DummyEngine(TranscriptionEngine):
    """Return canned text for every segment."""

    def __init__(self, config):
        super().__init__(config)
        self.backend_name = "DummyBackend"
        self._backend_fn = self.transcribe  # type: ignore

    def transcribe(self, _path: str) -> str:
        return "dummy"

    def transcribe_segments(
        self,
        _audio_path: str,
        windows: List[SegmentWindow],
    ) -> List[Segment]:
        return [
            Segment(
                start_sec=window.start_sec,
                end_sec=window.end_sec,
                text="dummy",
                attempts=1,
            )
            for window in windows
        ]


class DummyRegistry(EngineRegistry):
    """Engine registry that always returns the dummy implementation."""

    def create(self, config):
        return DummyEngine(config)

    def create_for_backend(self, backend: str, model: str) -> TranscriptionEngine:
        return DummyEngine(EngineConfig(backend=backend, model=model))


def _build_client(tmp_path: Path) -> Tuple[TestClient, Path]:
    """Create a TestClient with temporary dependency overrides."""
    app = FastAPI()
    app.include_router(dictation_router)

    fixture_db = copy_dictation_fixture_db(tmp_path)
    repo = DictationRepository(db_path=fixture_db)
    service = DictationService(
        repository=repo,
        vad_segmenter_factory=lambda cfg: DummySegmenter(cfg),
        engine_registry=DummyRegistry(),
    )

    app.dependency_overrides[get_dictation_service] = lambda: service
    return TestClient(app), fixture_db


def test_create_and_fetch_job(tmp_path: Path) -> None:
    client, _ = _build_client(tmp_path)
    audio_path = _write_audio(tmp_path)

    create_resp = client.post(
        "/api/dictations",
        json={
            "notes": "hello world",
            "metadata": {"source": "pytest"},
            "audio_path": str(audio_path),
        },
    )
    assert create_resp.status_code == 201
    job = create_resp.json()

    get_resp = client.get(f"/api/dictations/{job['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["notes"] == "hello world"


def test_start_job_changes_status(tmp_path: Path) -> None:
    client, fixture_db = _build_client(tmp_path)
    with sqlite3.connect(fixture_db) as conn:
        audio_path = conn.execute(
            "SELECT audio_path FROM intake ORDER BY timestamp LIMIT 1"
        ).fetchone()[0]
    job_id = client.post(
        "/api/dictations",
        json={"audio_path": audio_path},
    ).json()["id"]

    start_resp = client.post(f"/api/dictations/{job_id}/start")
    assert start_resp.status_code == 200
    assert start_resp.json()["status"] == "completed"
    assert start_resp.json()["segments"][0]["text"] == "dummy"

    list_resp = client.get("/api/dictations")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1
