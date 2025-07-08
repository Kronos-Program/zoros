from .standard_whisper_backend import WhisperBackend

class MockBackend(WhisperBackend):
    """Return fixed text for any audio input."""

    def __init__(self, model_name: str, text: str = "mock transcript") -> None:
        super().__init__(model_name)
        self.text = text

    def transcribe(self, audio_path: str) -> str:
        return self.text
