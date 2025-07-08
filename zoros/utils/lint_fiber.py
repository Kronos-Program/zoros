"""Fiber linting and auto-repair utilities."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Tuple

import yaml

REQUIRED_FIELDS = {"id", "title", "status"}
OPTIONAL_FIELDS = {"tags", "context", "project"}
DEFAULTS = {"status": "unchecked"}


def _load_fiber(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if text.lstrip().startswith("{"):
        import json
        return json.loads(text)
    return yaml.safe_load(text) or {}


def lint_fiber(path: Path, fix: bool = False) -> Tuple[bool, list[str]]:
    """Check a fiber file for required fields.

    Parameters
    ----------
    path:
        File containing a fiber in YAML or JSON format.
    fix:
        If ``True``, attempt to fill missing defaults.

    Returns
    -------
    ok : bool
        ``True`` if the fiber passes validation, ``False`` otherwise.
    messages : list[str]
        Human-readable warnings or errors discovered during linting.
    """
    data = _load_fiber(path)
    messages: list[str] = []
    ok = True
    changed = False

    for field in REQUIRED_FIELDS:
        value = data.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            messages.append(f"Missing required field '{field}'")
            if fix and field in DEFAULTS:
                data[field] = DEFAULTS[field]
                changed = True
            else:
                ok = False

    for field in OPTIONAL_FIELDS:
        value = data.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            messages.append(f"Warning: optional field '{field}' missing")

    if fix and changed:
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    return ok, messages


__all__ = ["lint_fiber"]
