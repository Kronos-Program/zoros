from pathlib import Path
from unittest.mock import patch

from source.fiberizer.document_warp import from_external, to_markdown, to_word


def test_from_external() -> None:
    fiber = from_external(Path("foo.docx"))
    assert fiber.stage == "external"
    assert fiber.content == "foo.docx"


def test_to_markdown(monkeypatch, tmp_path: Path) -> None:
    fiber = from_external(tmp_path / "in.docx")
    out = tmp_path / "out.md"
    with patch("subprocess.run") as run:
        to_markdown(fiber, out)
        run.assert_called_with(["pandoc", str(fiber.content), "-o", str(out)], check=True)


def test_to_word(monkeypatch, tmp_path: Path) -> None:
    fiber = from_external(tmp_path / "in.md")
    out = tmp_path / "out.docx"
    with patch("subprocess.run") as run:
        to_word(fiber, out)
        run.assert_called_with(["pandoc", str(fiber.content), "-o", str(out)], check=True)
