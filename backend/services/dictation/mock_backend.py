class MockBackend:
    """Return fixed text for any audio input.
    
    This backend doesn't depend on any external libraries and always returns
    the same text. It's useful for testing and development.
    """

    def __init__(self, model_name: str, text: str = "mock transcript") -> None:
        self.model_name = model_name
        self.text = text

    def transcribe(self, audio_path: str) -> str:
        """Return the mock text regardless of input."""
        return self.text
