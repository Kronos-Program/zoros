from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import yaml
import pytest


@pytest.fixture()
def _setup_env(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    (tmp_path / "routines" / "imported").mkdir(parents=True, exist_ok=True)
    yield tmp_path


def _run_cli(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def test_import_mainchain(_setup_env, tmp_path: Path):
    flow = tmp_path / "demo.yaml"
    flow.write_text(
        """steps:\n  - turn: add\n    with:\n      a: 1\n      b: 2\n  - turn: ask\n"""
    )
    proc = _run_cli([sys.executable, str(ROOT / "scripts" / "zoros_cli.py"), "import-flow", "--file", str(flow)])
    assert proc.returncode == 0
    out = tmp_path / "routines" / "imported" / "demo.routine.yaml"
    assert out.exists()
    data = yaml.safe_load(out.read_text())
    assert len(data) == 2
    db = sqlite3.connect(tmp_path / "fibers.db")
    rows = db.execute("SELECT id FROM routine_import_fibers").fetchall()
    assert rows


def test_import_n8n(_setup_env, tmp_path: Path):
    flow = tmp_path / "flow.json"
    flow.write_text(
        json.dumps({"nodes": [{"name": "add", "parameters": {"a": 1, "b": 2}}, {"name": "ask"}], "connections": {}})
    )
    proc = _run_cli([sys.executable, str(ROOT / "scripts" / "zoros_cli.py"), "import-flow", "--file", str(flow), "--py"])
    assert proc.returncode == 0
    out_yaml = tmp_path / "routines" / "imported" / "flow.routine.yaml"
    out_py = tmp_path / "routines" / "imported" / "flow.routine.py"
    assert out_yaml.exists() and out_py.exists()
    data = yaml.safe_load(out_yaml.read_text())
    assert data[0]["turn_id"] == "add"
