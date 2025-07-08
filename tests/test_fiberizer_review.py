import json
import os
from pathlib import Path

from streamlit.testing.v1 import AppTest

from scripts.fiberize_markdown import fiberize_markdown
from source.persistence import load_thread


def _setup_thread(tmp_path: Path) -> str:
    md = tmp_path / "chat.md"
    md.write_text("1. User: Hello\n2. Assistant: Hi")
    fiberize_markdown(md, "thread-test")
    return "thread-test"


def test_expand_collapse(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    tid = _setup_thread(tmp_path)
    monkeypatch.setenv("REVIEW_THREAD_ID", tid)

    at = AppTest.from_file("source/interfaces/streamlit/fiberizer_review.py")
    at.run()
    fid = load_thread(tid)["fiber_ids"][0]
    assert at.expander[0].proto.expanded is False

    at.button(key=f"toggle_{fid}").click()
    at.run()
    assert at.expander[0].proto.expanded is True


def test_edit_creates_annotation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    tid = _setup_thread(tmp_path)
    monkeypatch.setenv("REVIEW_THREAD_ID", tid)

    at = AppTest.from_file("source/interfaces/streamlit/fiberizer_review.py")
    at.run()
    fid = load_thread(tid)["fiber_ids"][0]

    at.button(key=f"edit_btn_{fid}").click()
    at.run()
    # text area appears on next run after edit flag set
    at.run()
    at.text_area(key=f"ta_{fid}").input("Updated")
    at.button(key=f"save_{fid}").click()
    at.run()

    fiber_dir = Path(tmp_path) / "fibers"
    types = [json.loads(p.read_text())["type"] for p in fiber_dir.glob("*.json")]
    assert "AnnotationFiber" in types
