from pathlib import Path
import os
import pytest

pytest.importorskip("pydantic")

from source.fiberizer.fibers import TaskWarpFiber, get_task_warp_fibers


def test_task_warp_fiber_save_and_query(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    fiber = TaskWarpFiber("TASK-999", "Created", {"foo": "bar"})
    fiber.save()

    rows = get_task_warp_fibers("TASK-999")
    assert len(rows) == 1
    row = rows[0]
    assert row["action"] == "Created"
    assert row["metadata"]["foo"] == "bar"
