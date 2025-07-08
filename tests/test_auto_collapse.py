import json
from pathlib import Path
from unittest import mock

from scripts.export_raw_md import export_raw_md
from scripts.fiberize_markdown import fiberize_markdown
from source.auto_collapse import auto_collapse
from source.persistence import load_thread, load_fiber


def test_auto_collapse(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    raw = tmp_path / "chat.txt"
    raw.write_text("User: A\nAssistant: B")
    md = tmp_path / "out.md"
    export_raw_md(raw, md)
    fiberize_markdown(md, "thread-example")

    with mock.patch("source.auto_collapse.LanguageService") as svc_cls:
        svc = svc_cls.return_value
        svc.complete_turn.return_value = {
            "collapse_map": {"thread-example-1": True, "thread-example-2": False},
            "collapse_accuracy_estimate": 0.9,
        }
        result = auto_collapse("thread-example", service=svc)

    assert result["thread-example-1"] is True
    metrics = json.loads((Path(tmp_path) / "metrics.json").read_text())
    assert metrics["collapse_accuracy_estimate"] == 0.9
