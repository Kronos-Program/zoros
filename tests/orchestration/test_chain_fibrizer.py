from datetime import datetime
from uuid import uuid4

import pytest

pytest.importorskip("pydantic")

from source.core.models.fiber import Fiber
from source.core.models.fibrizer_options import FibrizerOptions
from source.orchestration.fibrizers import chain_fibrizer
from source.orchestration.fibrizers.base_fibrizer import BaseFibrizer
from source.orchestration.fibrizers.chain_fibrizer import ChainFibrizer, WarningFiber


class DummyFibrizer(BaseFibrizer):
    def __init__(self, options: FibrizerOptions, level: int) -> None:
        super().__init__(options)
        self.level = level

    def fibrize(self, fiber: Fiber):
        return [self._create_fiber(f"{self.level}:{fiber.content}", self.level, fiber.id)]


class FailingFibrizer(BaseFibrizer):
    def fibrize(self, fiber: Fiber):  # pragma: no cover - exception path
        raise RuntimeError("boom")


def test_chain_runs_all_levels(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")

    class L0(DummyFibrizer):
        def __init__(self, options: FibrizerOptions):
            super().__init__(options, 0)

    class L1(FailingFibrizer):
        pass

    class L2(DummyFibrizer):
        def __init__(self, options: FibrizerOptions):
            super().__init__(options, 2)

    monkeypatch.setattr(ChainFibrizer, "FIBRIZER_MAP", {0: L0, 1: L1, 2: L2})

    fiber = Fiber(
        id=uuid4(),
        content="text",
        type="text",
        metadata={},
        revision_count=0,
        created_at=datetime.utcnow(),
        source="test",
    )
    opts = FibrizerOptions(fold_levels=[0, 1, 2], model_class="standard", embed=False)
    chain = ChainFibrizer(opts)
    out = chain.fibrize(fiber)

    assert len(out) == 3
    assert out[0].metadata["fold_level"] == 0
    assert isinstance(out[1], WarningFiber)
    assert out[2].metadata["fold_level"] == 2


def test_embedding(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")

    class L0(DummyFibrizer):
        def __init__(self, options: FibrizerOptions):
            super().__init__(options, 0)

    class DummyService:
        def __init__(self, *a, **k):
            pass

        def embed(self, text: str):
            return [1.0]

    monkeypatch.setattr(chain_fibrizer, "LanguageService", DummyService)
    monkeypatch.setattr(ChainFibrizer, "FIBRIZER_MAP", {0: L0})

    fiber = Fiber(
        id=uuid4(),
        content="x",
        type="text",
        metadata={},
        revision_count=0,
        created_at=datetime.utcnow(),
        source="test",
    )
    opts = FibrizerOptions(fold_levels=[0], model_class="standard", embed=True)
    chain = ChainFibrizer(opts)
    out = chain.fibrize(fiber)

    assert out[0].embeddings == [1.0]
