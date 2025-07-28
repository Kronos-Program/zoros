"""
Model caching system for transcription backends.

This module provides a caching mechanism to avoid repeated model loading,
significantly improving transcription performance for subsequent operations.

Spec: docs/requirements/dictation_requirements.md#performance-requirements
Tests: tests/test_transcription_performance.py#test_model_caching
Integration: source/dictation_backends/ for backend implementations
"""
import time
from typing import Dict, Any, Optional
from zoros.logger import get_logger
from pathlib import Path
import threading

logger = get_logger(__name__)


class ModelCache:
    """Cache for loaded transcription models to improve performance.
    
    This class provides a thread-safe caching mechanism for transcription
    models, avoiding the overhead of repeated model loading.
    
    Spec: docs/requirements/dictation_requirements.md#model-caching
    Tests: tests/test_transcription_performance.py#test_model_caching
    Integration: source/interfaces/intake/main.py#transcribe_audio
    """
    
    def __init__(self, max_size: int = 5, ttl_seconds: int = 3600):
        """Initialize the model cache.
        
        Args:
            max_size: Maximum number of models to cache
            ttl_seconds: Time-to-live for cached models in seconds
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.lock = threading.RLock()
        
        # Performance metrics
        self.hits = 0
        self.misses = 0
        self.load_times: Dict[str, float] = {}
    
    def get_model(self, backend: str, model: str) -> Optional[Any]:
        """Get a cached model or load it if not cached.
        
        Args:
            backend: Backend name (e.g., "MLXWhisper", "FasterWhisper")
            model: Model name (e.g., "small", "large-v3-turbo")
            
        Returns:
            Loaded model instance or None if loading failed
        """
        cache_key = f"{backend}_{model}"
        
        with self.lock:
            # Check if model is cached and not expired
            if cache_key in self.cache:
                cached_item = self.cache[cache_key]
                if not self._is_expired(cached_item):
                    self.hits += 1
                    logger.debug(f"Model cache hit: {cache_key}")
                    return cached_item['model']
                else:
                    # Remove expired item
                    del self.cache[cache_key]
            
            self.misses += 1
            logger.debug(f"Model cache miss: {cache_key}")
            
            # Load the model
            start_time = time.time()
            try:
                model_instance = self._load_model(backend, model)
                load_time = time.time() - start_time
                
                if model_instance:
                    self._cache_model(cache_key, model_instance, load_time)
                    logger.info(f"Loaded model {cache_key} in {load_time:.2f}s")
                    return model_instance
                else:
                    logger.error(f"Failed to load model: {cache_key}")
                    return None
                    
            except Exception as e:
                logger.error(f"Error loading model {cache_key}: {e}")
                return None
    
    def _load_model(self, backend: str, model: str) -> Optional[Any]:
        """Load a model using the specified backend.
        
        Args:
            backend: Backend name
            model: Model name
            
        Returns:
            Loaded model instance or None
        """
        try:
            if backend == "MLXWhisper":
                from .mlx_whisper_backend import MLXWhisperBackend
                backend_instance = MLXWhisperBackend(model)
                return backend_instance
                
            elif backend == "FasterWhisper":
                from faster_whisper import WhisperModel  # type: ignore
                return WhisperModel(model)
                
            elif backend == "WhisperCPP":
                from .whisper_cpp_backend import WhisperCPPBackend
                backend_instance = WhisperCPPBackend(model)
                return backend_instance
                
            elif backend == "StandardWhisper":
                import whisper  # type: ignore
                return whisper.load_model(model)
                
            else:
                logger.error(f"Unknown backend: {backend}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to load {backend}/{model}: {e}")
            return None
    
    def _cache_model(self, cache_key: str, model: Any, load_time: float) -> None:
        """Cache a loaded model.
        
        Args:
            cache_key: Cache key for the model
            model: Model instance to cache
            load_time: Time taken to load the model
        """
        # Evict oldest item if cache is full
        if len(self.cache) >= self.max_size:
            self._evict_oldest()
        
        self.cache[cache_key] = {
            'model': model,
            'load_time': load_time,
            'cached_at': time.time(),
            'access_count': 0
        }
        
        self.load_times[cache_key] = load_time
    
    def _is_expired(self, cached_item: Dict[str, Any]) -> bool:
        """Check if a cached item has expired.
        
        Args:
            cached_item: Cached item dictionary
            
        Returns:
            True if the item has expired
        """
        return time.time() - cached_item['cached_at'] > self.ttl_seconds
    
    def _evict_oldest(self) -> None:
        """Evict the oldest cached item."""
        if not self.cache:
            return
        
        oldest_key = min(self.cache.keys(), 
                        key=lambda k: self.cache[k]['cached_at'])
        del self.cache[oldest_key]
        logger.debug(f"Evicted oldest model from cache: {oldest_key}")
    
    def clear_cache(self) -> None:
        """Clear all cached models."""
        with self.lock:
            self.cache.clear()
            self.load_times.clear()
            logger.info("Model cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        with self.lock:
            total_requests = self.hits + self.misses
            hit_rate = self.hits / total_requests if total_requests > 0 else 0
            
            return {
                'cache_size': len(self.cache),
                'max_size': self.max_size,
                'hits': self.hits,
                'misses': self.misses,
                'hit_rate': hit_rate,
                'cached_models': list(self.cache.keys()),
                'average_load_time': sum(self.load_times.values()) / len(self.load_times) if self.load_times else 0
            }
    
    def preload_models(self, models: list[tuple[str, str]]) -> None:
        """Preload specified models in background.
        
        Args:
            models: List of (backend, model) tuples to preload
        """
        def _preload():
            for backend, model in models:
                try:
                    logger.info(f"Preloading model: {backend}/{model}")
                    self.get_model(backend, model)
                except Exception as e:
                    logger.error(f"Failed to preload {backend}/{model}: {e}")
        
        # Start preloading in background thread
        thread = threading.Thread(target=_preload, daemon=True)
        thread.start()
        logger.info(f"Started preloading {len(models)} models in background")


# Global model cache instance
_model_cache: Optional[ModelCache] = None


def get_model_cache() -> ModelCache:
    """Get the global model cache instance.
    
    Returns:
        Global ModelCache instance
    """
    global _model_cache
    if _model_cache is None:
        _model_cache = ModelCache()
    return _model_cache


def clear_global_cache() -> None:
    """Clear the global model cache."""
    global _model_cache
    if _model_cache:
        _model_cache.clear_cache()


def get_cache_stats() -> Dict[str, Any]:
    """Get global cache statistics.
    
    Returns:
        Cache statistics dictionary
    """
    return get_model_cache().get_stats() 