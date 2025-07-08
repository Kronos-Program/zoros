from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional
from uuid import uuid4


def _db_path() -> Path:
    return Path(os.getenv("DATA_DIR", "data")) / "fibers.db"


@dataclass
class RegistryTask:
    """Simple normalized task representation."""

    id: str
    title: str
    context: str = ""
    project: str = ""
    created_at: datetime | None = None
    due_date: str | None = None
    status: str = "new"
    gist: str = ""


def parse_raw_tasks(text: str, context: str = "", project: str = "") -> List[RegistryTask]:
    """Split raw text into tasks and attach metadata."""
    tasks: List[RegistryTask] = []
    for line in text.splitlines():
        clean = line.strip().lstrip("-*0123456789. ").strip()
        if not clean:
            continue
        t = RegistryTask(id=str(uuid4()), title=clean, context=context, project=project, created_at=datetime.utcnow())
        t.gist = clean[:80]
        tasks.append(t)
    return tasks


def save_registry_task(task: RegistryTask, db_path: Optional[Path] = None) -> None:
    path = db_path or _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS registry_tasks (
            id TEXT PRIMARY KEY,
            title TEXT,
            context TEXT,
            project TEXT,
            created_at TEXT,
            due_date TEXT,
            status TEXT,
            gist TEXT
        )"""
        )
        conn.execute(
            "INSERT OR REPLACE INTO registry_tasks (id, title, context, project, created_at, due_date, status, gist) VALUES (?,?,?,?,?,?,?,?)",
            (
                task.id,
                task.title,
                task.context,
                task.project,
                (task.created_at or datetime.utcnow()).isoformat(),
                task.due_date,
                task.status,
                task.gist,
            ),
        )
        conn.commit()


def load_registry_tasks(db_path: Optional[Path] = None) -> List[RegistryTask]:
    path = db_path or _db_path()
    if not path.exists():
        return []
    with sqlite3.connect(path) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS registry_tasks (
            id TEXT PRIMARY KEY,
            title TEXT,
            context TEXT,
            project TEXT,
            created_at TEXT,
            due_date TEXT,
            status TEXT,
            gist TEXT
        )"""
        )
        rows = conn.execute(
            "SELECT id, title, context, project, created_at, due_date, status, gist FROM registry_tasks"
        ).fetchall()
    tasks = []
    for row in rows:
        tasks.append(
            RegistryTask(
                id=row[0],
                title=row[1],
                context=row[2],
                project=row[3],
                created_at=datetime.fromisoformat(row[4]) if row[4] else None,
                due_date=row[5],
                status=row[6],
                gist=row[7],
            )
        )
    return tasks


def filter_tasks(tasks: Iterable[RegistryTask], *, status: str | None = None, context: str | None = None) -> List[RegistryTask]:
    result = []
    for t in tasks:
        if status and t.status != status:
            continue
        if context and t.context != context:
            continue
        result.append(t)
    return result


def export_yaml(tasks: Iterable[RegistryTask], out_path: Path) -> None:
    import yaml

    data = [asdict(t) for t in tasks]
    out_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def sync_from_yaml(path: Path, db_path: Optional[Path] = None) -> None:
    import yaml

    tasks = yaml.safe_load(path.read_text()) or []
    for item in tasks:
        task = RegistryTask(
            id=item.get("id", str(uuid4())),
            title=item.get("title", ""),
            context=item.get("context", ""),
            project=item.get("project", ""),
            created_at=datetime.fromisoformat(item.get("created_at")) if item.get("created_at") else datetime.utcnow(),
            due_date=item.get("due_date"),
            status=item.get("status", "new"),
            gist=item.get("gist", ""),
        )
        save_registry_task(task, db_path)


