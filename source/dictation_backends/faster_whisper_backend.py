from __future__ import annotations

import logging

from .standard_whisper_backend import WhisperBackend


class FasterWhisperBackend(WhisperBackend):
    """Whisper implementation using `faster_whisper` with MPS support."""

    def __init__(self, model_name: str) -> None:
        super().__init__(model_name)
        from faster_whisper import WhisperModel  # type: ignore
        import torch

        device = "mps" if torch.backends.mps.is_available() else "cpu"
        compute_type = "float16" if device == "mps" else "float32"
        self.model = WhisperModel(model_name, device=device, compute_type=compute_type)

    def transcribe(self, audio_path: str) -> str:
        try:
            segments, _info = self.model.transcribe(audio_path)
            return "".join(segment.text for segment in segments).strip()
        except Exception as err:  # pragma: no cover - passthrough
            logging.error("FasterWhisper failed: %s", err)
            raise
