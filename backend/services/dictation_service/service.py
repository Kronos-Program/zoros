"""
Application service coordinating dictation workflows.

Spec: docs/specs/dictation_service_spec.md#workflow
Tests: tests/services/test_dictation_service_router.py
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Callable, List, Optional
from uuid import UUID, uuid4

import soundfile as sf

from backend.services.dictation_service.engines import (
    EngineRegistry,
    TranscriptionEngine,
    transcribe_with_engine_chain,
)
from backend.services.dictation_service.models import (
    DictationJob,
    DictationJobCreate,
    DictationJobPatch,
    DictationStatus,
    VADConfig,
)
from backend.services.dictation_service.repository import DictationRepository
from backend.services.dictation_service.vad import SegmentWindow, SileroVADSegmenter

logger = logging.getLogger(__name__)


class DictationService:
    """High-level dictation orchestration entry point."""

    def __init__(
        self,
        repository: Optional[DictationRepository] = None,
        vad_segmenter_factory: Callable[[VADConfig], SileroVADSegmenter] | None = None,
        engine_registry: Optional[EngineRegistry] = None,
        audio_store: Path | str = Path("audio/intake"),
    ) -> None:
        self.repository = repository or DictationRepository()
        self.vad_segmenter_factory = vad_segmenter_factory or SileroVADSegmenter
        self.engine_registry = engine_registry or EngineRegistry()
        self.audio_store = Path(audio_store)
        self.audio_store.mkdir(parents=True, exist_ok=True)

    def create_job(self, payload: DictationJobCreate) -> DictationJob:
        """Create a new dictation job record."""
        job = DictationJob(
            id=uuid4(),
            audio_path=payload.audio_path,
            notes=payload.notes,
            engine_config=payload.engine_config,
            vad_config=payload.vad_config,
            metadata=payload.metadata,
        )
        if job.audio_path:
            job.audio_path = self._persist_audio(job.id, Path(job.audio_path))
            job.metadata.setdefault("source_audio_path", str(payload.audio_path))
        job.metadata.setdefault("created_at", job.created_at.isoformat())
        return self.repository.create_job(job)

    def start_job(self, job_id: UUID) -> DictationJob:
        """Transition a job into processing state and run transcription."""
        job = self._require_job(job_id)
        if not job.audio_path:
            raise ValueError("Dictation job missing audio_path")

        job.status = DictationStatus.PROCESSING
        job.metadata.setdefault("events", []).append(
            {"event": "job_started", "at": datetime.utcnow().isoformat()}
        )
        logger.info(
            "Starting dictation job %s (backend=%s, model=%s)",
            job.id,
            job.engine_config.backend,
            job.engine_config.model,
        )
        start_time = perf_counter()
        try:
            segmenter = self.vad_segmenter_factory(job.vad_config)
            segmenter_info: dict[str, object] = {
                "name": segmenter.__class__.__name__,
                "config": job.vad_config.model_dump(),
            }
            windows = segmenter.segment(job.audio_path)

            if not windows:
                duration = self._audio_duration_seconds(job.audio_path)
                windows = [SegmentWindow(0.0, duration)]
                segmenter_info["fallback_reason"] = "empty-window"

            if getattr(segmenter, "using_fallback", False):
                segmenter_info["fallback_reason"] = getattr(segmenter, "fallback_reason", "unknown")

            job.metadata["segment_windows"] = [
                {"start": window.start_sec, "end": window.end_sec} for window in windows
            ]
            job.metadata["segmenter"] = segmenter_info

            print("[service] job %s building engine chain" % job.id)
            engines, engine_errors = self.engine_registry.build_chain(job.engine_config)
            if engine_errors:
                job.metadata.setdefault("engine_errors", []).extend(engine_errors)
            if not engines:
                raise RuntimeError("No usable transcription engines available")

            job.metadata["engine_chain"] = [
                getattr(engine, "backend_name", engine.__class__.__name__) for engine in engines
            ]

            print("[service] job %s transcribe start" % job.id)
            job.segments = transcribe_with_engine_chain(
                job.audio_path,
                windows,
                engines,
                max_attempts=job.engine_config.max_attempts,
            )
            print("[service] job %s transcribe finished" % job.id)
            job.metadata["segment_count"] = len(job.segments)
            job.metadata["processing_seconds"] = round(perf_counter() - start_time, 3)
            job.status = DictationStatus.COMPLETED
            job.metadata["events"].append(
                {"event": "job_completed", "at": datetime.utcnow().isoformat()}
            )
            logger.info(
                "Completed dictation job %s in %.3fs with %d segments",
                job.id,
                job.metadata["processing_seconds"],
                len(job.segments),
            )
            return self.repository.update_job(job)
        except Exception as exc:  # pylint: disable=broad-except
            job.status = DictationStatus.FAILED
            job.metadata.setdefault("errors", []).append(str(exc))
            job.metadata["processing_seconds"] = round(perf_counter() - start_time, 3)
            job.metadata["events"].append(
                {"event": "job_failed", "at": datetime.utcnow().isoformat(), "error": str(exc)}
            )
            self.repository.update_job(job)
            logger.exception("Dictation job %s failed: %s", job.id, exc)
            raise

    def rerun_job(self, job_id: UUID) -> DictationJob:
        """Reset a job to pending."""
        job = self._require_job(job_id)
        if job.audio_path and not Path(job.audio_path).exists():
            raise FileNotFoundError(
                f"Audio for job {job_id} is missing at {job.audio_path}; cannot rerun."
            )
        job.status = DictationStatus.PENDING
        job.segments = []
        job.metadata["rerun_at"] = datetime.utcnow().isoformat()
        return self.repository.update_job(job)

    def get_job(self, job_id: UUID) -> DictationJob:
        """Fetch a job."""
        return self._require_job(job_id)

    def list_jobs(
        self,
        *,
        limit: int = 50,
        status: Optional[DictationStatus] = None,
    ) -> List[DictationJob]:
        """List jobs with optional filters."""
        return self.repository.list_jobs(limit=limit, status=status)

    def patch_job(self, job_id: UUID, payload: DictationJobPatch) -> DictationJob:
        """Update patchable job fields."""
        job = self._require_job(job_id)
        if payload.notes is not None:
            job.notes = payload.notes
        if payload.submitted is not None:
            job.submitted = payload.submitted
            if payload.submitted:
                job.metadata["submitted_at"] = datetime.utcnow().isoformat()
        if payload.metadata is not None:
            job.metadata.update(payload.metadata)
        return self.repository.update_job(job)

    def _require_job(self, job_id: UUID) -> DictationJob:
        job = self.repository.get_job(job_id)
        if not job:
            raise KeyError(f"Dictation job {job_id} not found")
        return job

    def _audio_duration_seconds(self, audio_path: str | Path) -> float:
        info = sf.info(str(audio_path))
        if info.frames == 0 or info.samplerate == 0:
            return 0.0
        return info.frames / info.samplerate

    def _persist_audio(self, job_id: UUID, source_path: Path) -> str:
        """Copy audio to the managed store to prevent loss."""
        if not source_path.exists():
            raise FileNotFoundError(f"Audio file not found: {source_path}")
        dest = self.audio_store / f"{job_id}{source_path.suffix or '.wav'}"
        if dest.resolve() == source_path.resolve():
            return str(dest)
        shutil.copy2(source_path, dest)
        return str(dest)
