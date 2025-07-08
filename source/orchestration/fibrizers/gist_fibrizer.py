from __future__ import annotations

from typing import List

from source.core.models.fiber import Fiber

from .base_fibrizer import BaseFibrizer


class GistFibrizer(BaseFibrizer):
    """Fold level 1 summarizer generating a short gist."""

    def fibrize(self, fiber: Fiber) -> List[Fiber]:
        text = fiber.content.strip()
        if len(text) < 50:
            return []
        template = self.options.prompt_templates.get(1, "{text}")
        prompt = template.format(text=text)
        summary = self._run_model(prompt).strip()
        if len(summary) > len(text):
            summary = summary[: len(text)]
        child = self._create_fiber(summary, 1, fiber.id)
        return [child]
