from datetime import datetime
from uuid import uuid4
from unittest import mock

import pytest

from source.core.models.fiber import Fiber
from source.core.models.fibrizer_options import FibrizerOptions
from source.orchestration.fibrizers.gist_fibrizer import GistFibrizer


@pytest.fixture
def sample_fiber() -> Fiber:
    return Fiber(
        id=uuid4(),
        content="This is a long piece of text that should be summarized by the gist fibrizer.",
        type="text",
        metadata={},
        revision_count=0,
        created_at=datetime.utcnow(),
        source="unit",
    )


def test_gist_fibrizer_basic(sample_fiber: Fiber) -> None:
    opts = FibrizerOptions(fold_levels=[1], prompt_templates={1: "{text}"}, model_class="standard")
    gf = GistFibrizer(opts)
    with mock.patch.object(gf, "_run_model", return_value="GIST"):
        out = gf.fibrize(sample_fiber)
    assert len(out) == 1
    assert out[0].metadata["fold_level"] == 1
    assert out[0].metadata["parent_fiber_id"] == str(sample_fiber.id)
    assert out[0].content == "GIST"


def test_gist_fibrizer_short_input() -> None:
    fiber = Fiber(
        id=uuid4(),
        content="short text",
        type="text",
        metadata={},
        revision_count=0,
        created_at=datetime.utcnow(),
        source="unit",
    )
    opts = FibrizerOptions(fold_levels=[1], prompt_templates={1: "{text}"}, model_class="standard")
    gf = GistFibrizer(opts)
    out = gf.fibrize(fiber)
    assert out == []
