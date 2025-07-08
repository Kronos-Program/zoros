from .standard_whisper_backend import WhisperBackend

class MLXWhisperBackend(WhisperBackend):
    """MLX Whisper backend using Metal acceleration via mlx_whisper."""
    def __init__(self, model_name: str):
        super().__init__(model_name)
        try:
            import mlx_whisper  # noqa: F401
        except ImportError:
            raise RuntimeError("mlx_whisper is not installed. Please install with 'pip install mlx_whisper'.")
        self.model_name = model_name
        self._model_cache = None

    def transcribe(self, wav_path: str) -> str:
        import mlx_whisper
        # Use the turbo model for large-v3-turbo, otherwise use model_name as HF repo
        if self.model_name == "large-v3-turbo":
            repo = "mlx-community/whisper-turbo"
        else:
            repo = self.model_name
        
        # Optimize for M1/M2 Metal performance
        out = mlx_whisper.transcribe(
            wav_path, 
            path_or_hf_repo=repo,
            fp16=True,  # Enable half-precision for speed
            word_timestamps=False,  # Disable if not needed for speed
            temperature=0.0,  # Deterministic output, faster
            condition_on_previous_text=False  # Disable for faster processing
        )
        return out.get("text", "").strip() if out else "" 