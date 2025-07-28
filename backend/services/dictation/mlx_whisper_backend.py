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
        
        # Use the turbo model for large-v3-turbo, otherwise use model_name as HF repo
        if self.model_name == "large-v3-turbo":
            repo = "mlx-community/whisper-turbo"
        else:
            repo = self.model_name
        
        # Check if we have a cached model
        if self._model_cache is None:
            print(f"DEBUG: Loading MLX model {repo} for first time")
            # Load model once and cache it
            try:
                self._model_cache = mlx_whisper.load_models(repo)
                print(f"DEBUG: MLX model {repo} loaded and cached")
            except Exception as e:
                print(f"DEBUG: MLX model loading failed, falling back to transcribe: {e}")
                # Fallback to direct transcribe if load_model fails
                out = mlx_whisper.transcribe(
                    wav_path, 
                    path_or_hf_repo=repo,
                    fp16=True,
                    word_timestamps=False,
                    temperature=0.0,
                    condition_on_previous_text=False
                )
                return out.get("text", "").strip() if out else ""
        
        # Use cached model for transcription
        try:
            if hasattr(mlx_whisper, 'transcribe_with_model') and self._model_cache:
                # Use cached model if API supports it
                out = mlx_whisper.transcribe_with_model(
                    self._model_cache,
                    wav_path,
                    fp16=True,
                    word_timestamps=False,
                    temperature=0.0,
                    condition_on_previous_text=False
                )
            else:
                # Fallback to regular transcribe
                out = mlx_whisper.transcribe(
                    wav_path, 
                    path_or_hf_repo=repo,
                    fp16=True,
                    word_timestamps=False,
                    temperature=0.0,
                    condition_on_previous_text=False
                )
        except Exception as e:
            print(f"DEBUG: MLX transcription error: {e}")
            # Force garbage collection on error
            self._model_cache = None
            gc.collect()
            return ""
        
        # Force garbage collection after transcription to free temporary memory
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