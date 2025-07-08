from pathlib import Path

from scripts.export_raw_md import export_raw_md


def test_export_raw_md(tmp_path: Path) -> None:
    raw = tmp_path / "chat.txt"
    raw.write_text(
        """Meta line\nUser: Hello\nAssistant: Hi\nUser: Bye\nAssistant: Good bye"""
    )
    out = tmp_path / "out.md"
    export_raw_md(raw, out)
    assert out.read_text().strip().splitlines() == [
        "1. User: Hello",
        "2. Assistant: Hi",
        "3. User: Bye",
        "4. Assistant: Good bye",
    ]
