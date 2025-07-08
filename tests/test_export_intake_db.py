import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from scripts import export_intake_db


def _make_db(path: Path) -> Path:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE fibers (id TEXT, content TEXT, type TEXT, created_at TEXT, audio_path TEXT, metadata TEXT)"
        )
        conn.execute(
            "INSERT INTO fibers VALUES (?,?,?,?,?,?)",
            ("1", "hello", "dictation", "2025-06-01T00:00:00Z", None, "{}"),
        )
    return path


def test_export_function(tmp_path: Path) -> None:
    db = _make_db(tmp_path / "test.db")
    out = tmp_path / "out.json"
    items = export_intake_db.export_intake_db(db, out)
    data = json.loads(out.read_text())
    assert data == items
    assert data[0]["id"] == "1"
    assert set(data[0]) == {
        "id",
        "content",
        "type",
        "created_at",
        "audio_path",
        "metadata",
    }
    assert data[0]["audio_path"] is None


def test_cli_overrides(tmp_path: Path) -> None:
    db = _make_db(tmp_path / "cli.db")
    out = tmp_path / "cli.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(Path("scripts/export_intake_db.py")),
            "--db",
            str(db),
            "--out",
            str(out),
        ],
        capture_output=True,
    )
    assert proc.returncode == 0
    assert out.exists()


def test_missing_db(tmp_path: Path) -> None:
    out = tmp_path / "missing.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(Path("scripts/export_intake_db.py")),
            "--db",
            str(tmp_path / "no.db"),
            "--out",
            str(out),
        ],
        capture_output=True,
    )
    assert proc.returncode == 1
