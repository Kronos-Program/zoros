from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import yaml

from source.orchestration.turn_registry import TurnRegistry
from .fibers import save_routine_import


def _detect_format(data: Any, ext: str) -> str:
    if ext == ".json":
        return "n8n"
    if isinstance(data, dict) and "nodes" in data and "connections" in data:
        return "n8n"
    return "mainchain"


def _parse_mainchain(data: Any) -> List[Dict[str, Any]]:
    steps = []
    items = []
    if isinstance(data, dict):
        for key in ("steps", "chain", "flow", "routine"):
            if key in data:
                items = data[key] or []
                break
        else:
            items = data.get("turns", [])
    elif isinstance(data, list):
        items = data
    for item in items:
        if not isinstance(item, dict):
            continue
        turn_id = item.get("turn") or item.get("turn_id") or item.get("name") or item.get("id")
        inp = item.get("with") or item.get("input") or item.get("params") or {}
        if turn_id:
            steps.append({"turn_id": str(turn_id), "input": inp})
    return steps


def _parse_n8n(data: Any) -> List[Dict[str, Any]]:
    steps = []
    nodes = data.get("nodes", []) if isinstance(data, dict) else []
    for node in nodes:
        name = node.get("name") or node.get("type") or node.get("id")
        params = node.get("parameters", {})
        if name:
            steps.append({"turn_id": str(name), "input": params})
    return steps


def import_flow(path: Path, py: bool = False) -> Path:
    text = path.read_text()
    ext = path.suffix.lower()
    data = json.loads(text) if ext == ".json" else yaml.safe_load(text)
    fmt = _detect_format(data, ext)
    routine = _parse_n8n(data) if fmt == "n8n" else _parse_mainchain(data)

    registry = TurnRegistry()
    warnings = [s["turn_id"] for s in routine if s["turn_id"] not in registry.turns]

    out_dir = Path("routines/imported")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_yaml = out_dir / f"{path.stem}.routine.yaml"
    out_yaml.write_text(yaml.safe_dump(routine, sort_keys=False))

    if py:
        out_py = out_dir / f"{path.stem}.routine.py"
        out_py.write_text("ROUTINE = " + json.dumps(routine, indent=2))

    save_routine_import(path, fmt)

    print(f"{len(routine)} steps imported from {fmt} format")
    if warnings:
        print("Validation warnings: unknown turns " + ", ".join(warnings))
    return out_yaml
