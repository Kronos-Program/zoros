from __future__ import annotations

from zoros.logger import get_logger
from pathlib import Path
from typing import List

from source.core.models.fiber import Fiber
from source.orchestration.fibrizers.base_fibrizer import BaseFibrizer

logger = get_logger(__name__)


class DocumentFiberizer(BaseFibrizer):
    """Fibrizer that ingests DOCX and PDF documents.

    Parameters
    ----------
    options : FibrizerOptions | None
        Optional configuration. The ``include_documents`` flag determines
        whether this fibrizer is added to a chain by default.

    Examples
    --------
    >>> df = DocumentFiberizer()
    >>> fibers = df.fibrize(Fiber(...))
    """

    def fibrize(self, fiber: Fiber) -> List[Fiber]:
        path = Path(fiber.content)
        if not path.exists():
            raise FileNotFoundError(path)
        if path.stat().st_size > 50 * 1024 * 1024:
            logger.warning("Skipping large file: %s", path)
            return []

        if path.suffix.lower() == ".docx":
            return self._from_docx(path, fiber.id)
        if path.suffix.lower() == ".pdf":
            return self._from_pdf(path, fiber.id)
        raise ValueError(f"Unsupported document type: {path.suffix}")

    def _from_docx(self, path: Path, parent_id) -> List[Fiber]:
        try:
            import docx
        except Exception as exc:  # pragma: no cover - optional dep
            raise ImportError("python-docx required for DOCX support") from exc

        doc = docx.Document(str(path))
        children: List[Fiber] = []
        for p in doc.paragraphs:
            text = p.text.strip()
            if text:
                children.append(self._create_fiber(text, level=0, parent_id=parent_id))
        return children

    def _from_pdf(self, path: Path, parent_id) -> List[Fiber]:
        try:
            import fitz  # PyMuPDF
        except Exception:
            try:
                from pdfminer.high_level import extract_text
            except Exception as exc:  # pragma: no cover - optional dep
                raise ImportError("PyMuPDF or pdfminer.six required for PDF support") from exc
            text = extract_text(str(path))
            pages = [p.strip() for p in text.split("\f") if p.strip()]
            return [self._create_fiber(t, level=0, parent_id=parent_id) for t in pages]

        doc = fitz.open(str(path))
        children: List[Fiber] = []
        for page in doc:
            text = page.get_text().strip()
            if text:
                children.append(self._create_fiber(text, level=0, parent_id=parent_id))
        doc.close()
        return children
