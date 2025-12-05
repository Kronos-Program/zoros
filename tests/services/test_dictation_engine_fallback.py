from __future__ import annotations

from pathlib import Path
from typing import List

import numpy as np
import soundfile as sf

from backend.services.dictation_service.engines import (
    TranscriptionEngine,
    transcribe_with_engine_chain,
)
from backend.services.dictation_service.models import EngineConfig, Segment
from backend.services.dictation_service.vad import SegmentWindow


def _write_silence(tmp_path: Path) -> Path:
    """Create a short mono WAV file."""
    sr = 16_000
    audio = np.zeros(sr, dtype=np.float32)
    wav_path = tmp_path / "silence.wav"
    sf.write(wav_path, audio, sr)
    return wav_path


class _FailingEngine(TranscriptionEngine):
    def __init__(self, config: EngineConfig):
        super().__init__(config)
        self.backend_name = "Failing"
        self._backend_fn = self._transcribe  # type: ignore

    def _transcribe(self, _path: str) -> str:
        raise RuntimeError("boom")

    def transcribe_segments(
        self, _audio_path: str | Path, _windows: List[SegmentWindow]
    ) -> List[Segment]:
        return []


class _SuccessEngine(TranscriptionEngine):
    def __init__(self, config: EngineConfig):
        super().__init__(config)
        self.backend_name = "Success"
        self._backend_fn = self._transcribe  # type: ignore

    def _transcribe(self, _path: str) -> str:
        return "ok"

    def transcribe_segments(
        self, _audio_path: str | Path, _windows: List[SegmentWindow]
    ) -> List[Segment]:
        return []


def test_transcribe_with_engine_chain_falls_back(tmp_path: Path) -> None:
    wav_path = _write_silence(tmp_path)
    windows = [SegmentWindow(0.0, 1.0)]
    engines = [
        _FailingEngine(EngineConfig()),
        _SuccessEngine(EngineConfig()),
    ]

    segments = transcribe_with_engine_chain(
        wav_path,
        windows,
        engines,
        max_attempts=2,
    )

    assert segments[0].text == "ok"
    # attempts should reflect both engines being tried
    assert segments[0].attempts == 2
