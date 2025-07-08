from __future__ import annotations

from pathlib import Path
from typing import List

from source.core.models.fiber import Fiber
from source.orchestration.fibrizers.base_fibrizer import BaseFibrizer


class SplitFibrizer(BaseFibrizer):
    """Fold level 0 fibrizer that splits a fiber into sentence-level fibers."""

    def fibrize(self, fiber: Fiber) -> List[Fiber]:
        template_path = Path(self.options.prompt_templates[0])
        prompt_template = template_path.read_text()
        try:
            prompt = prompt_template.format(input=fiber.content)
        except KeyError:
            prompt = prompt_template.format(text=fiber.content)
        output = self._run_model(prompt)
        sentences = [line.strip() for line in output.splitlines() if line.strip()]
        children: List[Fiber] = []
        for sentence in sentences:
            child = self._create_fiber(sentence, level=0, parent_id=fiber.id)
            children.append(child)
        return children

