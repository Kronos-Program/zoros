from __future__ import annotations

"""Simple plugin loader using YAML manifests."""

from dataclasses import dataclass, field
from datetime import datetime
import logging
import sqlite3
import subprocess
from pathlib import Path
from typing import Dict, List

import yaml

PLUGIN_DIR = Path("zoros_plugins")
LOG_DIR = Path("logs")
DB_PATH = Path("zoros.sqlite")

_REQUIRED = {"name", "entry_point", "description", "commands"}


@dataclass
class Plugin:
    """Metadata for a discovered plugin."""

    name: str
    entry_point: str
    description: str
    commands: List[str]
    path: Path
    last_discovered: datetime = field(default_factory=datetime.utcnow)


PLUGINS: Dict[str, Plugin] = {}


def _ensure_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS plugin_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plugin TEXT,
                timestamp TEXT,
                level TEXT,
                message TEXT
            )
            """
        )
        conn.commit()


def log_plugin(name: str, level: str, message: str) -> None:
    """Append a log entry for a plugin to file and database."""
    _ensure_db()
    ts = datetime.utcnow().isoformat()
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_path = LOG_DIR / f"plugin_{name}.log"
    with file_path.open("a", encoding="utf-8") as fh:
        fh.write(f"{ts} [{level}] {message}\n")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO plugin_logs (plugin, timestamp, level, message) VALUES (?,?,?,?)",
            (name, ts, level, message),
        )
        conn.commit()


def load_plugins() -> None:
    """Scan for plugins and populate :data:`PLUGINS`."""
    PLUGINS.clear()
    for manifest in PLUGIN_DIR.glob("*/plugin_manifest.yaml"):
        try:
            data = yaml.safe_load(manifest.read_text()) or {}
        except Exception as exc:  # pragma: no cover - invalid YAML
            logging.warning("Failed to read %s: %s", manifest, exc)
            continue
        if not _REQUIRED.issubset(data):
            continue
        if not isinstance(data.get("commands"), list):
            continue
        plugin = Plugin(
            name=data["name"],
            entry_point=data["entry_point"],
            description=data["description"],
            commands=list(data["commands"]),
            path=manifest.parent,
        )
        PLUGINS[plugin.name] = plugin


def list_plugins() -> List[Plugin]:
    """Return all loaded plugins, loading if necessary."""
    if not PLUGINS:
        load_plugins()
    return list(PLUGINS.values())


def execute_plugin(name: str, command: str) -> subprocess.CompletedProcess:
    """Run a plugin command via ``poetry run``.

    Logs stdout/stderr to both file and the SQLite table.
    """
    if not PLUGINS:
        load_plugins()
    if name not in PLUGINS:
        raise KeyError(name)
    plugin = PLUGINS[name]
    if command not in plugin.commands:
        raise KeyError(command)
    cmd = [
        "poetry",
        "run",
        "python",
        "-m",
        plugin.entry_point,
        command,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=plugin.path)
    log_plugin(name, "INFO", f"ran {command} -> {proc.returncode}")
    if proc.stderr:
        log_plugin(name, "ERROR" if proc.returncode else "INFO", proc.stderr.strip())
    return proc
