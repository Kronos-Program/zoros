from __future__ import annotations

import importlib
from zoros.logger import get_logger
from datetime import datetime
from typing import Dict, List, Type
from uuid import UUID, uuid4

from source.core.models.fiber import Fiber
# Import LanguageService at runtime to avoid circular imports

from .base_fibrizer import BaseFibrizer

logger = get_logger(__name__)


class WarningFiber(Fiber):
    """Fiber representing a warning produced during fibrization."""

    pass


DEFAULT_FIBRIZERS: Dict[int, str] = {
    0: "split_fibrizer.SplitFibrizer",
    1: "gist_fibrizer.GistFibrizer",
    2: "source_expanded_fibrizer.SourceFibrizer",
    3: "source_expanded_fibrizer.ExpandedFibrizer",
}


class ChainFibrizer(BaseFibrizer):
    """Run a sequence of fibrizers over a single fiber."""

    FIBRIZER_MAP: Dict[int, str] = DEFAULT_FIBRIZERS

    def fibrize(self, fiber: Fiber) -> List[Fiber]:
        results: List[Fiber] = []
        # Import at runtime to avoid circular imports
        from source.language_service import LanguageService
        service = LanguageService()
        for level in self.options.fold_levels:
            target = self.FIBRIZER_MAP.get(level)
            if not target:
                logger.warning("No fibrizer registered for level %s", level)
                results.append(self._warning(f"No fibrizer for level {level}", fiber.id))
                continue
            try:
                if isinstance(target, str):
                    mod_name, cls_name = target.rsplit(".", 1)
                    module = importlib.import_module(f"{__package__}.{mod_name}")
                    klass: Type[BaseFibrizer] = getattr(module, cls_name)
                    inst = klass(self.options)
                elif isinstance(target, type):
                    inst = target(self.options)
                else:
                    inst = target(self.options)
                new_fibers = inst.fibrize(fiber)
                if self.options.embed and hasattr(service, "embed"):
                    for f in new_fibers:
                        try:
                            f.embeddings = service.embed(f.content)
                        except Exception as exc:  # pragma: no cover - log and continue
                            logger.warning("Embedding failed: %s", exc)
                results.extend(new_fibers)
            except Exception as exc:
                logger.warning("Fibrizer level %s failed: %s", level, exc)
                results.append(self._warning(str(exc), fiber.id))
        return results

    def _warning(self, message: str, parent_id: UUID) -> WarningFiber:
        return WarningFiber(
            id=uuid4(),
            content=message,
            type="text",
            metadata={
                "fold_level": -1,
                "parent_fiber_id": parent_id,
                "fibrizer_used": self.__class__.__name__,
                "warning": True,
            },
            revision_count=0,
            created_at=datetime.utcnow(),
            source="warning",
        )
