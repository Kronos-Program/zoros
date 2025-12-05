"""
FastAPI router for dictation service endpoints.

Spec: docs/specs/dictation_service_spec.md#api-surface
Tests: tests/services/test_dictation_service_router.py
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.services.dictation_service.models import (
    DictationJob,
    DictationJobCreate,
    DictationJobPatch,
    DictationStatus,
)
from backend.services.dictation_service.service import DictationService

router = APIRouter(prefix="/api/dictations", tags=["dictations"])
_service = DictationService()


def get_dictation_service() -> DictationService:
    """Dependency hook for overriding in tests."""
    return _service


@router.post("", response_model=DictationJob, status_code=status.HTTP_201_CREATED)
def create_dictation_job(
    payload: DictationJobCreate,
    service: DictationService = Depends(get_dictation_service),
) -> DictationJob:
    """Create a new dictation job."""
    return service.create_job(payload)


@router.get("", response_model=List[DictationJob])
def list_dictation_jobs(
    limit: int = Query(50, ge=1, le=200),
    status_filter: Optional[DictationStatus] = Query(None, alias="status"),
    service: DictationService = Depends(get_dictation_service),
) -> List[DictationJob]:
    """List dictation jobs."""
    return service.list_jobs(limit=limit, status=status_filter)


@router.get("/{job_id}", response_model=DictationJob)
def get_dictation_job(
    job_id: UUID,
    service: DictationService = Depends(get_dictation_service),
) -> DictationJob:
    """Fetch a dictation job by ID."""
    try:
        return service.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{job_id}/start", response_model=DictationJob)
def start_dictation_job(
    job_id: UUID,
    service: DictationService = Depends(get_dictation_service),
) -> DictationJob:
    """Start transcription for a job."""
    try:
        return service.start_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{job_id}/rerun", response_model=DictationJob)
def rerun_dictation_job(
    job_id: UUID,
    service: DictationService = Depends(get_dictation_service),
) -> DictationJob:
    """Reset and rerun a job."""
    try:
        return service.rerun_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/{job_id}", response_model=DictationJob)
def patch_dictation_job(
    job_id: UUID,
    payload: DictationJobPatch,
    service: DictationService = Depends(get_dictation_service),
) -> DictationJob:
    """Patch job metadata."""
    try:
        return service.patch_job(job_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


