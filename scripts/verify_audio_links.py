import glob
import json
import logging
import os
import sqlite3
from pathlib import Path
from typing import List, Dict

DB_PATH = Path("zoros_intake.db")
AUDIO_DIR = Path("audio") / "intake"
REPORT_PATH = Path("artifacts") / "audio_link_report.json"
LOG_PATH = Path("logs") / "verify_audio.log"


def verify_audio_links(
    db_path: Path = DB_PATH,
    audio_dir: Path = AUDIO_DIR,
    report_path: Path = REPORT_PATH,
    log_path: Path = LOG_PATH,
) -> List[Dict[str, str]]:
    audio_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=log_path, level=logging.INFO, force=True)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, audio_path FROM intake WHERE audio_path IS NOT NULL"
        ).fetchall()
        report: List[Dict[str, str]] = []
        for row in rows:
            fid = row["id"]
            path = row["audio_path"]
            status = "ok"
            if not path or not Path(path).exists():
                status = "missing"
                matches = glob.glob(str(audio_dir / f"{fid}.*"))
                if matches:
                    new_path = matches[0]
                    conn.execute(
                        "UPDATE intake SET audio_path=? WHERE id=?", (new_path, fid)
                    )
                    conn.commit()
                    path = new_path
                else:
                    logging.warning("Audio missing for %s", fid)
            report.append({"id": fid, "audio_path": path, "status": status})

    with report_path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    return report


if __name__ == "__main__":
    verify_audio_links()
