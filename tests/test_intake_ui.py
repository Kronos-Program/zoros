import os
import sqlite3
from pathlib import Path
import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui import intake_review as review


@pytest.fixture
def sample_db(tmp_path: Path) -> Path:
    db = tmp_path / "db.sqlite"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE fibers (id TEXT, type TEXT, created_at TEXT, content TEXT, audio_path TEXT, metadata TEXT)"
    )
    rows = [
        ("1", "dictation", "2025-06-01T00:00:00", "hello world", None, "{}"),
        ("2", "free_text", "2025-06-02T00:00:00", "second entry", str(tmp_path / "a.wav"), "{}"),
    ]
    conn.executemany("INSERT INTO fibers VALUES (?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()
    (tmp_path / "a.wav").write_bytes(b"\x00\x00")
    return db


@pytest.fixture
def window(sample_db, monkeypatch):
    monkeypatch.setattr(review, "DB_PATH", Path(sample_db))
    win = review.ReviewWindow()
    return win


def test_table_populates(window):
    assert window.table.rowCount() == 2


def test_edit_and_save(window, monkeypatch):
    window.table.selectRow(0)
    window.content_edit.setPlainText("updated")
    window.save_changes()
    with sqlite3.connect(review.DB_PATH) as conn:
        cur = conn.execute("SELECT content FROM fibers WHERE id=?", ("1",))
        assert cur.fetchone()[0] == "updated"


def test_play_audio(window, monkeypatch):
    window.table.selectRow(1)
    played = {}
    monkeypatch.setattr(review.QMediaPlayer, "play", lambda self: played.setdefault("p", True))
    window.play_audio()
    assert played.get("p")


def test_filtering(window):
    window.type_filter.setCurrentText("dictation")
    window.apply_filters()
    assert window.table.rowCount() == 1
    window.type_filter.setCurrentText("All")
    window.start_date.setDate(review.QDate.fromString("2025-06-02", "yyyy-MM-dd"))
    window.apply_filters()
    assert window.table.rowCount() == 1

