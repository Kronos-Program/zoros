# See architecture: docs/zoros_architecture.md#component-overview
import json
import uuid
from pathlib import Path
from typing import Dict

from source.language_service import LanguageService
from source.persistence import (
    Fiber,
    resolveFiber,
    load_thread,
    load_fiber,
    base_dir,
)


def auto_collapse(thread_id: str, service: LanguageService | None = None) -> Dict[str, bool]:
    """Call LanguageService to propose collapse states for a thread."""
    service = service or LanguageService()
    thread = load_thread(thread_id)
    synopsis = [
        {"id": fid, "content": load_fiber(fid)["content"][:100]} for fid in thread["fiber_ids"]
    ]
    result = service.complete_turn("auto-collapse", {"synopsis": synopsis})
    collapse_map = result.get("collapse_map", {})
    fiber = Fiber(
        fiber_id=str(uuid.uuid4()),
        type="CollapseProposalFiber",
        content=json.dumps(collapse_map),
        source="auto_collapse",
    )
    resolveFiber(fiber)
    metrics = {
        "collapse_accuracy_estimate": result.get("collapse_accuracy_estimate", 0)
    }
    (base_dir() / "metrics.json").write_text(json.dumps(metrics))
    return collapse_map
