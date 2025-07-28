# See architecture: docs/zoros_architecture.md#component-overview
from __future__ import annotations

from pydantic import BaseModel


class SpinOptions(BaseModel):
    """Options for :class:`Spinner` operations."""

    summary: bool = False
    translate: bool = False

    model_config = {"extra": "allow"}
