"""
Utility helpers for working with the version-controlled dictation fixture DB.
"""

from __future__ import annotations

import shutil
from pathlib import Path

FIXTURE_DB = Path(__file__).resolve().parent / "data" / "dictation_fixture.db"


def copy_dictation_fixture_db(tmp_path: Path) -> Path:
    """Copy the stable dictation fixture DB into a temporary directory."""
    if not FIXTURE_DB.exists():
        raise FileNotFoundError(
            f"Fixture DB {FIXTURE_DB} is missing. Regenerate via "
            "'tests/fixtures/scripts/create_dictation_fixture_db.py'."
        )
    destination = tmp_path / "dictation_fixture.db"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURE_DB, destination)
    return destination


__all__ = ["copy_dictation_fixture_db", "FIXTURE_DB"]

