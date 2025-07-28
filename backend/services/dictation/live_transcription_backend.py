"""
🚀 LIVE TRANSCRIPTION BACKEND 🚀
The ultimate dictation limbo solution: transcribe WHILE recording!

Target: 5-10 seconds total for ANY length audio by processing during recording
Strategy: Stream + Buffer + Pipeline + Predict = INSTANT RESULTS

This backend starts transcribing as soon as audio comes in, building the transcript
in real-time so that when you hit STOP, the text is already 90%+ complete.
"""

import time
import logging
import threading
import queue
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable, Deque
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import tempfile

import numpy as np
import soundfile as sf

from .mlx_whisper_backend import MLXWhisperBackend

logger = logging.getLogger(__name__)


class LiveTranscriptionBackend:
    """Live transcription backend that processes audio streams in real-time."""
    
    def __init__(
        self,
        chunk_duration: float = 3.0,    # Process every 3 seconds
        overlap_duration: float = 0.5,  # 0.5s overlap for continuity
        max_workers: int = 2,            # Parallel processing workers
        buffer_size: int = 10,           # Buffer for audio chunks
        confidence_threshold: float = 0.8  # Only keep high-confidence results
    ):
        self.chunk_duration = chunk_duration
        self.overlap_duration = overlap_duration
        self.max_workers = max_workers
        self.buffer_size = buffer_size
        self.confidence_threshold = confidence_threshold
        self.sample_rate = 16000
        
        # Initialize the MLX backend for transcription
        self.transcriber = MLXWhisperBackend("large-v3-turbo")
        
        # Live processing components
        self.audio_buffer = deque(maxlen=int(self.sample_rate * (chunk_duration + overlap_duration) * 2))
        self.chunk_queue = queue.Queue(maxsize=buffer_size)
        self.result_queue = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # State tracking
        self.is_streaming = False
        self.current_chunk_id = 0
        self.live_transcript = ""
        self.finalized_transcript = ""
        
        # Performance tracking
        self.chunk_times = []
        self.processing_stats = {
            'chunks_processed': 0,
            'total_processing_time': 0,
            'average_chunk_time': 0
        }
        
        # Background processing thread
        self.processing_thread = None
        self.shutdown_event = threading.Event()
        
        logger.info(f"🚀 Live transcription backend initialized")
        logger.info(f"   Chunk duration: {chunk_duration}s")
        logger.info(f"   Workers: {max_workers}")
        logger.info(f"   Buffer size: {buffer_size}")
    
    def start_streaming(self, callback: Optional[Callable[[str, Dict], None]] = None) -> None:
        """Start live transcription streaming."""
        if self.is_streaming:
            return
        
        logger.info("🎬 Starting live transcription streaming...")
        
        self.is_streaming = True
        self.shutdown_event.clear()
        self.callback = callback
        
        # Start background processing thread
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()
        
        logger.info("✅ Live streaming started!")
    
    def stop_streaming(self) -> str:
        """Stop streaming and return final transcript."""
        if not self.is_streaming:
            return self.finalized_transcript
        
        logger.info("🛑 Stopping live transcription...")
        
        # Signal shutdown
        self.is_streaming = False
        self.shutdown_event.set()
        
        # Process any remaining audio
        final_chunk = self._create_final_chunk()
        if final_chunk:
            self._process_chunk_sync(final_chunk)
        
        # Wait for processing to complete
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=5.0)
        
        # Finalize the transcript
        self._finalize_transcript()
        
        logger.info(f"✅ Live transcription stopped")
        logger.info(f"📊 Processed {self.processing_stats['chunks_processed']} chunks")
        logger.info(f"⚡ Average processing: {self.processing_stats['average_chunk_time']:.2f}s per chunk")
        
        return self.finalized_transcript
    
    def add_audio_data(self, audio_data: np.ndarray) -> None:
        """Add audio data to the live processing buffer."""
        if not self.is_streaming:
            return
        
        # Add audio to rolling buffer
        self.audio_buffer.extend(audio_data)
        
        # Check if we have enough data for a chunk
        chunk_size = int(self.chunk_duration * self.sample_rate)
        if len(self.audio_buffer) >= chunk_size:
            self._create_and_queue_chunk()
    
    def _create_and_queue_chunk(self) -> None:
        """Create a chunk from current buffer and queue for processing."""
        chunk_size = int(self.chunk_duration * self.sample_rate)
        overlap_size = int(self.overlap_duration * self.sample_rate)
        
        # Extract chunk data
        chunk_data = np.array(list(self.audio_buffer)[:chunk_size])
        
        # Remove processed data but keep overlap
        for _ in range(chunk_size - overlap_size):
            if self.audio_buffer:
                self.audio_buffer.popleft()
        
        # Create chunk info
        chunk_info = {
            'id': self.current_chunk_id,
            'data': chunk_data,
            'timestamp': time.time(),
            'duration': len(chunk_data) / self.sample_rate
        }
        
        # Queue for processing (non-blocking)
        try:
            self.chunk_queue.put_nowait(chunk_info)
            self.current_chunk_id += 1
            logger.debug(f"📦 Queued chunk {chunk_info['id']}")
        except queue.Full:
            logger.warning("⚠️ Chunk queue full, dropping chunk")
    
    def _processing_loop(self) -> None:
        """Main processing loop for live chunks."""
        logger.info("🔄 Processing loop started")
        
        while self.is_streaming and not self.shutdown_event.is_set():
            try:
                # Get chunk from queue with timeout
                chunk_info = self.chunk_queue.get(timeout=0.1)
                
                # Submit for async processing
                future = self.executor.submit(self._process_chunk_async, chunk_info)
                
                # Don't wait for result here - let it complete in background
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"❌ Processing loop error: {e}")
        
        logger.info("🔄 Processing loop stopped")
    
    def _process_chunk_async(self, chunk_info: Dict) -> None:
        """Process a single chunk asynchronously."""
        start_time = time.time()
        
        try:
            # Save chunk to temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                sf.write(tmp_file.name, chunk_info['data'], self.sample_rate)
                tmp_path = tmp_file.name
            
            # Transcribe using MLX backend
            transcript = self.transcriber.transcribe(tmp_path)
            
            # Clean up temp file
            Path(tmp_path).unlink(missing_ok=True)
            
            # Calculate timing
            processing_time = time.time() - start_time
            
            # Update stats
            self.processing_stats['chunks_processed'] += 1
            self.processing_stats['total_processing_time'] += processing_time
            self.processing_stats['average_chunk_time'] = (
                self.processing_stats['total_processing_time'] / 
                self.processing_stats['chunks_processed']
            )
            
            # Add result to queue
            result = {
                'id': chunk_info['id'],
                'transcript': transcript,
                'timestamp': chunk_info['timestamp'],
                'processing_time': processing_time,
                'confidence': 1.0  # TODO: Add confidence calculation
            }
            
            self.result_queue.put(result)
            
            # Update live transcript
            self._update_live_transcript(result)
            
            logger.debug(f"✅ Processed chunk {chunk_info['id']}: {processing_time:.2f}s")
            
        except Exception as e:
            logger.error(f"❌ Chunk {chunk_info['id']} processing failed: {e}")
    
    def _process_chunk_sync(self, chunk_info: Dict) -> str:
        """Process a chunk synchronously (for final chunk)."""
        start_time = time.time()
        
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                sf.write(tmp_file.name, chunk_info['data'], self.sample_rate)
                tmp_path = tmp_file.name
            
            transcript = self.transcriber.transcribe(tmp_path)
            Path(tmp_path).unlink(missing_ok=True)
            
            processing_time = time.time() - start_time
            logger.info(f"🎯 Final chunk processed in {processing_time:.2f}s")
            
            return transcript
            
        except Exception as e:
            logger.error(f"❌ Final chunk processing failed: {e}")
            return ""
    
    def _create_final_chunk(self) -> Optional[Dict]:
        """Create final chunk from remaining buffer data."""
        if not self.audio_buffer:
            return None
        
        remaining_data = np.array(list(self.audio_buffer))
        
        if len(remaining_data) < self.sample_rate * 0.5:  # Skip if less than 0.5s
            return None
        
        return {
            'id': self.current_chunk_id,
            'data': remaining_data,
            'timestamp': time.time(),
            'duration': len(remaining_data) / self.sample_rate
        }
    
    def _update_live_transcript(self, result: Dict) -> None:
        """Update the live transcript with new result."""
        if result['confidence'] >= self.confidence_threshold:
            # Simple append for now - could be improved with intelligent merging
            if self.live_transcript and result['transcript'].strip():
                self.live_transcript += " " + result['transcript'].strip()
            elif result['transcript'].strip():
                self.live_transcript = result['transcript'].strip()
            
            # Call callback if provided
            if hasattr(self, 'callback') and self.callback:
                self.callback(self.live_transcript, {
                    'chunk_id': result['id'],
                    'processing_time': result['processing_time'],
                    'confidence': result['confidence']
                })
    
    def _finalize_transcript(self) -> None:
        """Finalize the transcript by processing any remaining results."""
        # Collect all remaining results
        remaining_results = []
        while not self.result_queue.empty():
            try:
                result = self.result_queue.get_nowait()
                remaining_results.append(result)
            except queue.Empty:
                break
        
        # Sort by chunk ID and merge
        remaining_results.sort(key=lambda x: x['id'])
        
        for result in remaining_results:
            if result['confidence'] >= self.confidence_threshold:
                if self.live_transcript and result['transcript'].strip():
                    self.live_transcript += " " + result['transcript'].strip()
                elif result['transcript'].strip():
                    self.live_transcript = result['transcript'].strip()
        
        self.finalized_transcript = self.live_transcript.strip()
    
    def get_live_transcript(self) -> str:
        """Get the current live transcript."""
        return self.live_transcript
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        return {
            **self.processing_stats,
            'is_streaming': self.is_streaming,
            'buffer_size': len(self.audio_buffer),
            'queue_size': self.chunk_queue.qsize(),
            'chunk_duration': self.chunk_duration,
            'overlap_duration': self.overlap_duration
        }
    
    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop_streaming()
        self.executor.shutdown(wait=True)
        
        # Clear queues
        while not self.chunk_queue.empty():
            try:
                self.chunk_queue.get_nowait()
            except queue.Empty:
                break
        
        while not self.result_queue.empty():
            try:
                self.result_queue.get_nowait()
            except queue.Empty:
                break
        
        logger.info("🧹 Live transcription backend cleaned up")


def create_live_transcription_backend(**kwargs) -> LiveTranscriptionBackend:
    """Create a live transcription backend with optimal settings."""
    return LiveTranscriptionBackend(**kwargs)