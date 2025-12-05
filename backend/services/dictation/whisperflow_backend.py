from __future__ import annotations

import logging

from .standard_whisper_backend import WhisperBackend


class WhisperFlowBackend(WhisperBackend):
    """WhisperFlow backend wrapper.

    This backend integrates the optional `whisperflow` engine. Import of the
    heavy dependency is deferred until initialization so the backend registry
    can fail gracefully when the package is missing. The interface mirrors the
    other Whisper backends.
    """

    def __init__(self, model_name: str) -> None:  # noqa: D401 - simple init
        super().__init__(model_name)
        try:
            from whisperflow import load_model  # type: ignore
        except Exception as exc:  # pragma: no cover - dependency missing
            raise ImportError("whisperflow package not installed") from exc

        self.model = load_model(model_name)

    def transcribe(self, audio_path: str) -> str:  # noqa: D401 - simple method
        try:
            result = self.model.transcribe(audio_path)
            return result.get("text", "").strip()
        except Exception as err:  # pragma: no cover - passthrough
            logging.error("WhisperFlow failed: %s", err)
            raise
