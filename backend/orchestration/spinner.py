# See architecture: docs/zoros_architecture.md#component-overview
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Union
from uuid import UUID, uuid4

from pydantic import BaseModel

from source.core.models.fiber import Fiber
from source.core.models.thread import Thread
from source.core.models.spin_options import SpinOptions


class SpinFiber(BaseModel):
    """Metadata fiber representing a spin lineage event."""

    id: UUID
    created_at: datetime
    spinner_name: str
    source_fiber_ids: List[UUID]

    def to_json(self) -> dict:
        return {
            "id": str(self.id),
            "created_at": self.created_at.isoformat(),
            "spinner_name": self.spinner_name,
            "source_fiber_ids": [str(fid) for fid in self.source_fiber_ids],
        }


class Spinner:
    """Primitive spinner that bundles fibers into a new thread."""

    def __init__(self, name: str = "spinner") -> None:
        self.name = name

    def _save_thread(self, thread: Thread) -> None:
        base = Path(os.getenv("DATA_DIR", "data")) / "snapshots" / "threads"
        base.mkdir(parents=True, exist_ok=True)
        path = base / f"{thread.id}.json"
        path.write_text(json.dumps(thread.to_json()))

    def spin(self, fibers: Union[Fiber, List[Fiber]], options: SpinOptions | None = None) -> Thread:
        options = options or SpinOptions()
        batch = [fibers] if isinstance(fibers, Fiber) else list(fibers)

        spin_fiber = SpinFiber(
            id=uuid4(),
            created_at=datetime.utcnow(),
            spinner_name=self.name,
            source_fiber_ids=[f.id for f in batch],
        )

        thread = Thread(
            id=uuid4(),
            name=f"thread-{spin_fiber.id}",
            fiber_ids=[f.id for f in batch],
            status="open",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={
                "spin_fiber_id": spin_fiber.id,
                "source_fiber_ids": spin_fiber.source_fiber_ids,
            },
            tags=["spun"],
        )

        self._save_thread(thread)
        return thread

    def batch_spin(
        self, batch: List[Union[Fiber, List[Fiber]]], options: SpinOptions | None = None
    ) -> List[Thread]:
        threads: List[Thread] = []
        for item in batch:
            try:
                threads.append(self.spin(item, options=options))
            except Exception as exc:  # pragma: no cover - log & continue
                print(f"Spin error: {exc}")
        return threads
