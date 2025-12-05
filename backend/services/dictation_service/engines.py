"""
Transcription engine adapters for the dictation service.

Spec: docs/specs/dictation_service_spec.md#components
"""

from __future__ import annotations

import logging
import os
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, List, Tuple

import numpy as np
import soundfile as sf

from backend.services.dictation.registry import BackendRegistry
from backend.services.dictation_service.models import EngineConfig, Segment
from backend.services.dictation_service.vad import SegmentWindow

logger = logging.getLogger(__name__)


class TranscriptionEngine(ABC):
    """Base class for transcription engines."""

    def __init__(self, config: EngineConfig):
        self.config = config
        self._warmed = False

    @abstractmethod
    def transcribe_segments(
        self,
        audio_path: str | Path,
        windows: List[SegmentWindow],
    ) -> List[Segment]:
        """Transcribe provided audio windows into `Segment` objects."""

    def warmup(self) -> None:
        """Optional warm-up hook implemented by subclasses."""
        self._warmed = True


def _load_mono_audio(audio_path: str | Path) -> tuple[np.ndarray, int]:
    path = Path(audio_path)
    audio, sr = sf.read(str(path), dtype="float32")
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)
    return audio, sr


def _transcribe_with_backends(
    backends: List[Tuple[str, Callable[[str], str]]],
    audio: np.ndarray,
    samplerate: int,
    windows: List[SegmentWindow],
    max_attempts: int,
) -> List[Segment]:
    segments: List[Segment] = []
    for window in windows:
        start_sample = max(int(window.start_sec * samplerate), 0)
        end_sample = min(int(window.end_sec * samplerate), len(audio))
        if end_sample <= start_sample:
            segments.append(
                Segment(
                    start_sec=window.start_sec,
                    end_sec=window.end_sec,
                    text="",
                    error="empty-window",
                    attempts=1,
                )
            )
            continue

        chunk = audio[start_sample:end_sample]
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            sf.write(tmp.name, chunk, samplerate)
            temp_path = tmp.name
        try:
            attempts = 0
            transcript = ""
            errors: list[str] = []
            for name, backend_transcribe in backends:
                if attempts >= max_attempts:
                    break
                attempts += 1
                try:
                    transcript = backend_transcribe(temp_path).strip()
                    if transcript:
                        break
                except Exception as exc:  # pylint: disable=broad-except
                    errors.append(f"{name}: {exc}")
            segments.append(
                Segment(
                    start_sec=window.start_sec,
                    end_sec=window.end_sec,
                    text=transcript,
                    error="; ".join(errors) if transcript == "" and errors else None,
                    attempts=attempts,
                )
            )
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass
    return segments


class DictationBackendEngine(TranscriptionEngine):
    """Engine that wraps existing dictation backends from the registry."""

    def __init__(
        self,
        config: EngineConfig,
        backend_factory: Callable[[str, str], object],
        backend_name: str,
    ):
        super().__init__(config)
        backend_obj = backend_factory(backend_name, config.model)
        # Some backends are modules with a `WhisperBackend`-style class attribute; unwrap if needed.
        if hasattr(backend_obj, "transcribe"):
            self.backend = backend_obj
        elif hasattr(backend_obj, "WhisperBackend"):
            self.backend = backend_obj.WhisperBackend(config.model)  # type: ignore[attr-defined]
        else:
            raise TypeError(f"Backend {backend_name} did not provide a callable transcribe")
        self.backend_name = backend_name
        self._backend_fn: Callable[[str], str] = getattr(self.backend, "transcribe")

    def warmup(self) -> None:
        if self._warmed:
            return
        silence = np.zeros(8000, dtype=np.float32)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            sf.write(tmp.name, silence, 16_000)
            temp_path = tmp.name
        try:
            self._backend_fn(temp_path)
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass
        super().warmup()

    def transcribe_segments(
        self,
        audio_path: str | Path,
        windows: List[SegmentWindow],
    ) -> List[Segment]:
        audio, sr = _load_mono_audio(audio_path)
        primary = [(self.backend_name, self._backend_fn)]
        return _transcribe_with_backends(
            primary,
            audio,
            sr,
            windows,
            max_attempts=self.config.max_attempts,
        )


class EngineRegistry:
    """Registry/factory for available transcription engines."""

    def __init__(self, backend_registry: BackendRegistry | None = None):
        self.backend_registry = backend_registry or BackendRegistry()
        self._cache: dict[tuple[str, str], TranscriptionEngine] = {}
        self._aliases: dict[str, str] = {
            "mlx_whisper": "MLXWhisper",
            "faster_whisper": "FasterWhisper",
            "whisper_cpp": "WhisperCPP",
            "mock": "Mock",
        }

    def create(self, config: EngineConfig) -> TranscriptionEngine:
        key = (config.backend, config.model)
        if key in self._cache:
            return self._cache[key]
        registry_name = self._aliases.get(config.backend, config.backend)
        backend_cls = self.backend_registry.get_backend_class(registry_name)
        engine = DictationBackendEngine(
            config=config,
            backend_factory=lambda name, model: backend_cls(model),
            backend_name=registry_name,
        )
        try:
            engine.warmup()
        except Exception:
            # Warm-up failures should not prevent the engine from being returned;
            # the service will handle retries/fallbacks.
            pass
        self._cache[key] = engine
        return engine

    def create_for_backend(self, backend: str, model: str) -> TranscriptionEngine:
        """Create an engine for a specific backend/model pair."""
        temp_config = EngineConfig(backend=backend, model=model)
        return self.create(temp_config)

    def build_chain(self, config: EngineConfig) -> tuple[list[TranscriptionEngine], list[str]]:
        """Return an ordered list of available engines and any errors encountered."""
        errors: list[str] = []
        engines: list[TranscriptionEngine] = []

        # Preserve caller ordering; caller controls fallback list (including mock if desired).
        candidates = [config.backend, *config.fallback_backends]
        seen: set[str] = set()
        for backend_name in candidates:
            if backend_name in seen:
                continue
            seen.add(backend_name)
            try:
                effective_config = config.model_copy(update={"backend": backend_name})
                engines.append(self.create(effective_config))
            except Exception as exc:  # pylint: disable=broad-except
                errors.append(f"{backend_name}: {exc}")
                logger.debug("Engine %s unavailable: %s", backend_name, exc)
        return engines, errors


def transcribe_with_engine_chain(
    audio_path: str | Path,
    windows: List[SegmentWindow],
    engines: List[TranscriptionEngine],
    max_attempts: int,
) -> List[Segment]:
    """Transcribe windows using a prioritized list of engines with fallback."""
    audio, sr = _load_mono_audio(audio_path)
    backend_fns: List[Tuple[str, Callable[[str], str]]] = []
    for engine in engines:
        name = getattr(engine, "backend_name", engine.__class__.__name__)
        fn = getattr(engine, "_backend_fn", None) or getattr(engine, "transcribe", None)
        if fn:
            backend_fns.append((name, fn))
        else:
            logger.debug("Engine %s missing callable transcribe method; skipping", name)
    if not backend_fns:
        raise RuntimeError("No transcription engines provided")
    return _transcribe_with_backends(backend_fns, audio, sr, windows, max_attempts=max_attempts)
