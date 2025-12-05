"""
Helper for running the local dictation service from the PySide intake UI.

Spec: docs/specs/dictation_service_spec.md
"""

from __future__ import annotations

from pathlib import Path

from backend.services.dictation_service.models import (
    DictationJob,
    DictationJobCreate,
    EngineConfig,
    VADConfig,
)
from backend.services.dictation_service.repository import DictationRepository
from backend.services.dictation_service.service import DictationService


class DictationServiceClient:
    """Thin wrapper around :class:`DictationService` for UI usage."""

    def __init__(
        self,
        *,
        db_path: Path | str = Path("zoros_intake.db"),
        engine_backend: str = "MLXWhisper",
        engine_model: str = "large-v3-turbo",
        vad_config: VADConfig | None = None,
    ) -> None:
        self.repository = DictationRepository(db_path=db_path)
        self.service = DictationService(repository=self.repository)
        self.engine_config = EngineConfig(backend=engine_backend, model=engine_model)
        self.vad_config = vad_config or VADConfig()

    def configure(
        self,
        *,
        backend: str | None = None,
        model: str | None = None,
        vad_config: VADConfig | None = None,
        fallback_backends: list[str] | None = None,
        max_attempts: int | None = None,
    ) -> None:
        """Update engine/VAD preferences."""
        if backend:
            self.engine_config.backend = backend
        if model:
            self.engine_config.model = model
        if vad_config:
            self.vad_config = vad_config
        if fallback_backends is not None:
            self.engine_config.fallback_backends = fallback_backends
        if max_attempts is not None:
            self.engine_config.max_attempts = max_attempts

    def transcribe(
        self,
        audio_path: str | Path,
        *,
        notes: str | None = None,
        metadata: dict | None = None,
    ) -> DictationJob:
        """Run the dictation service on ``audio_path`` and return the completed job."""
        print(f"[service_client] transcribe audio_path={audio_path}")
        # Ensure we always have usable fallbacks if the preferred backend is unavailable
        if not self.engine_config.fallback_backends:
            self.engine_config.fallback_backends = ["faster_whisper", "mock"]
        payload = DictationJobCreate(
            audio_path=str(audio_path),
            engine_config=self.engine_config,
            vad_config=self.vad_config,
            notes=notes,
            metadata=metadata or {},
        )
        job = self.service.create_job(payload)
        result = self.service.start_job(job.id)
        print(f"[service_client] transcribe done status={result.status}")
        return result

    def warm_engine(self) -> None:
        """Warm the current engine chain without persisting a job."""
        # Build chain and trigger warmup
        engines, _errors = self.service.engine_registry.build_chain(self.engine_config)
        for engine in engines:
            try:
                engine.warmup()
            except Exception:
                # Warmup failures should not break warm pass
                continue

    def reset_engines(self) -> None:
        """Clear cached engines so the next call reloads models (acts as unmount)."""
        if hasattr(self.service.engine_registry, "_cache"):
            self.service.engine_registry._cache.clear()  # type: ignore[attr-defined]
