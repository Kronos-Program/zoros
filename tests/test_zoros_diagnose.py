from __future__ import annotations

import sqlite3
from pathlib import Path
import subprocess
import sys

import pytest

from zoros.diagnose import run_diagnose


def _fake_run(cmd, capture_output=True, text=True, check=False):
    if cmd[:2] == ["poetry", "--version"]:
        return subprocess.CompletedProcess(cmd, 0, stdout="Poetry (version 1.5.1)", stderr="")
    return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="error")


def _fake_which(_: str) -> str:
    return "/usr/bin/tool"


@pytest.fixture()
def setup_env(tmp_path: Path, monkeypatch):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """[tool.poetry.plugins."zoros.plugins"]
whisper_cpp = "zoros_whisper_cpp:WhisperCPPPlugin"
""",
        encoding="utf-8",
    )
    (tmp_path / "zoros_whisper_cpp").mkdir()
    logs = tmp_path / "logs" / "errors"
    logs.mkdir(parents=True)
    (logs / "log.txt").write_text("x")
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db = data_dir / "fibers.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE fibers(id TEXT, created_at TEXT)")
        conn.execute("INSERT INTO fibers VALUES ('1','2025-01-01')")
    monkeypatch.setattr(subprocess, "run", _fake_run)
    monkeypatch.setattr("shutil.which", _fake_which)
    return tmp_path


def test_run_diagnose_ok(setup_env: Path, capsys):
    exit_code = run_diagnose(setup_env)
    captured = capsys.readouterr()
    assert "Poetry" in captured.out
    assert exit_code == 0

