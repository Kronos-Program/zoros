from __future__ import annotations

import logging
from datetime import datetime
from uuid import uuid4

import pytest

pytest.importorskip("pydantic")

from source.core.models.fiber import Fiber
from source.core.models.fibrizer_options import FibrizerOptions
from source.orchestration.fibrizers.base_fibrizer import BaseFibrizer


class DummyFibrizer(BaseFibrizer):
    def fibrize(self, fiber: Fiber):  # pragma: no cover - not used
        return []


def _make_fiber() -> Fiber:
    return Fiber(
        id=uuid4(),
        content="Hello",
        type="text",
        metadata={},
        revision_count=0,
        created_at=datetime.utcnow(),
        source="unit",
    )


def test_template_loading():
    opts = FibrizerOptions()
    fib = _make_fiber()
    fibrizer = DummyFibrizer(opts)
    prompt = fibrizer._prepare_prompt(fib, 1)
    assert prompt == "Gist: Hello\n"


def test_fallback_missing(tmp_path, caplog):
    missing = tmp_path / "none.txt"
    opts = FibrizerOptions(prompt_templates={1: str(missing)})
    fib = _make_fiber()
    fibrizer = DummyFibrizer(opts)
    with caplog.at_level(logging.WARNING):
        prompt = fibrizer._prepare_prompt(fib, 1)
    assert "fallback" in caplog.text.lower()
    assert prompt == "Process: Hello"
