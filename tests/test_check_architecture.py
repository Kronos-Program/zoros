from pathlib import Path
from scripts.maintenance import check_architecture


def test_detect_violation(tmp_path: Path) -> None:
    # create allowed structure
    for d in check_architecture.ALLOWED_TOP_LEVEL_DIRS:
        (tmp_path / d).mkdir()
    for f in check_architecture.ALLOWED_TOP_LEVEL_FILES:
        (tmp_path / f).write_text("x")

    # file in ignored dir should not trigger
    (tmp_path / "venv" / "x.txt").parent.mkdir()
    (tmp_path / "venv" / "x.txt").write_text("")

    # violation: unexpected root dir
    bad = tmp_path / "bad" / "file.txt"
    bad.parent.mkdir()
    bad.write_text("")

    violations = check_architecture.scan_repo(tmp_path)
    assert any(v.path == Path("bad/file.txt") for v in violations)
