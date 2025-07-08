import json
import os
from pathlib import Path

from scripts.export_raw_md import export_raw_md
from scripts.fiberize_markdown import fiberize_markdown
from source.persistence import load_thread, load_fiber


def test_fiberize(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    raw = tmp_path / "chat.txt"
    raw.write_text(
        """User: Hello\nAssistant: Hi"""
    )
    md = tmp_path / "out.md"
    export_raw_md(raw, md)

    fiberize_markdown(md, "thread-example")

    thread = load_thread("thread-example")
    assert len(thread["fiber_ids"]) == 2
    f0 = load_fiber(thread["fiber_ids"][0])
    assert f0["type"] == "PromptFiber"
    assert f0["content"] == "Hello"
    f1 = load_fiber(thread["fiber_ids"][1])
    assert f1["type"] == "ResponseFiber"
    assert f1["content"] == "Hi"
