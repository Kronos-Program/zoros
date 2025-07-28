# See architecture: docs/zoros_architecture.md#component-overview
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TransformOptions(BaseModel):
    """Options for :py:meth:`Fiber.transform`."""

    language: Optional[str] = None
    tags: Optional[List[str]] = None


class Fiber(BaseModel):
    """Core data unit representing a single piece of content.

    Example
    -------
    >>> f = Fiber(id=uuid4(), content="hello", type="text", metadata={}, revision_count=0,
    ...           created_at=datetime.utcnow(), source="test")
    >>> f.add_tag("Greeting")
    >>> f.tags
    ['greeting']
    """

    id: UUID
    content: str
    type: Literal["text", "audio", "manual", "external"]
    embeddings: Optional[List[float]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    revision_count: int = 0
    created_at: datetime
    source: str
    tags: List[str] = Field(default_factory=list)

    model_config = {"frozen": False}

    def add_tag(self, tag: str) -> None:
        norm = tag.lower()
        if norm not in self.tags:
            self.tags.append(norm)

    def remove_tag(self, tag: str) -> None:
        norm = tag.lower()
        if norm in self.tags:
            self.tags.remove(norm)

    def generate_summary(self) -> str:
        """Return a short summary using LanguageService if available."""
        try:
            from source.language_service import LanguageService

            service = LanguageService()
            resp = service.complete_turn(str(self.id), {"content": self.content})
            summary = resp.get("content", "")
            return summary[:128]
        except Exception:
            return self.content[:128]

    def transform(self, target_type: str, options: TransformOptions) -> "Fiber":
        """Return a transformed copy of this Fiber."""
        new = self.copy(deep=True)
        new.id = uuid4()
        new.created_at = datetime.utcnow()
        new.revision_count = self.revision_count + 1

        if target_type == "summary":
            new.content = self.generate_summary()
        elif target_type == "translation":
            lang = options.language or "unknown"
            new.content = f"[{lang}] {self.content}"
        elif target_type == "tag_extract":
            extracted = options.tags or []
            for t in extracted:
                new.add_tag(t)
        else:
            raise ValueError(f"Unsupported transform type: {target_type}")
        return new

    def to_json(self) -> Dict[str, Any]:
        """Return a JSON-serialisable representation of this Fiber."""
        public_meta = {k: v for k, v in self.metadata.items() if not str(k).startswith("_")}
        return {
            "id": str(self.id),
            "content": self.content,
            "type": self.type,
            "embeddings": self.embeddings,
            "metadata": public_meta,
            "revision_count": self.revision_count,
            "created_at": self.created_at.isoformat(),
            "source": self.source,
            "tags": self.tags,
        }


class WarpFiber(Fiber):
    def anchor(self, position: int) -> None:  # pragma: no cover - stub
        pass

    def interlace(self, thread_id: UUID, slot: int) -> None:  # pragma: no cover - stub
        pass


class WeftFiber(Fiber):
    def anchor(self, position: int) -> None:  # pragma: no cover - stub
        pass

    def interlace(self, thread_id: UUID, slot: int) -> None:  # pragma: no cover - stub
        pass
