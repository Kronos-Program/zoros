from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path

import zoros.cli as cli
from zoros.plugins import loader


def setup_demo(tmp_path: Path) -> Path:
    base = tmp_path / "zoros_plugins" / "demo"
    base.mkdir(parents=True)
    (base / "plugin_manifest.yaml").write_text(
        """\
name: demo
entry_point: demo.cli
description: Demo plugin
commands:
  - say
"""
    )
    return base.parent


def test_plugins_list(monkeypatch, capsys, tmp_path):
    plug_dir = setup_demo(tmp_path)
    monkeypatch.setattr(loader, "PLUGIN_DIR", plug_dir)
    loader.load_plugins()

    cli.list_plugins_cmd()
    out = capsys.readouterr().out
    assert "demo" in out


def test_run_plugin_logs(monkeypatch, tmp_path):
    plug_dir = setup_demo(tmp_path)
    monkeypatch.setattr(loader, "PLUGIN_DIR", plug_dir)
    monkeypatch.setattr(loader, "LOG_DIR", tmp_path / "logs")
    db = tmp_path / "test.sqlite"
    monkeypatch.setattr(loader, "DB_PATH", db)

    def fake_run(cmd, capture_output=True, text=True, cwd=None):
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    loader.load_plugins()
    cli.run_plugin_cmd("demo", "say")

    log_file = loader.LOG_DIR / "plugin_demo.log"
    assert log_file.exists()
    txt = log_file.read_text()
    assert "ran say" in txt

    with sqlite3.connect(db) as conn:
        cur = conn.execute("SELECT COUNT(*) FROM plugin_logs")
        assert cur.fetchone()[0] >= 1
