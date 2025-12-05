"""
Persistence helpers for intake fibers.

Spec: docs/requirements/dictation_requirements.md#data-model
Tasks: docs/tasks/TASK-091_dictation-module-modernization.md
Tests: tests/dictation/test_intake_pipeline.py
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

from backend.core.models.fiber import Fiber

DB_PATH = Path("zoros_intake.db")


def _ensure_db(db: Path = DB_PATH) -> None:
    """Create the intake table if it does not exist."""
    with sqlite3.connect(db) as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='intake'")
        table_exists = cursor.fetchone() is not None

        if not table_exists:
            conn.execute(
                """
                CREATE TABLE intake (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT,
                    content TEXT,
                    audio_path TEXT,
                    correction TEXT,
                    fiber_type TEXT,
                    submitted INTEGER DEFAULT 1
                )
                """
            )
        else:
            cursor = conn.execute("PRAGMA table_info(intake)")
            columns = [column[1] for column in cursor.fetchall()]

            if "correction" not in columns:
                conn.execute("ALTER TABLE intake ADD COLUMN correction TEXT")

            if "fiber_type" not in columns:
                conn.execute("ALTER TABLE intake ADD COLUMN fiber_type TEXT")

            if "submitted" not in columns:
                conn.execute("ALTER TABLE intake ADD COLUMN submitted INTEGER DEFAULT 1")

        conn.commit()


def insert_intake(
    content: str,
    audio_path: Optional[str],
    correction: Optional[str] = None,
    fiber_type: str = "dictation",
    db: Path = DB_PATH,
    *,
    fiber_id: str | None = None,
    submitted: bool = True,
) -> str:
    """Insert a new intake fiber row and return its ID."""
    _ensure_db(db)
    fid = fiber_id or str(uuid.uuid4())
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO intake (id, timestamp, content, audio_path, correction, fiber_type, submitted) VALUES (?,?,?,?,?,?,?)",
            (
                fid,
                datetime.utcnow().isoformat(),
                content,
                audio_path,
                correction,
                fiber_type,
                1 if submitted else 0,
            ),
        )
        conn.commit()
    return fid


def create_fiber_from_intake(fid: str, db: Path = DB_PATH) -> Fiber:
    """Return a :class:`Fiber` object for the given intake record."""
    _ensure_db(db)
    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT id, content, audio_path FROM intake WHERE id = ?",
            (fid,),
        ).fetchone()
    if not row:
        raise KeyError(fid)
    fiber_type = "audio" if row[2] else "text"
    return Fiber(
        id=UUID(row[0]),
        content=row[1],
        type=fiber_type,
        metadata={},
        revision_count=0,
        created_at=datetime.utcnow(),
        source="intake",
    )


def list_intake_records(db: Path = DB_PATH) -> list[dict]:
    """Return intake records for navigation."""
    _ensure_db(db)
    with sqlite3.connect(db) as conn:
        cursor = conn.execute(
            """
            SELECT id, timestamp, content, audio_path, correction, fiber_type, submitted
            FROM intake
            ORDER BY timestamp DESC
            """
        )
        return [
            {
                "id": row[0],
                "timestamp": row[1],
                "content": row[2],
                "audio_path": row[3],
                "correction": row[4],
                "fiber_type": row[5] or "dictation",
                "submitted": bool(row[6]),
            }
            for row in cursor.fetchall()
        ]


def update_intake_submission(
    fid: str,
    *,
    content: str,
    correction: str,
    submitted: bool,
    db: Path = DB_PATH,
) -> None:
    """Update an intake row with new content/correction/submitted flag."""
    _ensure_db(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            "UPDATE intake SET content = ?, correction = ?, submitted = ? WHERE id = ?",
            (content, correction, 1 if submitted else 0, fid),
        )
        conn.commit()


__all__ = [
    "DB_PATH",
    "_ensure_db",
    "insert_intake",
    "create_fiber_from_intake",
    "list_intake_records",
    "update_intake_submission",
]
