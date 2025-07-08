from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from source.core.models.fiber import Fiber


def _db_path() -> Path:
    return Path(os.getenv("DATA_DIR", "data")) / "fibers.db"


def _ensure_tables() -> None:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fibers (
                id TEXT PRIMARY KEY,
                content TEXT,
                tags TEXT,
                created_at TEXT,
                source TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS routine_import_fibers (
                id TEXT PRIMARY KEY,
                source_path TEXT,
                format TEXT,
                created_at TEXT
            )
            """
        )
        conn.commit()


class RoutineImportFiber(Fiber):
    """Fiber capturing provenance for an imported routine."""

    source_path: str
    format: str


def save_routine_import(path: Path, fmt: str) -> RoutineImportFiber:
    """Persist a RoutineImportFiber and return it."""
    _ensure_tables()
    fiber = RoutineImportFiber(
        id=uuid4(),
        content=f"Imported {path.name}",
        type="text",
        metadata={"format": fmt},
        revision_count=0,
        created_at=datetime.utcnow(),
        source="import-flow",
        source_path=str(path),
        format=fmt,
    )
    with sqlite3.connect(_db_path()) as conn:
        conn.execute(
            "INSERT INTO fibers (id, content, tags, created_at, source) VALUES (?,?,?,?,?)",
            (
                str(fiber.id),
                fiber.content,
                json.dumps(["routine_import"]),
                fiber.created_at.isoformat(),
                fiber.source,
            ),
        )
        conn.execute(
            "INSERT INTO routine_import_fibers (id, source_path, format, created_at) VALUES (?,?,?,?)",
            (
                str(fiber.id),
                fiber.source_path,
                fiber.format,
                fiber.created_at.isoformat(),
            ),
        )
        conn.commit()
    return fiber
