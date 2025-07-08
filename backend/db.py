import os
import sqlite3
from pathlib import Path
from typing import Iterable

DB_PATH = Path(os.getenv("DATABASE_URL", "data/app.db").replace("sqlite:///", ""))


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fibers (
                id TEXT PRIMARY KEY,
                content TEXT,
                tags TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                source TEXT
            )
            """
        )
        
        # Add updated_at column if it doesn't exist (for existing databases)
        try:
            conn.execute("ALTER TABLE fibers ADD COLUMN updated_at TEXT DEFAULT (datetime('now'))")
        except sqlite3.OperationalError:
            # Column already exists
            pass
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fiber_id TEXT REFERENCES fibers(id),
                title TEXT,
                description TEXT,
                status TEXT DEFAULT 'new',
                assigned_to TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                priority INTEGER,
                due_date TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER REFERENCES tasks(id),
                content TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.commit()


def execute(sql: str, args: Iterable = ()):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(sql, args)
        conn.commit()
        return cur
