import os
from pathlib import Path

from scripts.fiberize_prompt_response_md import fiberize_prompt_response_md
from source.persistence import load_thread, load_fiber


def test_fiberize_prompt_response(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    md = tmp_path / "chat.md"
    md.write_text(
        """# Chat\n\n## PROMPT 1\nHello there. How are you?\n\n## RESPONSE 1\nI am good. Thanks!\n"""
    )

    fiberize_prompt_response_md(md, "thread-test")

    thread = load_thread("thread-test")
    # Document fiber + prompt + response + 2 sentence splits + 2 sentence splits
    assert len(thread["fiber_ids"]) == 1 + 2 + 4

    prompt = load_fiber("thread-test-1")
    assert prompt["type"] == "PromptFiber"
    assert "Hello there" in prompt["content"]

    sub = load_fiber("thread-test-1-1")
    assert sub["type"] == "SubFiber"
    assert sub["content"].startswith("Hello")
