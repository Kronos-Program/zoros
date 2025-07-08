import sqlite3
from pathlib import Path
from zoros import logger as logger_mod
from source.core.models import log_fiber


def test_logging_to_file_and_db(tmp_path, monkeypatch):
    conf = tmp_path / "logging_config.yaml"
    conf.write_text("default_level: INFO\nmodules:{}\n")
    monkeypatch.setattr(logger_mod, "CONFIG_PATH", conf)
    monkeypatch.setattr(logger_mod, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(logger_mod, "DB_PATH", tmp_path / "logs.db")
    monkeypatch.setattr(log_fiber, "DB_PATH", tmp_path / "logs.db")

    log = logger_mod.get_logger("test.module")
    log.warning("warn1")
    log.error("boom")
    log.error("boom")

    file_path = tmp_path / "logs" / "test.module.log"
    assert file_path.exists()
    text = file_path.read_text()
    assert "warn1" in text

    with sqlite3.connect(logger_mod.DB_PATH) as conn:
        cur = conn.execute("SELECT COUNT(*) FROM log_events")
        assert cur.fetchone()[0] == 3
        cur = conn.execute("SELECT tags FROM log_fibers WHERE level='ERROR'")
        rows = [row[0] for row in cur.fetchall()]
        assert any("auto-repair-candidate" in row for row in rows)
