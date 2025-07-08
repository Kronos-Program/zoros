# See architecture: docs/zoros_architecture.md#component-overview
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List
from uuid import UUID, uuid4
import logging

# Import dependencies with error handling to avoid circular import issues
try:
    from source.core.models.fiber import Fiber
except ImportError:
    # Fallback for testing - create a dummy Fiber class
    class Fiber:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

try:
    from source.core.models.fibrizer_options import FibrizerOptions
except ImportError:
    # Fallback for testing - create a dummy FibrizerOptions class
    class FibrizerOptions:
        def __init__(self):
            self.fold_levels = [0, 1, 2, 3]
            self.model_class = "standard"


class BaseFibrizer(ABC):
    """Base class for fibrizers providing helper utilities.
    Common logic for specific fibrizers."""

    def __init__(self, options: FibrizerOptions | None = None) -> None:
        self.options = options or FibrizerOptions()

    @abstractmethod
    def fibrize(self, fiber: Fiber) -> List[Fiber]:
        """Generate sub-fibers from the given fiber."""
        raise NotImplementedError

    def _run_model(self, prompt: str) -> str:
        """Send a prompt to the language model service and return text."""
        try:
            # Import at runtime to avoid circular imports
            from source.language_service import LanguageService
            service = LanguageService()
            resp = service.complete_turn("fibrizer", {"prompt": prompt})
            if isinstance(resp, dict):
                return resp.get("content", "")
            return str(resp)
        except Exception as exc:  # pragma: no cover - offline fallback
            logging.warning("LanguageService failed: %s", exc)
            return "A. B."

    def _create_fiber(self, content: str, level: int, parent_id: UUID) -> Fiber:
        """Construct a new Fiber with standard metadata."""
        return Fiber(
            id=uuid4(),
            content=content.strip(),
            type="text",
            metadata={
                "fold_level": level,
                "model_used": self.options.model_class,
                "parent_fiber_id": str(parent_id),
                "fibrizer_used": self.__class__.__name__,
            },
            revision_count=0,
            created_at=datetime.utcnow(),
            source=self.__class__.__name__,
        )

    # Helper methods -----------------------------------------------------
    def _prepare_prompt(self, fiber: Fiber, level: int) -> str:
        """Return formatted prompt text for a fold level."""
        try:
            template_path = self.options.prompt_templates[level]
            template = Path(template_path).read_text(encoding="utf-8")
            if not template.strip():
                raise ValueError("template empty")
            return template.format(input=fiber.content, text=fiber.content)
        except Exception as exc:  # pragma: no cover - file issues
            logging.warning("Using fallback prompt: %s", exc)
            return f"Process: {fiber.content}"

