"""Document WarpFiber utilities."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional
import subprocess
from uuid import uuid4

from source.core.models.fiber import WarpFiber


class DocumentWarpFiber(WarpFiber):
    """WarpFiber representing a document at a specific conversion stage."""

    stage: str
    parent_id: Optional[str] = None


def _make_fiber(content: str, stage: str, parent_id: Optional[str] = None) -> DocumentWarpFiber:
    return DocumentWarpFiber(
        id=uuid4(),
        content=content,
        type="text",
        metadata={},
        revision_count=0,
        created_at=datetime.utcnow(),
        source=stage,
        stage=stage,
        parent_id=parent_id,
    )


def _run_pandoc(input_path: Path, output_path: Path) -> None:
    try:
        subprocess.run(["pandoc", str(input_path), "-o", str(output_path)], check=True)
    except FileNotFoundError as exc:  # pragma: no cover
        raise RuntimeError("pandoc not found") from exc


def from_external(path: Path) -> DocumentWarpFiber:
    return _make_fiber(str(path), "external")


def to_markdown(fiber: DocumentWarpFiber, out: Path) -> DocumentWarpFiber:
    _run_pandoc(Path(fiber.content), out)
    return _make_fiber(str(out), "markdown", parent_id=str(fiber.id))


def to_word(fiber: DocumentWarpFiber, out: Path) -> DocumentWarpFiber:
    _run_pandoc(Path(fiber.content), out)
    return _make_fiber(str(out), "word", parent_id=str(fiber.id))
