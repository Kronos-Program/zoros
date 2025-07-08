from __future__ import annotations

from typing import List

from source.core.models.fiber import Fiber

from .base_fibrizer import BaseFibrizer


class SourceFibrizer(BaseFibrizer):
    """Fold level 2 summarizer providing source faithful content."""

    def fibrize(self, fiber: Fiber) -> List[Fiber]:
        text = fiber.content.strip()
        if len(text) < 100:
            return []
        template = self.options.prompt_templates.get(2, "{text}")
        prompt = template.format(text=text)
        summary = self._run_model(prompt).strip()
        child = self._create_fiber(summary, 2, fiber.id)
        return [child]


class ExpandedFibrizer(BaseFibrizer):
    """Fold level 3 summarizer producing expanded explanation."""

    def fibrize(self, fiber: Fiber) -> List[Fiber]:
        text = fiber.content.strip()
        if len(text) < 100:
            return []
        template = self.options.prompt_templates.get(3, "{text}")
        prompt = template.format(text=text)
        summary = self._run_model(prompt).strip()
        child = self._create_fiber(summary, 3, fiber.id)
        return [child]
