from pathlib import Path

from scripts.maintenance.metadata_enforcer import validate_file


def test_valid_metadata(tmp_path: Path) -> None:
    file = tmp_path / "task.md"
    file.write_text("""---
id: T1
title: Sample
status: planned
---
""")
    errors = validate_file(file, "task")
    assert errors == []


def test_missing_field(tmp_path: Path) -> None:
    file = tmp_path / "task.md"
    file.write_text("""---
id: T1
title: Sample
---
""")
    errors = validate_file(file, "task")
    assert any("missing field" in e for e in errors)
