"""
Parallel MLX Whisper Backend - Metal GPU Optimized Streaming

This backend provides parallel chunk processing for MLX Whisper with Metal GPU
optimization. It processes audio in overlapping chunks using multiple workers
to achieve significant speedup over standard MLX Whisper.

WARNING: This backend has known Metal GPU command buffer conflicts on macOS
Apple Silicon that can cause segmentation faults. Use QueueBasedStreamingBackend
for production use.

Spec: docs/streaming_backend_plan.md#parallel-processing
Tests: tests/test_transcription_performance.py
Integration: source/interfaces/intake/main.py

Performance:
- Target: 3-5x speedup over standard MLX Whisper
- Chunk-based parallel processing
- Metal GPU acceleration with overlap handling

Known Issues:
- Metal GPU command buffer conflicts on macOS Apple Silicon
- Segmentation faults during parallel chunk processing
- GPU resource contention with multiple MLX Whisper instances

Dependencies:
- mlx_whisper for transcription
- numpy for audio processing
- concurrent.futures for parallel processing
"""

import logging
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import soundfile as sf

from .mlx_whisper_backend import MLXWhisperBackend

logger = logging.getLogger(__name__)


class ParallelMLXWhisperBackend(MLXWhisperBackend):
    """Parallel MLX Whisper backend with Metal GPU optimization.
    
    This backend processes audio in overlapping chunks using multiple workers
    to achieve significant speedup. However, it has known Metal GPU issues
    that can cause crashes on macOS Apple Silicon.
    
    WARNING: Use QueueBasedStreamingBackend for production use due to
    Metal GPU command buffer conflicts.
    
    Spec: docs/streaming_backend_plan.md#parallel-processing
    Tests: tests/test_transcription_performance.py
    Integration: source/interfaces/intake/main.py
    
    Performance Characteristics:
    - Parallel chunk processing with ThreadPoolExecutor
    - Overlapping chunks to maintain context
    - Metal GPU acceleration (with known issues)
    - Target 3-5x speedup over standard MLX Whisper
    
    Known Issues:
    - Metal GPU command buffer conflicts
    - Segmentation faults during parallel processing
    - GPU resource contention
    """
    
    def __init__(self, model: str = "small", chunk_duration: float = 10.0, 
                 overlap_duration: float = 2.0, max_workers: int = 2):
        """Initialize the parallel MLX Whisper backend.
        
        Args:
            model: Whisper model size (tiny, small, medium, large)
            chunk_duration: Duration of each audio chunk in seconds
            overlap_duration: Overlap between chunks in seconds
            max_workers: Maximum number of parallel workers
            
        Spec: docs/streaming_backend_plan.md#parallel-processing
        Tests: tests/test_transcription_performance.py#test_parallel_backend
        """
        super().__init__(model)
        self.chunk_duration = chunk_duration
        self.overlap_duration = overlap_duration
        self.max_workers = max_workers
        
        logger.warning("ParallelMLXWhisperBackend has known Metal GPU issues. "
                      "Use QueueBasedStreamingBackend for production.")
    
    def transcribe(self, wav_path: str) -> str:
        """Transcribe audio file using parallel chunk processing.
        
        This method splits the audio into overlapping chunks, processes them
        in parallel using multiple workers, and merges the results.
        
        Args:
            wav_path: Path to the audio file to transcribe
            
        Returns:
            Transcribed text as string
            
        Spec: docs/streaming_backend_plan.md#parallel-processing
        Tests: tests/test_transcription_performance.py#test_parallel_transcription
        
        Raises:
            RuntimeError: If parallel processing fails due to Metal GPU issues
        """
        start_time = time.time()
        logger.debug(f"Starting parallel transcription of {wav_path}")
        logger.debug(f"Chunk duration: {self.chunk_duration}s, Overlap: {self.overlap_duration}s, Workers: {self.max_workers}")
        
        try:
            # Load and split audio
            logger.debug("Loading audio file...")
            audio_data, sample_rate = sf.read(wav_path)
            logger.debug(f"Audio loaded - shape: {audio_data.shape}, sample_rate: {sample_rate}")
            
            # Convert to mono if stereo
            if len(audio_data.shape) > 1:
                audio_data = np.mean(audio_data, axis=1)
            
            logger.debug("Splitting audio into chunks...")
            chunks = self._split_audio_into_chunks(audio_data, sample_rate)
            logger.debug(f"Created {len(chunks)} chunks")
            
            # Process chunks in parallel
            logger.debug("Starting parallel chunk processing...")
            chunk_results = self._process_chunks_parallel(chunks)
            logger.debug(f"Parallel processing completed - {len(chunk_results)} results")
            
            # Merge results
            logger.debug("Merging chunk results...")
            final_result = self._merge_chunk_results(chunk_results)
            logger.debug(f"Merging completed - final length: {len(final_result)}")
            
            total_time = time.time() - start_time
            logger.debug(f"Parallel transcription completed in {total_time:.2f}s")
            logger.debug(f"Processed {len(chunks)} chunks, final result length: {len(final_result)}")
            
            return final_result
            
        except Exception as e:
            logger.error(f"Parallel transcription failed: {e}")
            raise RuntimeError(f"Parallel transcription failed: {e}") from e
    
    def _split_audio_into_chunks(self, audio_data: np.ndarray, sample_rate: int) -> List[Tuple[int, np.ndarray]]:
        """Split audio data into overlapping chunks.
        
        Args:
            audio_data: Audio data as numpy array
            sample_rate: Audio sample rate
            
        Returns:
            List of (chunk_index, chunk_data) tuples
            
        Spec: docs/streaming_backend_plan.md#chunking-strategy
        Tests: tests/test_transcription_performance.py#test_audio_chunking
        """
        logger.debug("_split_audio_into_chunks called")
        logger.debug(f"Audio data length: {len(audio_data)} samples")
        logger.debug(f"Sample rate: {sample_rate} Hz")
        
        # Calculate chunk parameters
        chunk_size = int(self.chunk_duration * sample_rate)
        overlap_size = int(self.overlap_duration * sample_rate)
        step_size = chunk_size - overlap_size
        
        logger.debug(f"Audio duration: {len(audio_data) / sample_rate:.2f} seconds")
        logger.debug(f"Chunk size: {chunk_size} samples ({self.chunk_duration}s)")
        logger.debug(f"Overlap size: {overlap_size} samples ({self.overlap_duration}s)")
        logger.debug(f"Step size: {step_size} samples ({step_size / sample_rate:.2f}s)")
        
        chunks = []
        start = 0
        chunk_index = 0
        
        logger.debug("Starting chunk creation loop...")
        
        while start < len(audio_data):
            end = min(start + chunk_size, len(audio_data))
            chunk_data = audio_data[start:end]
            
            logger.debug(f"Chunk {chunk_index}: start={start}, end={end}, length={len(chunk_data)}")
            
            # Pad the last chunk if necessary
            if len(chunk_data) < chunk_size:
                padding_size = chunk_size - len(chunk_data)
                chunk_data = np.pad(chunk_data, (0, padding_size), mode='constant')
                logger.debug(f"Chunk {chunk_index}: padded with {padding_size} samples")
            
            chunks.append((chunk_index, chunk_data))
            start += step_size
            chunk_index += 1
        
        logger.debug(f"Created {len(chunks)} chunks total")
        logger.debug("Chunk details:")
        for i, (idx, data) in enumerate(chunks):
            logger.debug(f"  Chunk {idx}: {len(data)} samples ({len(data) / sample_rate:.2f}s)")
        
        return chunks
    
    def _process_chunks_parallel(self, chunks: List[Tuple[int, np.ndarray]]) -> List[Tuple[int, str]]:
        """Process audio chunks in parallel using ThreadPoolExecutor.
        
        Args:
            chunks: List of (chunk_index, chunk_data) tuples
            
        Returns:
            List of (chunk_index, transcription) tuples
            
        Spec: docs/streaming_backend_plan.md#parallel-processing
        Tests: tests/test_transcription_performance.py#test_parallel_chunk_processing
        """
        logger.debug(f"_process_chunks_parallel called with {len(chunks)} chunks")
        logger.debug(f"Max workers: {self.max_workers}")
        
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit chunks to executor
            logger.debug("Submitting chunks to executor...")
            future_to_chunk = {}
            
            for chunk_index, chunk_data in chunks:
                logger.debug(f"Submitting chunk {chunk_index} (size: {len(chunk_data)} samples)")
                future = executor.submit(self._transcribe_chunk, chunk_index, chunk_data)
                future_to_chunk[future] = chunk_index
            
            # Collect results
            logger.debug("Collecting results from executor...")
            for future in as_completed(future_to_chunk):
                chunk_index = future_to_chunk[future]
                try:
                    transcription = future.result()
                    results.append((chunk_index, transcription))
                    logger.debug(f"Chunk {chunk_index} completed: {len(transcription)} chars")
                except Exception as e:
                    logger.error(f"Chunk {chunk_index} failed: {e}")
                    results.append((chunk_index, ""))
        
        # Sort results by chunk index
        results.sort(key=lambda x: x[0])
        logger.debug(f"All futures completed, sorting results...")
        logger.debug(f"Final results: {len(results)} chunks")
        for chunk_index, transcription in results:
            logger.debug(f"  Chunk {chunk_index}: {len(transcription)} chars")
        
        return results
    
    def _transcribe_chunk(self, chunk_index: int, chunk_data: np.ndarray) -> str:
        """Transcribe a single audio chunk.
        
        Args:
            chunk_index: Index of the chunk
            chunk_data: Audio data for the chunk
            
        Returns:
            Transcribed text for the chunk
            
        Spec: docs/streaming_backend_plan.md#chunk-transcription
        Tests: tests/test_transcription_performance.py#test_chunk_transcription
        """
        logger.debug(f"_transcribe_chunk called for chunk {chunk_index}")
        logger.debug(f"Chunk {chunk_index} data size: {len(chunk_data)} samples")
        
        try:
            # Save chunk to temporary file
            logger.debug(f"Saving chunk {chunk_index} to temp file...")
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                sf.write(tmp_file.name, chunk_data, 16000)
                tmp_path = tmp_file.name
            
            logger.debug(f"Chunk {chunk_index} saved to: {tmp_path}")
            
            # Transcribe using base backend
            logger.debug(f"Transcribing chunk {chunk_index} with base backend...")
            transcription = super().transcribe(tmp_path)
            
            # Clean up temporary file
            Path(tmp_path).unlink(missing_ok=True)
            
            return transcription
            
        except Exception as e:
            logger.error(f"Error transcribing chunk {chunk_index}: {e}")
            # Clean up temporary file on error
            if 'tmp_path' in locals():
                Path(tmp_path).unlink(missing_ok=True)
            raise
    
    def _merge_chunk_results(self, chunk_results: List[Tuple[int, str]]) -> str:
        """Merge transcription results from multiple chunks.
        
        Args:
            chunk_results: List of (chunk_index, transcription) tuples
            
        Returns:
            Merged transcription text
            
        Spec: docs/streaming_backend_plan.md#result-merging
        Tests: tests/test_transcription_performance.py#test_result_merging
        """
        logger.debug("Merging chunk results...")
        
        # Sort by chunk index to ensure correct order
        chunk_results.sort(key=lambda x: x[0])
        
        # Simple concatenation for now
        # TODO: Implement overlap handling and deduplication
        merged_text = " ".join(transcription for _, transcription in chunk_results)
        
        # Clean up extra whitespace
        merged_text = " ".join(merged_text.split())
        
        logger.debug(f"Merging completed - final length: {len(merged_text)}")
        return merged_text 