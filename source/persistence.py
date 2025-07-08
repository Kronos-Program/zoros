# See architecture: docs/zoros_architecture.md#component-overview
from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict



def _base_dir() -> Path:
    """Return base data directory, respecting the DATA_DIR environment variable."""
    return Path(os.getenv("DATA_DIR", "data"))


def _db_path() -> Path:
    return _base_dir() / "fibers.db"


def _fiber_dir() -> Path:
    return _base_dir() / "fibers"


def _thread_dir() -> Path:
    return _base_dir() / "threads"


def _ui_state_dir() -> Path:
    return _base_dir() / "ui_state"


def base_dir() -> Path:
    """Public helper returning the current DATA_DIR path."""
    return _base_dir()


BASE_DIR = base_dir()


def _ensure_db() -> None:
    db_path = _db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS fibers (fiber_id TEXT PRIMARY KEY, type TEXT, content TEXT, source TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS threads (thread_id TEXT PRIMARY KEY, fiber_ids TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, name TEXT, gist TEXT, status TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS task_warp_fibers (id TEXT PRIMARY KEY, task_id TEXT, action TEXT, timestamp TEXT, metadata TEXT)"
    )
    conn.close()


@dataclass
class Fiber:
    fiber_id: str
    type: str
    content: str
    source: str


def resolveFiber(fiber: Fiber) -> Fiber:
    _ensure_db()
    conn = sqlite3.connect(_db_path())
    cur = conn.execute("SELECT fiber_id FROM fibers WHERE fiber_id=?", (fiber.fiber_id,))
    if not cur.fetchone():
        conn.execute(
            "INSERT INTO fibers (fiber_id, type, content, source) VALUES (?,?,?,?)",
            (fiber.fiber_id, fiber.type, fiber.content, fiber.source),
        )
        conn.commit()
        fiber_dir = _fiber_dir()
        fiber_dir.mkdir(parents=True, exist_ok=True)
        (fiber_dir / f"{fiber.fiber_id}.json").write_text(json.dumps(asdict(fiber)))
    conn.close()
    return fiber


def load_fiber(fiber_id: str) -> Dict:
    return json.loads((_fiber_dir() / f"{fiber_id}.json").read_text())


def resolveThread(thread_id: str, fiber_ids: List[str]) -> Dict:
    _ensure_db()
    conn = sqlite3.connect(_db_path())
    data = json.dumps(fiber_ids)
    cur = conn.execute("SELECT thread_id FROM threads WHERE thread_id=?", (thread_id,))
    if cur.fetchone():
        conn.execute("UPDATE threads SET fiber_ids=? WHERE thread_id=?", (data, thread_id))
    else:
        conn.execute("INSERT INTO threads (thread_id, fiber_ids) VALUES (?,?)", (thread_id, data))
    conn.commit()
    conn.close()
    thread_dir = _thread_dir()
    thread_dir.mkdir(parents=True, exist_ok=True)
    thread = {"thread_id": thread_id, "fiber_ids": fiber_ids}
    (thread_dir / f"{thread_id}.json").write_text(json.dumps(thread))
    return thread


def load_thread(thread_id: str) -> Dict:
    return json.loads((_thread_dir() / f"{thread_id}.json").read_text())


def save_fiber_metadata(fiber_id: str, metadata: Dict) -> None:
    """Persist ``metadata`` for ``fiber_id`` alongside the fiber JSON."""
    path = _fiber_dir() / f"{fiber_id}_meta.json"
    path.write_text(json.dumps(metadata))
