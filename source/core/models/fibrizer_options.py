# See architecture: docs/zoros_architecture.md#component-overview
from __future__ import annotations

from typing import Dict, List, Literal

from pydantic import BaseModel, Field


class FibrizerOptions(BaseModel):
    """Configuration model for Fibrizers.

    Example
    -------
    >>> FibrizerOptions(
    ...     fold_levels=[0, 1],
    ...     model_class="standard",
    ...     embed=False,
    ...     prompt_templates={0: "prompts/ultra.txt", 1: "prompts/gist.txt"},
    ... )
    """
    """Configuration options for fibrizers."""

    fold_levels: List[int] = Field(default_factory=lambda: [0, 1, 2, 3])
    model_class: Literal["reasoning", "standard", "lightweight"] = "standard"
    embed: bool = False
    prompt_templates: Dict[int, str] = Field(
        default_factory=lambda: {
            0: "prompts/ultra.txt",
            1: "prompts/gist.txt",
            2: "prompts/source.txt",
            3: "prompts/expanded.txt",
        }
    )
    include_documents: bool = False

    model_config = {"extra": "allow"}

