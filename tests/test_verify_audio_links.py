import json
import sqlite3
from pathlib import Path

from scripts import verify_audio_links


def setup_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE intake (
                id TEXT PRIMARY KEY,
                timestamp TEXT,
                content TEXT,
                audio_path TEXT
            )
            """
        )
        conn.commit()


def test_verify_audio_links(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "db.sqlite"
    setup_db(db)
    audio_dir = tmp_path / "audio" / "intake"
    audio_dir.mkdir(parents=True)
    id_ok = "id_ok"
    id_fix = "id_fix"
    id_missing = "id_missing"
    p_ok = audio_dir / f"{id_ok}.wav"
    p_ok.write_text("a")
    p_alt = audio_dir / f"{id_fix}.mp3"
    p_alt.write_text("b")
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO intake (id, timestamp, content, audio_path) VALUES (?,?,?,?)",
            (id_ok, "t", "c", str(p_ok)),
        )
        conn.execute(
            "INSERT INTO intake (id, timestamp, content, audio_path) VALUES (?,?,?,?)",
            (id_fix, "t", "c", str(tmp_path / "missing.wav")),
        )
        conn.execute(
            "INSERT INTO intake (id, timestamp, content, audio_path) VALUES (?,?,?,?)",
            (id_missing, "t", "c", str(tmp_path / "none.wav")),
        )
        conn.commit()

    report = tmp_path / "artifacts" / "audio_link_report.json"
    log = tmp_path / "logs" / "verify_audio.log"
    monkeypatch.setattr(verify_audio_links, "DB_PATH", db)
    monkeypatch.setattr(verify_audio_links, "AUDIO_DIR", audio_dir)
    monkeypatch.setattr(verify_audio_links, "REPORT_PATH", report)
    monkeypatch.setattr(verify_audio_links, "LOG_PATH", log)

    verify_audio_links.verify_audio_links(db, audio_dir, report, log)

    data = json.loads(report.read_text())
    status = {d["id"]: d["status"] for d in data}
    assert status[id_ok] == "ok"
    assert status[id_fix] == "missing"
    assert status[id_missing] == "missing"

    with sqlite3.connect(db) as conn:
        cur = conn.execute("SELECT audio_path FROM intake WHERE id=?", (id_fix,))
        new_path = cur.fetchone()[0]
        assert new_path == str(p_alt)

    log_text = log.read_text()
    assert id_missing in log_text
