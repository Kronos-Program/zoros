from __future__ import annotations

import re
import sqlite3
import os
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List
import yaml
import csv


@dataclass
class LifeTask:
    """Model of a Task Fiber from docs/tasks/life.*"""

    id: str
    title: str
    time_hint: str = ""
    tags: List[str] = field(default_factory=list)
    description: List[str] = field(default_factory=list)


TASK_RE = re.compile(r"^### Task Fiber: (?P<title>.+)")
FIELD_RE = re.compile(r"\* \*\*(?P<key>[a-z_\\]+)\*\*: ?(?:`?(?P<val>.+?)`?)?$")


def parse_life_tasks(path: Path) -> List[LifeTask]:
    """Parse tasks from a markdown file."""
    lines = path.read_text(encoding="utf-8").splitlines()
    tasks: List[LifeTask] = []
    i = 0
    current: LifeTask | None = None
    while i < len(lines):
        line = lines[i]
        m = TASK_RE.match(line)
        if m:
            if current:
                tasks.append(current)
            current = LifeTask(id="", title=m.group("title"))
            i += 1
            continue
        if line.strip() == "---":
            if current:
                tasks.append(current)
                current = None
            i += 1
            continue
        if current:
            m = FIELD_RE.match(line.strip())
            if m:
                key = m.group("key").replace('\\', '')  # Remove escapes from key
                val = (m.group("val") or "").strip('"')
                if key == "id":
                    current.id = val
                elif key == "title":
                    current.title = val
                elif key == "time_hint":
                    current.time_hint = val
                elif key == "tags":
                    # Handle escaped brackets \[ and \] in the markdown
                    val_clean = val.replace('\\[', '').replace('\\]', '')
                    current.tags = [t.strip('" ').strip() for t in val_clean.split(',') if t.strip()]
                    # Clean up any remaining brackets from individual tags
                    current.tags = [t.replace('"', '').replace('[', '').replace(']', '') for t in current.tags]
                elif key == "description":
                    desc = []
                    j = i + 1
                    while (
                        j < len(lines)
                        and lines[j].strip() != "---"
                        and lines[j].lstrip().startswith(tuple("-0123456789"))
                    ):
                        d = lines[j].lstrip().lstrip('-').lstrip()
                        d = re.sub(r"^\d+[.)]?\s*", "", d)
                        desc.append(d)
                        j += 1
                    current.description = desc
                    i = j - 1
        i += 1
    if current:
        tasks.append(current)
    return tasks


def export_yaml(tasks: List[LifeTask], out_path: Path) -> None:
    """Write tasks to a YAML file."""
    data = [asdict(t) for t in tasks]
    out_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def export_csv(tasks: List[LifeTask], out_path: Path) -> None:
    """Write tasks to CSV (Excel-friendly)."""
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["id", "title", "time_hint", "tags", "description"])
        for t in tasks:
            writer.writerow([t.id, t.title, t.time_hint, ",".join(t.tags), "|".join(t.description)])


def save_task_db(task: LifeTask, db_path: Path | None = None) -> None:
    """Insert or update a task in the `tasks` table."""
    db = db_path or Path(os.getenv("DATA_DIR", "data")) / "fibers.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, title TEXT, time_hint TEXT, tags TEXT, description TEXT)"
        )
        conn.execute(
            "INSERT OR REPLACE INTO tasks (id, title, time_hint, tags, description) VALUES (?,?,?,?,?)",
            (task.id, task.title, task.time_hint, ",".join(task.tags), "\n".join(task.description)),
        )
        conn.commit()
