import pytest
from datetime import datetime
from uuid import uuid4

from source.core.models.fibrizer_options import FibrizerOptions
from source.core.models.fiber import Fiber
from source.orchestration.fibrizers.base_fibrizer import BaseFibrizer


class DummyFibrizer(BaseFibrizer):
    def fibrize(self, fiber: Fiber):
        return super().fibrize(fiber)


def make_fiber() -> Fiber:
    return Fiber(
        id=uuid4(),
        content="txt",
        type="text",
        metadata={},
        revision_count=0,
        created_at=datetime.utcnow(),
        source="unit",
    )


def test_options_valid():
    opts = FibrizerOptions(
        fold_levels=[0, 1],
        model_class="standard",
        embed=False,
        prompt_templates={0: "a.txt", 1: "b.txt"},
    )
    assert opts.model_class == "standard"


def test_options_invalid():
    with pytest.raises(Exception):
        FibrizerOptions(
            fold_levels="bad",  # type: ignore
            model_class="wrong",  # type: ignore
            embed="no",  # type: ignore
            prompt_templates={0: "a"},
        )


def test_fibrize_not_implemented():
    opts = FibrizerOptions(
        fold_levels=[0],
        model_class="standard",
        embed=False,
        prompt_templates={0: "a.txt"},
    )
    fibrizer = DummyFibrizer(opts)
    with pytest.raises(NotImplementedError):
        fibrizer.fibrize(make_fiber())

