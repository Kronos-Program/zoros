import pytest
from pathlib import Path

pytest.importorskip("fitz")

from scripts.fiberize_pdf import fiberize_pdf
from source.persistence import load_thread, load_fiber


def _make_pdf(path: Path) -> None:
    import fitz

    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text((72, 72), "Abstract\nA\nIntroduction\nB")
    page2 = doc.new_page()
    page2.insert_text((72, 72), "Methods\nC\nConclusion\nD")
    doc.save(path)
    doc.close()


def test_fiberize_pdf(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    pdf = tmp_path / "sample.pdf"
    _make_pdf(pdf)

    thread_id = fiberize_pdf(pdf)

    thread = load_thread(thread_id)
    assert len(thread["fiber_ids"]) >= 5  # doc fiber + 4 sections
    meta = (tmp_path / "fibers" / f"{thread_id}-1_meta.json")
    assert meta.exists()
    doc_fiber = load_fiber(thread["fiber_ids"][0])
    assert doc_fiber["type"] == "DocFiber"
