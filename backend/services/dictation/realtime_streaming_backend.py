"""
Real-time Streaming MLX Whisper Backend

This module provides true real-time streaming transcription that processes audio
chunks as they're being recorded, rather than waiting for the complete recording.

Specification: docs/requirements/dictation_requirements.md#realtime-streaming
Architecture: docs/zoros_architecture.md#realtime-streaming-backend
Tests: tests/test_realtime_streaming.py
Integration: source/interfaces/intake/main.py#realtime_streaming

Related Modules:
- source/dictation_backends/streaming_mlx_whisper_backend.py - Batch streaming implementation
- source/interfaces/intake/main.py - Intake UI integration
- docs/realtime_streaming.md - Real-time streaming documentation

Dependencies:
- External libraries: mlx_whisper, numpy, soundfile, threading, queue
- Internal modules: source.dictation_backends.mlx_whisper_backend
- Configuration: config/realtime_streaming_settings.json
"""

from __future__ import annotations

import json
import logging
import tempfile
import threading
import time
from collections import deque
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue

import numpy as np
import soundfile as sf
from .mlx_whisper_backend import MLXWhisperBackend

logger = logging.getLogger(__name__)


class RealtimeStreamingBackend(MLXWhisperBackend):
    """Real-time streaming MLX Whisper backend for live transcription.
    
    This backend processes audio chunks in real-time as they're being recorded,
    providing immediate transcription feedback without waiting for the recording
    to complete.
    
    Spec: docs/requirements/dictation_requirements.md#realtime-streaming
    Tests: tests/test_realtime_streaming.py#test_realtime_backend
    Usage: source/interfaces/intake/main.py#realtime_streaming
    
    Dependencies:
    - MLXWhisperBackend for base transcription
    - ThreadPoolExecutor for parallel processing
    - Queue for chunk management
    - Real-time audio processing
    """

    def __init__(
        self, 
        model_name: str = "large-v3-turbo",
        chunk_duration: float = 3.0,  # Reduced for faster feedback
        overlap_duration: float = 0.5,  # Reduced overlap for M1 efficiency
        max_workers: int = 2,  # Increased for M1 parallel processing
        buffer_size: int = 5,  # Increased buffer for smoother streaming
        callback: Optional[Callable[[str, float], None]] = None
    ):
        """Initialize the real-time streaming backend.
        
        Args:
            model_name: MLX Whisper model to use
            chunk_duration: Duration of each audio chunk in seconds
            overlap_duration: Overlap between chunks in seconds
            max_workers: Maximum number of parallel transcription workers
            buffer_size: Maximum number of chunks to keep in buffer
            callback: Optional callback function for real-time results
            
        Spec: docs/requirements/dictation_requirements.md#realtime-configuration
        Tests: tests/test_realtime_streaming.py#test_backend_initialization
        """
        super().__init__(model_name)
        self.chunk_duration = chunk_duration
        self.overlap_duration = overlap_duration
        self.max_workers = max_workers
        self.buffer_size = buffer_size
        self.callback = callback
        self.sample_rate = 16000
        
        # Real-time processing components
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.chunk_queue = Queue(maxsize=buffer_size)
        self.result_queue = Queue()
        self.processing_lock = threading.Lock()
        
        # State tracking
        self.is_streaming = False
        self.current_chunk_id = 0
        self.audio_buffer = deque(maxlen=int(self.sample_rate * (chunk_duration + overlap_duration)))
        self.last_chunk_time = 0.0
        
        # Performance metrics
        self.chunk_times = []
        self.latency_times = []
        self.total_processed_chunks = 0
        
        # Background processing thread
        self.processing_thread = None
        self.shutdown_event = threading.Event()
        
        logger.info(f"Initialized RealtimeStreamingBackend with chunk_duration={chunk_duration}s, overlap={overlap_duration}s")

    def start_streaming(self) -> None:
        """Start real-time streaming processing.
        
        Spec: docs/requirements/dictation_requirements.md#streaming-start
        Tests: tests/test_realtime_streaming.py#test_start_streaming
        """
        if self.is_streaming:
            return
            
        self.is_streaming = True
        self.shutdown_event.clear()
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()
        
        logger.info("Started real-time streaming processing")

    def stop_streaming(self) -> str:
        """Stop real-time streaming and return final merged result.
        
        Returns:
            Final merged transcription text
            
        Spec: docs/requirements/dictation_requirements.md#streaming-stop
        Tests: tests/test_realtime_streaming.py#test_stop_streaming
        """
        if not self.is_streaming:
            return ""
            
        logger.info("Stopping real-time streaming processing")
        
        # Signal shutdown
        self.is_streaming = False
        self.shutdown_event.set()
        
        # Wait for processing thread to finish with timeout
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=2.0)  # Reduced timeout
            if self.processing_thread.is_alive():
                logger.warning("Processing thread did not stop within timeout")
        
        # Process any remaining audio in buffer with timeout
        try:
            final_result = self._process_remaining_audio()
        except Exception as e:
            logger.error(f"Error processing remaining audio: {e}")
            final_result = ""
        
        # Clean up
        self.cleanup()
        
        return final_result

    def add_audio_data(self, audio_data: np.ndarray, timestamp: float) -> None:
        """Add audio data to the streaming buffer.
        
        Args:
            audio_data: Audio data as numpy array
            timestamp: Timestamp of the audio data
            
        Spec: docs/requirements/dictation_requirements.md#audio-data-addition
        Tests: tests/test_realtime_streaming.py#test_add_audio_data
        """
        if not self.is_streaming:
            return
            
        # Add audio data to buffer
        self.audio_buffer.extend(audio_data)
        
        # Check if we have enough data for a new chunk
        chunk_size = int(self.chunk_duration * self.sample_rate)
        if len(self.audio_buffer) >= chunk_size:
            self._create_and_queue_chunk(timestamp)

    def _create_and_queue_chunk(self, timestamp: float) -> None:
        """Create a new audio chunk and add it to the processing queue.
        
        Args:
            timestamp: Current timestamp
            
        Spec: docs/requirements/dictation_requirements.md#chunk-creation
        Tests: tests/test_realtime_streaming.py#test_chunk_creation
        """
        chunk_size = int(self.chunk_duration * self.sample_rate)
        overlap_size = int(self.overlap_duration * self.sample_rate)
        
        # Extract chunk data
        chunk_data = np.array(list(self.audio_buffer)[:chunk_size])
        
        # Remove processed data (keep overlap)
        for _ in range(chunk_size - overlap_size):
            if self.audio_buffer:
                self.audio_buffer.popleft()
        
        # Create chunk info
        chunk_info = {
            'id': self.current_chunk_id,
            'data': chunk_data,
            'timestamp': timestamp,
            'start_time': timestamp - self.chunk_duration
        }
        
        # Add to processing queue (non-blocking)
        try:
            self.chunk_queue.put_nowait(chunk_info)
            self.current_chunk_id += 1
            logger.debug(f"Queued chunk {chunk_info['id']} at timestamp {timestamp:.2f}s")
        except:
            logger.warning("Chunk queue full, dropping chunk")

    def _processing_loop(self) -> None:
        """Main processing loop for real-time chunks.
        
        Spec: docs/requirements/dictation_requirements.md#processing-loop
        Tests: tests/test_realtime_streaming.py#test_processing_loop
        """
        while self.is_streaming and not self.shutdown_event.is_set():
            try:
                # Get chunk from queue with timeout
                chunk_info = self.chunk_queue.get(timeout=0.1)
                
                # Process chunk
                self._process_chunk(chunk_info)
                
            except:
                # Timeout or queue empty, continue
                continue

    def _process_chunk(self, chunk_info: Dict) -> None:
        """Process a single audio chunk.
        
        Args:
            chunk_info: Dictionary containing chunk information
            
        Spec: docs/requirements/dictation_requirements.md#chunk-processing
        Tests: tests/test_realtime_streaming.py#test_chunk_processing
        """
        start_time = time.time()
        
        try:
            # Save chunk to temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                sf.write(tmp_file.name, chunk_info['data'], self.sample_rate)
                tmp_path = tmp_file.name
            
            # Transcribe using base MLX Whisper backend
            transcription = super().transcribe(tmp_path)
            
            # Clean up temporary file
            Path(tmp_path).unlink(missing_ok=True)
            
            # Calculate timing
            chunk_time = time.time() - start_time
            latency = time.time() - chunk_info['timestamp']
            
            self.chunk_times.append(chunk_time)
            self.latency_times.append(latency)
            self.total_processed_chunks += 1
            
            # Add to result queue
            result_info = {
                'id': chunk_info['id'],
                'transcription': transcription,
                'timestamp': chunk_info['timestamp'],
                'chunk_time': chunk_time,
                'latency': latency
            }
            
            self.result_queue.put(result_info)
            
            # Call callback if provided
            if self.callback:
                self.callback(transcription, latency)
            
            logger.debug(f"Processed chunk {chunk_info['id']} in {chunk_time:.2f}s, latency: {latency:.2f}s")
            
        except Exception as e:
            logger.error(f"Error processing chunk {chunk_info['id']}: {e}")

    def _process_remaining_audio(self) -> str:
        """Process any remaining audio in the buffer.
        
        Returns:
            Transcription of remaining audio
            
        Spec: docs/requirements/dictation_requirements.md#remaining-audio
        Tests: tests/test_realtime_streaming.py#test_remaining_audio
        """
        if not self.audio_buffer:
            return ""
            
        try:
            # Process remaining audio
            remaining_data = np.array(list(self.audio_buffer))
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                sf.write(tmp_file.name, remaining_data, self.sample_rate)
                tmp_path = tmp_file.name
            
            transcription = super().transcribe(tmp_path)
            Path(tmp_path).unlink(missing_ok=True)
            
            return transcription
            
        except Exception as e:
            logger.error(f"Error processing remaining audio: {e}")
            return ""

    def get_latest_results(self, max_results: int = 5) -> List[Dict]:
        """Get the latest transcription results.
        
        Args:
            max_results: Maximum number of results to return
            
        Returns:
            List of recent result dictionaries
            
        Spec: docs/requirements/dictation_requirements.md#latest-results
        Tests: tests/test_realtime_streaming.py#test_latest_results
        """
        results = []
        while len(results) < max_results:
            try:
                result = self.result_queue.get_nowait()
                results.append(result)
            except:
                break
        
        return results

    def get_performance_metrics(self) -> Dict[str, Union[float, int]]:
        """Get performance metrics for the real-time backend.
        
        Returns:
            Dictionary containing performance metrics
            
        Spec: docs/requirements/dictation_requirements.md#realtime-metrics
        Tests: tests/test_realtime_streaming.py#test_performance_metrics
        """
        avg_chunk_time = float(np.mean(self.chunk_times)) if self.chunk_times else 0.0
        avg_latency = float(np.mean(self.latency_times)) if self.latency_times else 0.0
        
        return {
            "total_processed_chunks": self.total_processed_chunks,
            "average_chunk_time": avg_chunk_time,
            "average_latency": avg_latency,
            "chunk_duration": self.chunk_duration,
            "overlap_duration": self.overlap_duration,
            "max_workers": self.max_workers,
            "buffer_size": self.buffer_size,
            "is_streaming": self.is_streaming
        }

    def cleanup(self) -> None:
        """Clean up resources used by the real-time backend."""
        self.is_streaming = False
        self.shutdown_event.set()
        
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=2.0)
        
        self.executor.shutdown(wait=True)
        self.audio_buffer.clear()
        
        # Clear queues
        while not self.chunk_queue.empty():
            try:
                self.chunk_queue.get_nowait()
            except:
                break
                
        while not self.result_queue.empty():
            try:
                self.result_queue.get_nowait()
            except:
                break
        
        logger.info("Realtime streaming backend cleaned up")


def create_realtime_backend(
    model_name: str = "large-v3-turbo",
    chunk_duration: float = 5.0,
    overlap_duration: float = 1.0,
    max_workers: int = 1,
    callback: Optional[Callable[[str, float], None]] = None
) -> RealtimeStreamingBackend:
    """Create a real-time streaming backend with optimized settings.
    
    Args:
        model_name: MLX Whisper model to use
        chunk_duration: Duration of each chunk in seconds
        overlap_duration: Overlap between chunks in seconds
        max_workers: Number of parallel workers
        callback: Optional callback for real-time results
        
    Returns:
        Configured RealtimeStreamingBackend instance
        
    Spec: docs/requirements/dictation_requirements.md#realtime-backend-creation
    Tests: tests/test_realtime_streaming.py#test_backend_creation
    """
    return RealtimeStreamingBackend(
        model_name=model_name,
        chunk_duration=chunk_duration,
        overlap_duration=overlap_duration,
        max_workers=max_workers,
        callback=callback
    ) 