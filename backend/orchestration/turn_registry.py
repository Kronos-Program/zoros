"""TurnRegistry module for RoutineRunner.

This implements the TurnRegistry skeleton described in
[deep_research_synthesis.md](../docs/plans/deep_research_synthesis.md#L14-L18).
It loads YAML manifests from ``turns/`` and resolves handlers for execution.

Specification: docs/plans/deep_research_synthesis.md#L14-L18
Architecture: docs/zoros_architecture.md#RoutineRunner
Tests: tests/test_turn_registry.py
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from zoros.logger import get_logger
import re
from pathlib import Path
from typing import Callable, Dict, Any

import yaml

logger = get_logger(__name__)


class ManualPause(Exception):
    """Signal that a manual turn requires user input."""


def _camel_to_snake(name: str) -> str:
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


@dataclass
class TurnInfo:
    turn_id: str
    handler: str
    env: str | None = None


class TurnRegistry:
    """Load turn manifests and provide handler callables."""

    def __init__(self, directory: str | Path = "turns") -> None:
        self.directory = Path(directory)
        self.turns: Dict[str, TurnInfo] = {}
        for path in self.directory.rglob("*.yml"):
            data = yaml.safe_load(path.read_text()) or {}
            tid = data.get("turn_id")
            handler = data.get("handler")
            if tid and handler:
                self.turns[tid] = TurnInfo(tid, handler, data.get("env"))

    # ------------------------------------------------------------------
    def get_handler(self, turn_id: str) -> Callable[[Any], Any]:
        info = self.turns.get(turn_id)
        if not info:
            raise KeyError(turn_id)
        if info.env == "manual":
            def _manual(_ctx=None):
                raise ManualPause(turn_id)
            return _manual
        if info.handler.startswith("tool:"):
            tool_name = info.handler.split(":", 1)[1]

            def _tool(ctx=None):
                logger.info("Tool stub %s called", tool_name)
                from source.language_service import LanguageService

                service = LanguageService()
                return service.complete_turn(tool_name, ctx or {})

            return _tool
        handler_obj = self._import_handler(info.handler)
        if hasattr(handler_obj, "fibrize"):
            def _run(fiber, *a, **kw):
                inst = handler_obj()
                return inst.fibrize(fiber)
            return _run
        if callable(handler_obj):
            return handler_obj
        raise ValueError(f"Handler for {turn_id} is not callable")

    # ------------------------------------------------------------------
    def _import_handler(self, spec: str):
        if spec.startswith("fibrizer:"):
            class_name = spec.split(":", 1)[1]
            module = f"source.orchestration.fibrizers.{_camel_to_snake(class_name)}"
            mod = import_module(module)
            return getattr(mod, class_name)
        if ":" in spec:
            module, name = spec.split(":", 1)
        else:
            module, name = spec.rsplit(".", 1)
        mod = import_module(module)
        return getattr(mod, name)
