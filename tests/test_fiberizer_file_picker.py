import os
from pathlib import Path

from streamlit.testing.v1 import AppTest

from source.persistence import load_thread


def test_file_picker_fiberizes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    md = tmp_path / "chat.md"
    md.write_text("""# Chat\n\n## PROMPT 1\nHello\n\n## RESPONSE 1\nHi\n""")
    monkeypatch.setenv("FIBERIZER_MD_PATH", str(md))
    monkeypatch.setenv("FIBERIZER_THREAD_ID", "thread-test")

    at = AppTest.from_file("source/interfaces/streamlit/fiberizer_file_picker.py")
    at.run()
    at.button(key="fiberize").click()
    at.run()

    thread = load_thread("thread-test")
    assert len(thread["fiber_ids"]) > 0

    from streamlit.runtime.caching import cache_data
    cache_data.clear()
