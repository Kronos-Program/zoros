from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from source.language_service import _load_simple_yaml

from .cli_wrapper import WhisperCLICaller


CFG_PATH = Path(__file__).resolve().parent.parent / "config" / "whisper.yaml"


def load_config(path: Optional[str] = None) -> dict[str, Any]:
    cfg_file = Path(os.path.expanduser(path)) if path else CFG_PATH
    if not cfg_file.exists():
        return {}
    return _load_simple_yaml(cfg_file)


def create_whisper_service(config_path: Optional[str] = None) -> WhisperCLICaller:
    cfg = load_config(config_path)
    binary_path = cfg.get("binary_path", "whisper")
    model_path = cfg.get("model_path", "models/ggml-base.bin")
    service = WhisperCLICaller(binary_path=binary_path, model_path=model_path)
    service.default_beam_size = int(cfg.get("default_beam_size", 5))  # type: ignore[attr-defined]
    service.enable_lexicon = str(cfg.get("enable_lexicon", "false")).lower() == "true"  # type: ignore[attr-defined]
    service.default_prompt = cfg.get("default_prompt", "")  # type: ignore[attr-defined]
    return service
