"""
Utility script for regenerating the dictation fixture SQLite database.

Run from the repo root:

    python tests/fixtures/scripts/create_dictation_fixture_db.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

ROWS = [
    {
        "id": "d79c7767-b8f4-4a82-920a-e5eb31a56ddf",
        "timestamp": "2025-07-04T05:48:00",
        "content": "Preload + chunking plan",
        "audio_path": "tests/assets/dictation-d79c7767.wav",
        "correction": (
            "With regards to your suggestion, let's preload the model when the app "
            "starts by default, but then we can also unmount the model so there'll be "
            "a button to mount and unmount the model. And this will likely be "
            "something that you'll need to mock these interactions. There's already a "
            "load model button and unload. But yes, let's start with preloading when "
            "the app starts. And then yes, let's process chunks during recording with "
            "our super fast backend. And do the preload model and caching intermediate. "
            "And we I'm not thinking we'll work too hard on the parallel processing "
            "yet. I just want to lock in the gains that we seem to be able to realize."
        ),
        "fiber_type": "dictation",
    },
    {
        "id": "bd102bc2-ba28-49c3-aae9-4a40ed83f0fa",
        "timestamp": "2025-07-04T04:12:00",
        "content": "Short mic test",
        "audio_path": "tests/assets/dictation-bd102bc2.wav",
        "correction": "What happens if I try recording again?",
        "fiber_type": "dictation",
    },
]


def main() -> None:
    db_path = Path(__file__).resolve().parents[1] / "data" / "dictation_fixture.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS intake (
                id TEXT PRIMARY KEY,
                timestamp TEXT,
                content TEXT,
                audio_path TEXT,
                correction TEXT,
                fiber_type TEXT,
                submitted INTEGER DEFAULT 1
            )
            """
        )
        conn.execute("DELETE FROM intake")
        for row in ROWS:
            conn.execute(
                """
                INSERT INTO intake (id, timestamp, content, audio_path, correction, fiber_type, submitted)
                VALUES (?,?,?,?,?,?,1)
                """,
                (
                    row["id"],
                    row["timestamp"],
                    row["content"],
                    row["audio_path"],
                    row["correction"],
                    row["fiber_type"],
                ),
            )
        conn.commit()
    print(f"Wrote fixture DB to {db_path}")


if __name__ == "__main__":
    main()

