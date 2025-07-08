from __future__ import annotations

import logging


class WhisperBackend:
    """Base interface for whisper backends."""

    def __init__(self, model_name: str) -> None:  # noqa: D401 - simple init
        self.model_name = model_name

    def transcribe(self, audio_path: str) -> str:  # noqa: D401 - simple method
        raise NotImplementedError


class StandardOpenAIWhisperBackend(WhisperBackend):
    """CPU-based transcription using the upstream whisper package."""

    def __init__(self, model_name: str) -> None:
        super().__init__(model_name)
        import whisper  # type: ignore

        self.model = whisper.load_model(model_name)

    def transcribe(self, audio_path: str) -> str:
        try:
            result = self.model.transcribe(audio_path)
            return result.get("text", "").strip()
        except Exception as err:  # pragma: no cover - passthrough
            logging.error("StandardWhisper failed: %s", err)
            raise
