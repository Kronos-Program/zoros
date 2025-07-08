import pytest
from pathlib import Path

from source.orchestration.turn_registry import TurnRegistry, ManualPause
from source.orchestration.routine_runner import RoutineRunner


def test_routine_runner_manual_pause(tmp_path: Path) -> None:
    add_yml = tmp_path / "add.yml"
    add_yml.write_text("turn_id: add\nhandler: tests.sample_turns:add_numbers\n")
    manual_yml = tmp_path / "ask.yml"
    manual_yml.write_text("turn_id: ask\nhandler: noop\nenv: manual\n")

    registry = TurnRegistry(directory=tmp_path)
    routine = [
        {"turn_id": "add", "input": {"a": 2, "b": 3}},
        {"turn_id": "ask"},
    ]
    runner = RoutineRunner(registry)

    with pytest.raises(ManualPause):
        runner.run(routine)

    assert runner.context["add"] == 5
    assert runner.state == "waiting"
