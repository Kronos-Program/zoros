"""
🏆 LIMBO CHAMPION BACKEND 🏆
The ultimate dictation speed backend designed to break the 13.5s barrier
for 135-second audio files. Combines every optimization trick in the book.

Target: <13.5s for 135s audio (10x real-time factor)
Current Best: 14.05s (QueueBasedStreamingMLXWhisper)
Goal: Break through the final 0.55s barrier!
"""

import os
import time
import logging
import threading
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing as mp

import numpy as np
import soundfile as sf

from .mlx_whisper_backend import MLXWhisperBackend

logger = logging.getLogger(__name__)


class LimboChampionBackend(MLXWhisperBackend):
    """The ultimate dictation speed backend designed to win the limbo challenge."""
    
    # Global model cache shared across all instances
    _global_model_cache: Dict[str, Any] = {}
    _cache_lock = threading.Lock()
    _warmup_complete = False
    
    def __init__(self, model_name: str = "large-v3-turbo"):
        super().__init__(model_name)
        self._setup_champion_config()
        
        # Ensure warmup is complete
        if not self._warmup_complete:
            self._global_warmup()
    
    def _setup_champion_config(self):
        """Configure for absolute maximum speed."""
        # Metal GPU acceleration to the max
        os.environ['MLX_METAL_MEMORY_POOL'] = '1'
        os.environ['MLX_METAL_CAPTURE_ENABLED'] = '1'
        os.environ['MLX_METAL_BUFFER_OPTIMIZATION'] = '1'
        
        # Champion-level transcription parameters
        self.transcribe_params = {
            'fp16': True,                           # Half precision for max speed
            'batch_size': 64,                       # Large batch for M1 efficiency
            'word_timestamps': False,               # Disabled for speed
            'temperature': 0.0,                     # Deterministic and fast
            'condition_on_previous_text': False,    # No context dependency overhead
            'no_speech_threshold': 0.95,           # Ultra-aggressive silence detection
            'logprob_threshold': -0.3,             # Very permissive
            'compression_ratio_threshold': 1.2,     # Optimized for speech content
            'initial_prompt': None,                 # No prompt processing overhead
            'suppress_blank': True,                 # Skip blank segments immediately
            'suppress_tokens': [-1],               # Minimal token suppression
            'prepend_punctuations': "",            # No punctuation processing
            'append_punctuations': "",             # No punctuation processing
        }
        
        # Chunk processing optimization
        self.optimal_chunk_size = 25  # seconds - sweet spot for M1 processing
        self.chunk_overlap = 0.5      # minimal overlap for max speed
        self.max_parallel_chunks = mp.cpu_count()  # Use all cores
    
    @classmethod
    def _global_warmup(cls):
        """One-time global warmup for all instances."""
        if cls._warmup_complete:
            return
        
        logger.info("🔥 CHAMPION WARMUP: Preloading models for maximum speed...")
        
        try:
            import mlx_whisper
            
            # Preload the turbo model
            repo = "mlx-community/whisper-turbo"
            
            start_time = time.time()
            with cls._cache_lock:
                if repo not in cls._global_model_cache:
                    model = mlx_whisper.load_model(repo)
                    cls._global_model_cache[repo] = model
                    
                    warmup_time = time.time() - start_time
                    logger.info(f"🔥 Champion model loaded in {warmup_time:.2f}s")
                    
                    # Run a quick warmup transcription
                    dummy_audio = np.random.normal(0, 0.1, 16000)  # 1s dummy audio
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                        sf.write(tmp.name, dummy_audio, 16000)
                        
                        # Warmup transcription
                        mlx_whisper.transcribe(tmp.name, model=model, fp16=True, temperature=0.0)
                        Path(tmp.name).unlink()
                    
                    cls._warmup_complete = True
                    logger.info("🔥 Champion warmup complete!")
        
        except Exception as e:
            logger.error(f"❌ Champion warmup failed: {e}")
    
    def transcribe(self, wav_path: str) -> str:
        """Champion-level transcription with ultimate optimizations."""
        start_time = time.time()
        
        # Check if we should use chunked processing for large files
        audio_duration = self._get_audio_duration(wav_path)
        
        if audio_duration and audio_duration > 30:
            # Use parallel chunked processing for large files
            logger.info(f"🚀 Champion chunked processing for {audio_duration:.1f}s audio")
            return self._transcribe_chunked_parallel(wav_path)
        else:
            # Use direct processing for smaller files
            return self._transcribe_direct(wav_path)
    
    def _transcribe_direct(self, wav_path: str) -> str:
        """Direct transcription for smaller files."""
        import mlx_whisper
        
        repo = "mlx-community/whisper-turbo"
        
        with self._cache_lock:
            model = self._global_model_cache.get(repo)
        
        if model is None:
            logger.warning("⚠️ Model not cached, falling back to loading")
            result = mlx_whisper.transcribe(wav_path, path_or_hf_repo=repo, **self.transcribe_params)
        else:
            result = mlx_whisper.transcribe(wav_path, model=model, **self.transcribe_params)
        
        return result.get("text", "").strip() if result else ""
    
    def _transcribe_chunked_parallel(self, wav_path: str) -> str:
        """Parallel chunked transcription for maximum speed on large files."""
        start_time = time.time()
        
        # Create optimized chunks
        chunks = self._create_optimized_chunks(wav_path)
        logger.info(f"🔪 Created {len(chunks)} optimized chunks")
        
        # Process chunks in parallel with maximum workers
        chunk_results = self._process_chunks_champion_parallel(chunks)
        
        # Intelligent merging
        final_transcript = self._champion_merge_transcripts(chunk_results)
        
        # Cleanup
        self._cleanup_chunks(chunks)
        
        total_time = time.time() - start_time
        audio_duration = self._get_audio_duration(wav_path)
        if audio_duration:
            rtf = total_time / audio_duration
            logger.info(f"🏆 Champion parallel: {total_time:.2f}s (RTF: {rtf:.3f}x)")
        
        return final_transcript
    
    def _create_optimized_chunks(self, wav_path: str) -> List[Dict[str, Any]]:
        """Create optimally-sized chunks for parallel processing."""
        chunks = []
        
        with sf.SoundFile(wav_path) as f:
            sample_rate = f.samplerate
            total_frames = len(f)
            total_duration = total_frames / sample_rate
            
            chunk_frames = int(self.optimal_chunk_size * sample_rate)
            overlap_frames = int(self.chunk_overlap * sample_rate)
            step_frames = chunk_frames - overlap_frames
            
            start_frame = 0
            chunk_id = 0
            
            while start_frame < total_frames:
                end_frame = min(start_frame + chunk_frames, total_frames)
                
                # Read chunk data efficiently
                f.seek(start_frame)
                chunk_data = f.read(end_frame - start_frame)
                
                # Save chunk with optimized naming
                chunk_file = Path(tempfile.gettempdir()) / f"champion_chunk_{chunk_id:03d}_{time.time_ns()}.wav"
                sf.write(chunk_file, chunk_data, sample_rate)
                
                chunks.append({
                    'id': chunk_id,
                    'file': chunk_file,
                    'start_time': start_frame / sample_rate,
                    'end_time': end_frame / sample_rate,
                    'duration': (end_frame - start_frame) / sample_rate
                })
                
                start_frame += step_frames
                chunk_id += 1
                
                if end_frame >= total_frames:
                    break
        
        return chunks
    
    def _process_chunks_champion_parallel(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process chunks with champion-level parallelization."""
        import mlx_whisper
        
        def transcribe_chunk_champion(chunk):
            """Champion chunk transcription function."""
            chunk_start = time.time()
            
            # Use cached model for maximum speed
            with self._cache_lock:
                model = self._global_model_cache.get("mlx-community/whisper-turbo")
            
            if model:
                result = mlx_whisper.transcribe(
                    str(chunk['file']), 
                    model=model, 
                    **self.transcribe_params
                )
            else:
                result = mlx_whisper.transcribe(
                    str(chunk['file']), 
                    path_or_hf_repo="mlx-community/whisper-turbo",
                    **self.transcribe_params
                )
            
            transcript = result.get("text", "").strip() if result else ""
            chunk_time = time.time() - chunk_start
            
            return {
                'id': chunk['id'],
                'transcript': transcript,
                'start_time': chunk['start_time'],
                'end_time': chunk['end_time'],
                'duration': chunk['duration'],
                'transcribe_time': chunk_time
            }
        
        # Use maximum parallelization
        results = []
        with ThreadPoolExecutor(max_workers=self.max_parallel_chunks) as executor:
            future_to_chunk = {
                executor.submit(transcribe_chunk_champion, chunk): chunk 
                for chunk in chunks
            }
            
            for future in as_completed(future_to_chunk):
                chunk = future_to_chunk[future]
                try:
                    result = future.result(timeout=60)  # 60s timeout per chunk
                    results.append(result)
                    logger.info(f"🏆 Chunk {result['id']}: {result['transcribe_time']:.2f}s")
                except Exception as e:
                    logger.error(f"❌ Chunk {chunk['id']} failed: {e}")
        
        # Sort by chunk ID to maintain order
        results.sort(key=lambda x: x['id'])
        return results
    
    def _champion_merge_transcripts(self, chunk_results: List[Dict[str, Any]]) -> str:
        """Champion-level intelligent transcript merging."""
        if not chunk_results:
            return ""
        
        if len(chunk_results) == 1:
            return chunk_results[0]['transcript']
        
        # Simple but effective merging for maximum speed
        # TODO: Could add intelligent overlap detection for even better quality
        merged_parts = []
        
        for result in chunk_results:
            transcript = result['transcript'].strip()
            if transcript:
                merged_parts.append(transcript)
        
        return " ".join(merged_parts)
    
    def _cleanup_chunks(self, chunks: List[Dict[str, Any]]):
        """Clean up temporary chunk files."""
        for chunk in chunks:
            try:
                chunk['file'].unlink()
            except:
                pass
    
    def _get_audio_duration(self, wav_path: str) -> Optional[float]:
        """Fast audio duration calculation."""
        try:
            with sf.SoundFile(wav_path) as f:
                return len(f) / f.samplerate
        except Exception:
            return None
    
    @classmethod
    def get_champion_status(cls) -> Dict[str, Any]:
        """Get champion backend status."""
        with cls._cache_lock:
            return {
                "warmup_complete": cls._warmup_complete,
                "cached_models": list(cls._global_model_cache.keys()),
                "cache_size": len(cls._global_model_cache),
                "cpu_count": mp.cpu_count(),
                "champion_ready": cls._warmup_complete and len(cls._global_model_cache) > 0
            }


def create_limbo_champion() -> LimboChampionBackend:
    """Create the ultimate limbo champion backend."""
    return LimboChampionBackend("large-v3-turbo")