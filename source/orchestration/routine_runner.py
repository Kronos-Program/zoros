"""Routine execution engine.

Skeleton RoutineRunner referenced in
[deep_research_synthesis.md](../docs/plans/deep_research_synthesis.md#L14-L18).
It executes a sequence of Turns via :class:`TurnRegistry` and handles ManualPause.

Specification: docs/plans/deep_research_synthesis.md#L14-L18
Architecture: docs/zoros_architecture.md#RoutineRunner
Tests: tests/test_routine_runner.py
"""
from __future__ import annotations

from zoros.logger import get_logger
from typing import Any, Dict, Iterable

from .turn_registry import TurnRegistry, ManualPause

logger = get_logger(__name__)


class RoutineRunner:
    """Execute a routine step by step."""

    def __init__(self, registry: TurnRegistry | None = None) -> None:
        self.registry = registry or TurnRegistry()
        self.context: Dict[str, Any] = {}
        self.state: str = "idle"

    # ------------------------------------------------------------------
    def run(self, routine: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        """Run a list of steps until completion or manual pause."""

        self.state = "running"
        for step in routine:
            turn_id = step.get("turn_id")
            handler = self.registry.get_handler(turn_id)
            try:
                result = handler(step.get("input"))
            except ManualPause:
                self.state = "waiting"
                raise
            except Exception as exc:  # pragma: no cover - log then stop
                logger.error("Turn %s failed: %s", turn_id, exc)
                self.state = "failed"
                raise
            self.context[turn_id] = result
        self.state = "completed"
        return self.context
