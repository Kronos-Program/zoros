"""
Controller and adapters for the intake UI to keep PySide concerns separate.

Spec: docs/specs/dictation_service_spec.md#workflow
Architecture: docs/zoros_architecture.md#architecture-principles
Tasks: docs/tasks/TASK-091_dictation-module-modernization.md, docs/tasks/TASK-092_dictation-service-hardening.md
Tests: tests/interfaces/test_intake_controller.py
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Protocol
from uuid import uuid4

from backend.interfaces.intake.service_client import DictationServiceClient
from backend.services.dictation_service.models import DictationJob

logger = logging.getLogger(__name__)


class RecorderLike(Protocol):
    """Minimal recorder interface the controller depends on."""

    def start(self, device: Optional[int] = None) -> None: ...

    def stop(self, path: Path, keep_stream: bool = False) -> None: ...

    @property
    def level(self) -> float: ...


class PersistFunc(Protocol):
    """Signature for persisting intake rows."""

    def __call__(
        self,
        content: str,
        audio_path: Optional[str],
        correction: Optional[str] = None,
        fiber_type: str = "dictation",
        db: Path | str = Path("zoros_intake.db"),
        *,
        fiber_id: str | None = None,
        submitted: bool = True,
    ) -> str: ...


@dataclass
class TranscriptionOutcome:
    """Outcome payload for UI consumption."""

    transcript: str
    job: DictationJob
    saved_audio_path: Optional[Path]
    fiber_id: Optional[str]
    metadata: Dict[str, Any]


class RecordingAdapter:
    """Wraps recording concerns so the controller can be UI-agnostic."""

    def __init__(self, recorder: RecorderLike, temp_dir: Optional[Path] = None) -> None:
        self.recorder = recorder
        self.temp_dir = temp_dir or Path(tempfile.gettempdir())

    def start(self, device: Optional[int] = None) -> None:
        self.recorder.start(device=device)

    def stop(self, *, keep_stream: bool = False) -> Path:
        temp_path = self.temp_dir / f"tmp_{uuid4()}.wav"
        self.recorder.stop(temp_path, keep_stream=keep_stream)
        return temp_path

    @property
    def level(self) -> float:
        return self.recorder.level


class ServiceAdapter:
    """Thin wrapper around the dictation service client."""

    def __init__(self, client: DictationServiceClient) -> None:
        self.client = client

    def transcribe(
        self,
        audio_path: Path,
        *,
        notes: str | None = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DictationJob:
        return self.client.transcribe(audio_path, notes=notes, metadata=metadata or {})


class PersistenceAdapter:
    """Persistence boundary for intake fibers."""

    def __init__(
        self,
        persist_fn: PersistFunc,
        *,
        db_path: Path,
        expose_data: bool = False,
    ) -> None:
        self.persist_fn = persist_fn
        self.db_path = Path(db_path)
        self.expose_data = expose_data

    def persist(
        self,
        *,
        transcript: str,
        audio_path: Optional[Path],
        submitted: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> tuple[str, Optional[Path]]:
        fiber_id = self.persist_fn(
            transcript,
            str(audio_path) if audio_path else None,
            correction=transcript,
            fiber_type="dictation",
            db=self.db_path,
            fiber_id=None,
            submitted=submitted,
        )
        # Placeholder for expose_data flow if needed later.
        return fiber_id, audio_path


class IntakeController:
    """UI-agnostic controller coordinating recording, service, and persistence."""

    def __init__(
        self,
        *,
        recording: RecordingAdapter,
        service: ServiceAdapter,
        persistence: PersistenceAdapter,
    ) -> None:
        self.recording = recording
        self.service = service
        self.persistence = persistence

    def start_recording(self, device: Optional[int] = None) -> None:
        self.recording.start(device=device)

    def stop_and_transcribe(
        self,
        *,
        notes: Optional[str],
        metadata: Optional[Dict[str, Any]] = None,
        keep_stream: bool = False,
    ) -> TranscriptionOutcome:
        print("[controller] stop called (keep_stream=%s)" % keep_stream)
        audio_path = self.recording.stop(keep_stream=keep_stream)
        print("[controller] audio written to", audio_path)
        return self.transcribe_audio(audio_path=audio_path, notes=notes, metadata=metadata)

    def transcribe_audio(
        self,
        *,
        audio_path: Path,
        notes: Optional[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TranscriptionOutcome:
        base_metadata = metadata.copy() if metadata else {}
        print("[controller] transcribe start", audio_path)
        job = self.service.transcribe(audio_path, notes=notes, metadata=base_metadata)
        print("[controller] transcribe finished status=%s segments=%d" % (job.status, len(job.segments)))
        transcript = "\n".join(seg.text for seg in job.segments if seg.text).strip()
        fiber_id, saved_path = self.persistence.persist(
            transcript=transcript,
            audio_path=Path(job.audio_path) if job.audio_path else audio_path,
            submitted=False,
            metadata=job.metadata,
        )
        merged_metadata = {}
        merged_metadata.update(base_metadata)
        merged_metadata.update(job.metadata or {})
        merged_metadata["fiber_id"] = fiber_id
        logger.info(
            "Dictation job %s persisted (fiber_id=%s, segments=%d)",
            job.id,
            fiber_id,
            len(job.segments),
        )
        return TranscriptionOutcome(
            transcript=transcript,
            job=job,
            saved_audio_path=saved_path,
            fiber_id=fiber_id,
            metadata=merged_metadata,
        )
