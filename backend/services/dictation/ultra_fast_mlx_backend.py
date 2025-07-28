"""
Ultra-Fast MLX Backend for Sub-5-Second Dictation
Optimized specifically for 3-5 second stop-to-text target on M1/M2 Macs.

This backend implements aggressive optimizations for the shortest possible
latency between clicking stop and seeing transcribed text.
"""

import logging
import os
import time
import threading
from pathlib import Path
from typing import Optional, Dict, Any, Callable
import tempfile

from .mlx_whisper_backend import MLXWhisperBackend

logger = logging.getLogger(__name__)


class UltraFastMLXBackend(MLXWhisperBackend):
    """Ultra-optimized MLX backend for sub-5-second stop-to-text latency."""
    
    # Class-level model cache for instant access
    _model_cache: Dict[str, Any] = {}
    _cache_lock = threading.Lock()
    _preloaded = False
    
    def __init__(self, model_name: str = "large-v3-turbo"):
        super().__init__(model_name)
        self._setup_ultra_fast_config()
        
        # Preload model on first instantiation
        if not self._preloaded:
            self._preload_model()
    
    def _setup_ultra_fast_config(self):
        """Configure for absolute minimum latency."""
        # Metal optimization
        os.environ['MLX_METAL_MEMORY_POOL'] = '1'
        os.environ['MLX_METAL_CAPTURE_ENABLED'] = '1'
        
        # Ultra-aggressive transcription parameters
        self.transcribe_params = {
            'fp16': True,                           # Half precision
            'batch_size': 32,                       # Larger batch for M1 efficiency  
            'word_timestamps': False,               # Disabled for speed
            'temperature': 0.0,                     # Deterministic
            'condition_on_previous_text': False,    # No context dependency
            'no_speech_threshold': 0.9,            # Very aggressive silence detection
            'logprob_threshold': -0.5,             # Less conservative
            'compression_ratio_threshold': 1.5,     # Optimize for speech
            'initial_prompt': None,                 # No prompt overhead
            'suppress_blank': True,                 # Skip blank segments
            'suppress_tokens': [-1],               # Suppress unnecessary tokens
        }
    
    def _preload_model(self):
        """Preload model into memory for instant access."""
        try:
            import mlx_whisper
            
            repo = self._get_optimized_repo()
            start_time = time.time()
            
            logger.info(f"Preloading ultra-fast model: {repo}")
            
            with self._cache_lock:
                if repo not in self._model_cache:
                    # Load model with maximum optimization
                    model = mlx_whisper.load_models(repo)
                    self._model_cache[repo] = model
                    
                    load_time = time.time() - start_time
                    logger.info(f"Model preloaded in {load_time:.2f}s")
                    
                    # Set class flag to prevent repeated preloading
                    UltraFastMLXBackend._preloaded = True
                    
        except Exception as e:
            logger.error(f"Failed to preload model: {e}")
    
    def _get_optimized_repo(self) -> str:
        """Get the fastest model repository for the configuration."""
        # Always use turbo for ultra-fast processing
        if self.model_name in ["large-v3-turbo", "large-v3", "large-v2", "large"]:
            return "mlx-community/whisper-turbo"
        elif self.model_name in ["medium"]:
            return "mlx-community/whisper-medium-mlx"
        elif self.model_name in ["small"]:
            return "mlx-community/whisper-small-mlx"
        else:
            # Default to turbo for maximum speed
            return "mlx-community/whisper-turbo"
    
    def transcribe(self, wav_path: str) -> str:
        """Ultra-fast transcription with aggressive optimizations."""
        import mlx_whisper
        
        start_time = time.time()
        repo = self._get_optimized_repo()
        
        try:
            # Use cached model for instant access
            with self._cache_lock:
                cached_model = self._model_cache.get(repo)
            
            if cached_model is not None:
                # Direct transcription with cached model
                result = mlx_whisper.transcribe(
                    wav_path,
                    model=cached_model,
                    **self.transcribe_params
                )
            else:
                # Fallback to standard loading (shouldn't happen after preload)
                logger.warning("Model not cached, using fallback loading")
                result = mlx_whisper.transcribe(
                    wav_path,
                    path_or_hf_repo=repo,
                    **self.transcribe_params
                )
            
            text = result.get("text", "").strip() if result else ""
            
            # Log performance metrics
            transcribe_time = time.time() - start_time
            audio_duration = self._get_audio_duration(wav_path)
            
            if audio_duration:
                rtf = transcribe_time / audio_duration
                logger.info(f"Ultra-fast transcription: {transcribe_time:.2f}s, RTF: {rtf:.2f}x")
                
                # Warn if not meeting target
                if transcribe_time > 3.0:
                    logger.warning(f"Transcription time {transcribe_time:.2f}s exceeds 3s target")
            
            return text
            
        except Exception as e:
            logger.error(f"Ultra-fast transcription failed: {e}")
            raise
    
    def _get_audio_duration(self, wav_path: str) -> Optional[float]:
        """Quick audio duration calculation."""
        try:
            import soundfile as sf
            with sf.SoundFile(wav_path) as f:
                return len(f) / f.samplerate
        except Exception:
            return None
    
    @classmethod
    def warmup(cls) -> None:
        """Warmup the backend for first-use optimization."""
        logger.info("Warming up ultra-fast backend...")
        
        # Create dummy audio for warmup
        try:
            import numpy as np
            import soundfile as sf
            
            # Generate 2 seconds of dummy audio
            dummy_audio = np.random.normal(0, 0.1, 32000)  # 2s at 16kHz
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                sf.write(tmp_file.name, dummy_audio, 16000)
                tmp_path = tmp_file.name
            
            # Run warmup transcription
            backend = cls()
            result = backend.transcribe(tmp_path)
            
            # Clean up
            Path(tmp_path).unlink(missing_ok=True)
            
            logger.info(f"Warmup complete: '{result[:50]}...'")
            
        except Exception as e:
            logger.error(f"Warmup failed: {e}")
    
    @classmethod
    def get_cache_info(cls) -> Dict[str, Any]:
        """Get cache status information."""
        with cls._cache_lock:
            return {
                "cached_models": list(cls._model_cache.keys()),
                "preloaded": cls._preloaded,
                "cache_size": len(cls._model_cache)
            }


# Convenience factory function
def create_ultra_fast_backend() -> UltraFastMLXBackend:
    """Create an ultra-fast MLX backend optimized for sub-5-second latency."""
    return UltraFastMLXBackend("large-v3-turbo")