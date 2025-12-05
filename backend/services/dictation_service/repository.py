"""
SQLite-backed persistence for dictation jobs.

Spec: docs/specs/dictation_service_spec.md#persistence--data-flow
Tests: tests/services/test_dictation_service_router.py
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional
from uuid import UUID

from backend.services.dictation_service.models import (
    DictationJob,
    DictationStatus,
    EngineConfig,
    Segment,
    VADConfig,
)


class DictationRepository:
    """Lightweight repository around `zoros_intake.db`."""

    def __init__(self, db_path: Path | str = Path("zoros_intake.db")) -> None:
        self.db_path = Path(db_path)
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dictation_jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    audio_path TEXT,
                    notes TEXT,
                    engine_config TEXT,
                    vad_config TEXT,
                    segments TEXT,
                    metadata TEXT,
                    intake_id TEXT,
                    submitted INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def create_job(self, job: DictationJob) -> DictationJob:
        """Insert a new dictation job."""
        self._execute(
            """
            INSERT INTO dictation_jobs (
                id, status, audio_path, notes, engine_config, vad_config,
                segments, metadata, intake_id, submitted, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._serialize_job(job),
        )
        return job

    def update_job(self, job: DictationJob) -> DictationJob:
        """Persist updates to an existing job."""
        job.updated_at = datetime.utcnow()
        self._execute(
            """
            UPDATE dictation_jobs
            SET status=?, audio_path=?, notes=?, engine_config=?, vad_config=?,
                segments=?, metadata=?, intake_id=?, submitted=?, updated_at=?
            WHERE id=?
            """,
            (
                job.status.value,
                job.audio_path,
                job.notes,
                json.dumps(job.engine_config.model_dump()),
                json.dumps(job.vad_config.model_dump()),
                json.dumps([segment.model_dump() for segment in job.segments]),
                json.dumps(job.metadata),
                job.intake_id,
                1 if job.submitted else 0,
                job.updated_at.isoformat(),
                str(job.id),
            ),
        )
        return job

    def get_job(self, job_id: UUID) -> Optional[DictationJob]:
        """Retrieve a single job by ID."""
        rows = self._query(
            "SELECT * FROM dictation_jobs WHERE id = ?",
            (str(job_id),),
        )
        if not rows:
            return None
        return self._row_to_job(rows[0])

    def list_jobs(
        self,
        *,
        limit: int = 50,
        status: Optional[DictationStatus] = None,
    ) -> List[DictationJob]:
        """List jobs with optional status filter."""
        query = "SELECT * FROM dictation_jobs"
        params: list = []
        if status:
            query += " WHERE status = ?"
            params.append(status.value)
        query += " ORDER BY datetime(created_at) DESC LIMIT ?"
        params.append(limit)
        rows = self._query(query, tuple(params))
        return [self._row_to_job(row) for row in rows]

    def _row_to_job(self, row: sqlite3.Row) -> DictationJob:
        """Convert raw DB row to DictationJob."""
        engine_cfg = EngineConfig(**json.loads(row["engine_config"]))
        vad_cfg = VADConfig(**json.loads(row["vad_config"]))
        segments = [Segment(**segment) for segment in json.loads(row["segments"] or "[]")]
        metadata = json.loads(row["metadata"] or "{}")
        return DictationJob(
            id=UUID(row["id"]),
            status=DictationStatus(row["status"]),
            audio_path=row["audio_path"],
            notes=row["notes"],
            engine_config=engine_cfg,
            vad_config=vad_cfg,
            segments=segments,
            metadata=metadata,
            intake_id=row["intake_id"],
            submitted=bool(row["submitted"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _serialize_job(self, job: DictationJob) -> Iterable:
        """Serialize job for inserts."""
        return (
            str(job.id),
            job.status.value,
            job.audio_path,
            job.notes,
            json.dumps(job.engine_config.model_dump()),
            json.dumps(job.vad_config.model_dump()),
            json.dumps([segment.model_dump() for segment in job.segments]),
            json.dumps(job.metadata),
            job.intake_id,
            1 if job.submitted else 0,
            job.created_at.isoformat(),
            job.updated_at.isoformat(),
        )

    def _execute(self, query: str, params: Iterable) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(query, tuple(params))
            conn.commit()

    def _query(self, query: str, params: Iterable = ()) -> List[sqlite3.Row]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, tuple(params))
            return cursor.fetchall()


