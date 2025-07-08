from datetime import datetime
from uuid import uuid4
from unittest import mock

from source.core.models.fiber import Fiber
from source.core.models.fibrizer_options import FibrizerOptions
from source.orchestration.fibrizers.source_expanded_fibrizer import (
    SourceFibrizer,
    ExpandedFibrizer,
)


def _make_fiber(text: str) -> Fiber:
    return Fiber(
        id=uuid4(),
        content=text,
        type="text",
        metadata={},
        revision_count=0,
        created_at=datetime.utcnow(),
        source="unit",
    )


def test_source_and_expanded() -> None:
    opts = FibrizerOptions(
        fold_levels=[2, 3],
        prompt_templates={2: "{text}", 3: "{text}"},
        model_class="standard",
    )
    sf = SourceFibrizer(opts)
    ef = ExpandedFibrizer(opts)

    text = "x" * 120
    fiber = _make_fiber(text)
    with mock.patch.object(sf, "_run_model", return_value="SRC"):
        out_s = sf.fibrize(fiber)
    with mock.patch.object(ef, "_run_model", return_value="EXP"):
        out_e = ef.fibrize(fiber)

    assert out_s[0].metadata["fold_level"] == 2
    assert out_e[0].metadata["fold_level"] == 3
    assert out_s[0].metadata["parent_fiber_id"] == str(fiber.id)
    assert out_e[0].metadata["parent_fiber_id"] == str(fiber.id)


def test_source_skip_short() -> None:
    opts = FibrizerOptions(fold_levels=[2], prompt_templates={2: "{text}"}, model_class="standard")
    sf = SourceFibrizer(opts)
    fiber = _make_fiber("short text")
    assert sf.fibrize(fiber) == []
