"""
Domain models for the dictation service.

Spec: docs/specs/dictation_service_spec.md#data-models
Tests: tests/services/test_dictation_service_router.py
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DictationStatus(str, Enum):
    """Lifecycle states for dictation jobs."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class EngineConfig(BaseModel):
    """User-selected transcription backend settings."""

    backend: str = "mlx_whisper"
    model: str = "large-v3"
    device: str = "auto"
    compute_type: str = "default"
    language: Optional[str] = None
    beam_size: int = 5
    temperature: float = 0.0
    fallback_backends: List[str] = Field(
        default_factory=lambda: ["faster_whisper", "mock"],
        description="Ordered list of fallback backends to try when the primary fails.",
    )
    max_attempts: int = Field(
        default=2,
        ge=1,
        description="Maximum attempts per segment across primary + fallbacks.",
    )


class VADConfig(BaseModel):
    """Silero VAD tuning parameters."""

    preset: str = "balanced"
    threshold: float = 0.5
    min_speech_ms: int = 300
    max_speech_s: float = 30.0
    min_silence_ms: int = 1200
    pad_ms: int = 300


class Segment(BaseModel):
    """Represents a single speech segment."""

    start_sec: float
    end_sec: float
    text: Optional[str] = None
    error: Optional[str] = None
    attempts: int = 0


class DictationJob(BaseModel):
    """Server-side representation of a dictation job."""

    id: UUID
    status: DictationStatus = DictationStatus.PENDING
    audio_path: Optional[str] = None
    notes: Optional[str] = None
    engine_config: EngineConfig = Field(default_factory=EngineConfig)
    vad_config: VADConfig = Field(default_factory=VADConfig)
    segments: List[Segment] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    intake_id: Optional[str] = None
    submitted: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DictationJobCreate(BaseModel):
    """Payload for creating new dictation jobs."""

    audio_path: Optional[str] = None
    notes: Optional[str] = None
    engine_config: EngineConfig = Field(default_factory=EngineConfig)
    vad_config: VADConfig = Field(default_factory=VADConfig)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DictationJobPatch(BaseModel):
    """Subset of fields that can be updated via PATCH."""

    notes: Optional[str] = None
    submitted: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None
