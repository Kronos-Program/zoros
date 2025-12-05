"""
Silero VAD integration for dictation service.

Spec: docs/specs/dictation_service_spec.md#configuration--presets
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import List

import numpy as np
import soundfile as sf

from backend.services.dictation_service.models import VADConfig

logger = logging.getLogger(__name__)

try:
    import torch
    import torchaudio
    _TORCH_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - optional dependency handling
    torch = None  # type: ignore
    torchaudio = None  # type: ignore
    _TORCH_IMPORT_ERROR = exc

SAMPLE_RATE = 16_000


@dataclass(frozen=True)
class SegmentWindow:
    """Simple container for start/end times (seconds)."""

    start_sec: float
    end_sec: float


@lru_cache(maxsize=1)
def _load_silero_model() -> tuple[torch.nn.Module, tuple]:
    """Load Silero VAD model and helper utilities (cached).

    Attempts to reuse a local cache first (SILERO_VAD_CACHE). If downloads are
    disallowed via SILERO_VAD_ALLOW_DOWNLOAD=0 and no cache is present, raises a
    RuntimeError with guidance.
    """
    if torch is None:
        raise RuntimeError(
            "Silero VAD requires torch/torchaudio; falling back to naive segmentation "
            f"(import error: {_TORCH_IMPORT_ERROR})"
        )

    cache_override = os.environ.get("SILERO_VAD_CACHE")
    allow_download = os.environ.get("SILERO_VAD_ALLOW_DOWNLOAD", "1") not in {"0", "false", "False"}

    def _try_load(repo_or_dir: str | Path) -> tuple[torch.nn.Module, tuple] | None:
        try:
            return torch.hub.load(
                repo_or_dir=str(repo_or_dir),
                model="silero_vad",
                trust_repo=True,
            )
        except Exception:
            return None

    # Prefer an explicit cache path if provided.
    if cache_override:
        cached = _try_load(cache_override)
        if cached:
            return cached
        if not allow_download:
            raise RuntimeError(
                "Silero VAD cache missing and downloads disabled (set SILERO_VAD_ALLOW_DOWNLOAD=1 "
                "or pre-populate SILERO_VAD_CACHE)."
            )

    # Fall back to the default hub cache; torch.hub will download once then reuse.
    cached = _try_load("snakers4/silero-vad")
    if cached:
        return cached

    if not allow_download:
        raise RuntimeError(
            "Silero VAD download blocked and no cached weights found. Enable SILERO_VAD_ALLOW_DOWNLOAD "
            "or provide SILERO_VAD_CACHE pointing to cached weights."
        )

    # Last attempt with download enabled (torch.hub handles caching).
    return torch.hub.load(
        repo_or_dir="snakers4/silero-vad",
        model="silero_vad",
        trust_repo=True,
    )


class SileroVADSegmenter:
    """Segmenter that produces speech windows using Silero VAD."""

    def __init__(self, config: VADConfig):
        self.config = config
        self.using_fallback = False
        self.fallback_reason: str | None = None
        if torch is None or torchaudio is None:
            self.using_fallback = True
            self.fallback_reason = (
                f"torch/torchaudio unavailable ({_TORCH_IMPORT_ERROR}); "
                "falling back to single-window segmentation"
            )
            self.model = None
            self.get_speech_timestamps = None
            return

        try:
            self.model, utils = _load_silero_model()
            (
                self.get_speech_timestamps,
                self.save_audio,
                self.read_audio,
                self.VADIterator,
                self.collect_chunks,
            ) = utils
        except Exception as exc:  # pragma: no cover - network/offline fallback
            self.using_fallback = True
            self.fallback_reason = str(exc)
            self.model = None
            self.get_speech_timestamps = None
            logger.warning("Silero VAD unavailable, using fallback segmentation: %s", exc)

    def segment(self, audio_path: str | Path) -> List[SegmentWindow]:
        """Return voice-activity windows for the provided audio file."""
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        if self.using_fallback or not self.get_speech_timestamps or not self.model:
            return self._fallback_segments(path)

        try:
            data, sr = sf.read(str(path), dtype="float32")
            if data.ndim > 1:
                data = np.mean(data, axis=1)
            waveform = torch.tensor(data, dtype=torch.float32)
            if sr != SAMPLE_RATE:
                waveform = torchaudio.functional.resample(
                    waveform.unsqueeze(0), sr, SAMPLE_RATE
                ).squeeze(0)

            timestamps = self.get_speech_timestamps(
                waveform,
                self.model,
                sampling_rate=SAMPLE_RATE,
                threshold=self.config.threshold,
                min_speech_duration_ms=self.config.min_speech_ms,
                max_speech_duration_s=self.config.max_speech_s,
                min_silence_duration_ms=self.config.min_silence_ms,
                speech_pad_ms=self.config.pad_ms,
            )

            segments = [
                SegmentWindow(
                    start_sec=ts["start"] / SAMPLE_RATE,
                    end_sec=ts["end"] / SAMPLE_RATE,
                )
                for ts in timestamps
            ]
            return segments
        except Exception as exc:  # pragma: no cover - resilience path
            self.using_fallback = True
            self.fallback_reason = f"silero-segmentation-failed: {exc}"
            logger.warning("Silero segmentation failed, falling back to naive window: %s", exc)
            return self._fallback_segments(path)

    def _fallback_segments(self, audio_path: Path) -> List[SegmentWindow]:
        """Return a single window spanning the whole file for resilience."""
        try:
            info = sf.info(str(audio_path))
            duration = info.frames / info.samplerate if info.samplerate else 0.0
        except Exception:
            duration = 0.0
        return [SegmentWindow(0.0, duration or 0.0)]
