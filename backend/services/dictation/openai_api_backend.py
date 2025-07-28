from __future__ import annotations

import logging
import os
from openai import OpenAI

from .standard_whisper_backend import WhisperBackend


class OpenAIAPIBackend(WhisperBackend):
    """Transcribe using the OpenAI Whisper API."""

    def __init__(self, model_name: str) -> None:
        super().__init__(model_name)
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        self.client = OpenAI(api_key=api_key)

    def transcribe(self, audio_path: str) -> str:
        """Transcribe audio via OpenAI Whisper API, always using the 'whisper-1' model."""
        try:
            model_to_use = "whisper-1"
            if self.model_name != model_to_use:
                logging.debug(
                    "Remapping OpenAI Whisper API model '%s' to '%s'", self.model_name, model_to_use
                )
            with open(audio_path, "rb") as fh:
                resp = self.client.audio.transcriptions.create(
                    model=model_to_use,
                    file=fh,
                )
            return resp.text.strip()
        except Exception as err:  # pragma: no cover - passthrough
            logging.error("OpenAI API backend failed: %s", err)
            raise
