from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
import logging
import os

DB_PATH = Path(os.getenv("DATA_DIR", "data")) / "logs.db"


class LogFiber(BaseModel):
    """Structured log entry stored as a Fiber."""

    id: UUID
    created_at: datetime
    level: str
    source: str
    message: str
    tags: List[str] = Field(default_factory=list)

    @classmethod
    def create_from_log(cls, record: logging.LogRecord, repeat: bool = False) -> "LogFiber":
        if record.levelno < logging.WARNING:
            raise ValueError("Only warnings or errors create LogFibers")
        tags = [record.levelname.lower()]
        if repeat and record.levelno >= logging.ERROR:
            tags.append("auto-repair-candidate")
        return cls(
            id=uuid4(),
            created_at=datetime.utcfromtimestamp(record.created),
            level=record.levelname,
            source=record.name,
            message=record.getMessage(),
            tags=tags,
        )

    def save(self) -> None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS log_fibers (id TEXT PRIMARY KEY, timestamp TEXT, level TEXT, source TEXT, message TEXT, tags TEXT)"
            )
            conn.execute(
                "INSERT INTO log_fibers (id, timestamp, level, source, message, tags) VALUES (?,?,?,?,?,?)",
                (
                    str(self.id),
                    self.created_at.isoformat(),
                    self.level,
                    self.source,
                    self.message,
                    json.dumps(self.tags),
                ),
            )
            conn.commit()
