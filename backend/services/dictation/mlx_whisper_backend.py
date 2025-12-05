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
        import gc

        repo = "mlx-community/whisper-turbo" if self.model_name == "large-v3-turbo" else self.model_name

        try:
            # Call transcribe directly; avoid caching complications
            out = mlx_whisper.transcribe(
                wav_path,
                path_or_hf_repo=repo,
                fp16=True,
                word_timestamps=False,
                temperature=0.0,
                condition_on_previous_text=False,
            )
        except Exception as e:
            print(f"DEBUG: MLX transcription error: {e}")
            # Explicitly bail on ffmpeg missing rather than looping
            if "ffmpeg" in str(e):
                raise RuntimeError("FFmpeg is required for MLX transcription; install ffmpeg and retry") from e
            gc.collect()
            return ""

        gc.collect()
        return out.get("text", "").strip() if out else ""
    
    def cleanup(self):
        """Clean up model cache and free memory."""
        if self._model_cache is not None:
            print("DEBUG: Cleaning up MLX model cache")
            # Explicitly delete model to free GPU memory
            del self._model_cache
            self._model_cache = None
            
            # Platform-specific cleanup
            import gc
            import sys
            gc.collect()
            
            # On Windows, force additional memory cleanup
            if sys.platform == "win32":
                # Force multiple GC cycles for Windows memory cleanup
                for _ in range(3):
                    gc.collect()
                    
            print("DEBUG: MLX model cache cleared")
    
    def __enter__(self):
        """Context manager entry."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.cleanup() 
