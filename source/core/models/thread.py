# See architecture: docs/zoros_architecture.md#component-overview
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, conint

from .fiber import Fiber, TransformOptions


def resolve_fiber(fiber_id: UUID) -> Optional[Fiber]:  # pragma: no cover - stub
    """Placeholder fiber resolver. Replaced by DAO at runtime."""
    return None


class Thread(BaseModel):
    """Sequence of fibers forming a routine."""

    id: UUID
    name: str
    fiber_ids: List[UUID] = Field(default_factory=list)
    status: Literal["open", "in-progress", "closed"]
    priority: conint(ge=1, le=5) = 3
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)

    model_config = {"frozen": False}

    def add_fiber(self, fiber_id: UUID, position: int | None = None) -> None:
        if resolve_fiber(fiber_id) is None:
            raise ValueError("Fiber does not exist")
        if position is None or position > len(self.fiber_ids):
            self.fiber_ids.append(fiber_id)
        else:
            pos = max(0, position)
            self.fiber_ids.insert(pos, fiber_id)
        self.updated_at = datetime.utcnow()

    def remove_fiber(self, fiber_id: UUID) -> None:
        if fiber_id in self.fiber_ids:
            self.fiber_ids.remove(fiber_id)
            self.updated_at = datetime.utcnow()

    def reorder_fibers(self, new_order: List[UUID]) -> None:
        if set(new_order) != set(self.fiber_ids):
            raise ValueError("Fiber IDs mismatch")
        self.fiber_ids = list(new_order)
        self.updated_at = datetime.utcnow()

    def summarize(self) -> str:
        contents = []
        for fid in self.fiber_ids:
            fiber = resolve_fiber(fid)
            if fiber:
                contents.append(fiber.content)
        temp = Fiber(
            id=self.id,
            content=" ".join(contents),
            type="text",
            metadata={},
            revision_count=0,
            created_at=datetime.utcnow(),
            source="thread",
        )
        return temp.generate_summary()

    def to_json(self) -> Dict[str, Any]:
        """Return a JSON-serialisable representation of this Thread."""
        return {
            "id": str(self.id),
            "name": self.name,
            "fiber_ids": [str(fid) for fid in self.fiber_ids],
            "status": self.status,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": {
                k: (str(v) if isinstance(v, UUID) else [str(i) for i in v] if isinstance(v, list) else v)
                for k, v in self.metadata.items()
            },
            "tags": self.tags,
        }
