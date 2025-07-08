from __future__ import annotations

from datetime import datetime
import json
import os
import sqlite3
from pathlib import Path
from uuid import uuid4

from source.core.models.fiber import Fiber


def _db_path() -> Path:
    return Path(os.getenv("DATA_DIR", "data")) / "fibers.db"


def _ensure_task_warp_table() -> None:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_warp_fibers (
                id TEXT PRIMARY KEY,
                task_id TEXT,
                action TEXT,
                timestamp TEXT,
                metadata TEXT
            )
            """
        )
        conn.commit()


class TaskWarpFiber(Fiber):
    """Fiber capturing lifecycle events for a task."""

    task_id: str | None = None
    action: str | None = None

    def __init__(self, task_id: str, action: str, metadata: dict) -> None:
        super().__init__(
            id=uuid4(),
            content=f"TASK {task_id} {action}",
            type="text",
            metadata=metadata,
            revision_count=0,
            created_at=datetime.utcnow(),
            source="taskwarp",
        )
        self.task_id = task_id
        self.action = action

    def save(self) -> None:
        """Persist this warp fiber to the task_warp_fibers table."""
        _ensure_task_warp_table()
        with sqlite3.connect(_db_path()) as conn:
            conn.execute(
                "INSERT INTO task_warp_fibers (id, task_id, action, timestamp, metadata) VALUES (?,?,?,?,?)",
                (
                    str(self.id),
                    self.task_id,
                    self.action,
                    self.created_at.isoformat(),
                    json.dumps(self.metadata),
                ),
            )
            conn.commit()


def get_task_warp_fibers(task_id: str) -> list[dict]:
    """Return all TaskWarpFiber rows for a task ordered by timestamp."""
    _ensure_task_warp_table()
    with sqlite3.connect(_db_path()) as conn:
        cur = conn.execute(
            "SELECT id, task_id, action, timestamp, metadata FROM task_warp_fibers WHERE task_id=? ORDER BY timestamp",
            (task_id,),
        )
        rows = [
            {
                "id": rid,
                "task_id": tid,
                "action": action,
                "timestamp": ts,
                "metadata": json.loads(meta) if meta else {},
            }
            for rid, tid, action, ts, meta in cur.fetchall()
        ]
    return rows

def _ensure_lint_table() -> None:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fiber_lint (
                id TEXT PRIMARY KEY,
                fiber_path TEXT,
                issues TEXT,
                fixed INTEGER,
                timestamp TEXT
            )
            """
        )
        conn.commit()


class FiberLintFiber(Fiber):
    """Record of lint issues found in a fiber file."""

    fiber_path: str
    issues: list[str]
    fixed: bool = False

    def save(self) -> None:
        _ensure_lint_table()
        with sqlite3.connect(_db_path()) as conn:
            conn.execute(
                "INSERT INTO fiber_lint (id, fiber_path, issues, fixed, timestamp) VALUES (?,?,?,?,?)",
                (
                    str(self.id),
                    self.fiber_path,
                    json.dumps(self.issues),
                    int(self.fixed),
                    self.created_at.isoformat(),
                ),
            )
            conn.commit()
