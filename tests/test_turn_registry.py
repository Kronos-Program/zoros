import pytest
from pathlib import Path
from source.orchestration.turn_registry import TurnRegistry


def test_turn_registry_load_and_call(tmp_path: Path) -> None:
    yml = tmp_path / "add.yml"
    yml.write_text("turn_id: add_two\nhandler: tests.sample_turns:add_numbers\n")
    registry = TurnRegistry(directory=tmp_path)
    handler = registry.get_handler("add_two")
    result = handler({"a": 1, "b": 2})
    assert result == 3
