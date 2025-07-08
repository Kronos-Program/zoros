"""
🚀 Live Chunk Processor for Real-time Dictation
Process audio chunks during recording for ultra-fast results.

This module handles live transcription during recording, building the transcript
progressively so that when the user hits "stop", minimal final processing is needed.
"""

import time
import logging
import threading
import queue
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable, Deque
from collections import deque
from concurrent.futures import ThreadPoolExecutor, Future
import uuid

import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)


class LiveChunkProcessor:
    """Process audio chunks in real-time during recording for instant results."""
    
    def __init__(
        self,
        backend_instance,  # Pre-loaded backend instance
        chunk_duration: float = 3.0,    # Process every 3 seconds
        overlap_duration: float = 0.5,  # 0.5s overlap for continuity
        max_buffer_chunks: int = 5,     # Buffer size for smooth processing
        confidence_threshold: float = 0.7  # Minimum confidence for results
    ):
        self.backend_instance = backend_instance
        self.chunk_duration = chunk_duration
        self.overlap_duration = overlap_duration
        self.max_buffer_chunks = max_buffer_chunks
        self.confidence_threshold = confidence_threshold
        self.sample_rate = 16000
        
        # Live processing state
        self.audio_buffer = deque()
        self.chunk_queue = queue.Queue(maxsize=max_buffer_chunks)
        self.result_queue = queue.Queue()
        self.processed_chunks = []
        
        # Processing control
        self.is_processing = False
        self.current_chunk_id = 0
        self.processing_thread = None
        self.shutdown_event = threading.Event()
        
        # Live transcript state
        self.live_transcript = ""
        self.chunk_transcripts = {}
        self.final_transcript = ""
        
        # Performance tracking
        self.stats = {
            'chunks_processed': 0,
            'total_processing_time': 0,
            'average_chunk_time': 0,
            'processing_errors': 0
        }
        
        # Callback for live updates
        self.update_callback = None
        
        logger.info(f"🚀 Live chunk processor initialized")
        logger.info(f"   Chunk duration: {chunk_duration}s")
        logger.info(f"   Buffer size: {max_buffer_chunks}")
    
    def start_processing(self, update_callback: Optional[Callable[[str], None]] = None) -> None:
        """Start live chunk processing."""
        if self.is_processing:
            return
        
        logger.info("🎬 Starting live chunk processing...")
        
        self.is_processing = True
        self.shutdown_event.clear()
        self.update_callback = update_callback
        
        # Start background processing thread
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()
        
        logger.info("✅ Live processing started!")
    
    def add_audio_chunk(self, audio_data: np.ndarray) -> None:
        """Add audio data to the live processing buffer."""
        if not self.is_processing:
            return
        
        # Add to rolling buffer
        self.audio_buffer.extend(audio_data)
        
        # Check if we have enough data for processing
        chunk_size = int(self.chunk_duration * self.sample_rate)
        if len(self.audio_buffer) >= chunk_size:
            self._create_and_queue_chunk()
    
    def _create_and_queue_chunk(self) -> None:
        """Create a chunk from current buffer and queue for processing."""
        chunk_size = int(self.chunk_duration * self.sample_rate)
        overlap_size = int(self.overlap_duration * self.sample_rate)
        
        if len(self.audio_buffer) < chunk_size:
            return
        
        # Extract chunk data
        chunk_data = np.array(list(self.audio_buffer)[:chunk_size])
        
        # Remove processed data but keep overlap
        for _ in range(chunk_size - overlap_size):
            if self.audio_buffer:
                self.audio_buffer.popleft()
        
        # Create chunk metadata
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
            logger.debug(f"📦 Queued chunk {chunk_info['id']} for processing")
        except queue.Full:
            logger.warning("⚠️ Chunk queue full, dropping chunk for live processing")
    
    def _processing_loop(self) -> None:
        """Main processing loop for live chunks."""
        logger.debug("🔄 Live processing loop started")
        
        while self.is_processing and not self.shutdown_event.is_set():
            try:
                # Get chunk from queue with timeout
                chunk_info = self.chunk_queue.get(timeout=0.1)
                
                # Process chunk immediately
                self._process_chunk_sync(chunk_info)
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"❌ Processing loop error: {e}")
                self.stats['processing_errors'] += 1
        
        logger.debug("🔄 Live processing loop stopped")
    
    def _process_chunk_sync(self, chunk_info: Dict) -> None:
        """Process a single chunk synchronously for live results."""
        chunk_start = time.time()
        
        try:
            # Save chunk to temporary file
            chunk_file = Path(tempfile.gettempdir()) / f"live_chunk_{chunk_info['id']}_{uuid.uuid4().hex[:8]}.wav"
            sf.write(chunk_file, chunk_info['data'], self.sample_rate)
            
            # Transcribe using pre-loaded backend
            transcript = self.backend_instance.transcribe(str(chunk_file))
            
            # Clean up temp file immediately
            chunk_file.unlink(missing_ok=True)
            
            # Calculate timing
            processing_time = time.time() - chunk_start
            
            # Update stats
            self.stats['chunks_processed'] += 1
            self.stats['total_processing_time'] += processing_time
            self.stats['average_chunk_time'] = (
                self.stats['total_processing_time'] / self.stats['chunks_processed']
            )
            
            # Store result
            result = {
                'id': chunk_info['id'],
                'transcript': transcript.strip(),
                'timestamp': chunk_info['timestamp'],
                'processing_time': processing_time,
                'confidence': 1.0  # TODO: Add actual confidence calculation
            }
            
            # Add to results
            self.chunk_transcripts[chunk_info['id']] = result
            
            # Update live transcript
            self._update_live_transcript()
            
            logger.debug(f"✅ Live chunk {chunk_info['id']}: {processing_time:.2f}s -> '{transcript[:50]}...'")
            
        except Exception as e:
            logger.error(f"❌ Live chunk {chunk_info['id']} processing failed: {e}")
            self.stats['processing_errors'] += 1
    
    def _update_live_transcript(self) -> None:
        """Update the live transcript from processed chunks."""
        # Sort chunks by ID to maintain order
        sorted_chunks = sorted(self.chunk_transcripts.items())
        
        # Build live transcript
        transcript_parts = []
        for chunk_id, result in sorted_chunks:
            if result['confidence'] >= self.confidence_threshold and result['transcript']:
                transcript_parts.append(result['transcript'])
        
        # Update live transcript
        self.live_transcript = " ".join(transcript_parts)
        
        # Call update callback if provided
        if self.update_callback and self.live_transcript:
            self.update_callback(self.live_transcript)
    
    def stop_processing(self) -> str:
        """Stop live processing and return final transcript."""
        if not self.is_processing:
            return self.final_transcript
        
        logger.info("🛑 Stopping live chunk processing...")
        
        # Signal shutdown
        self.is_processing = False
        self.shutdown_event.set()
        
        # Process any remaining audio in buffer
        self._process_remaining_chunks()
        
        # Wait for processing thread to finish
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=3.0)
        
        # Finalize transcript
        self._finalize_transcript()
        
        logger.info(f"✅ Live processing stopped")
        logger.info(f"📊 Processed {self.stats['chunks_processed']} chunks")
        logger.info(f"⚡ Average processing: {self.stats['average_chunk_time']:.2f}s per chunk")
        
        return self.final_transcript
    
    def _process_remaining_chunks(self) -> None:
        """Process any remaining chunks in the queue and buffer."""
        # Process remaining queued chunks
        remaining_chunks = []
        while not self.chunk_queue.empty():
            try:
                chunk_info = self.chunk_queue.get_nowait()
                remaining_chunks.append(chunk_info)
            except queue.Empty:
                break
        
        # Process remaining audio in buffer
        if len(self.audio_buffer) >= int(0.5 * self.sample_rate):  # At least 0.5s
            final_chunk_data = np.array(list(self.audio_buffer))
            final_chunk = {
                'id': self.current_chunk_id,
                'data': final_chunk_data,
                'timestamp': time.time(),
                'duration': len(final_chunk_data) / self.sample_rate
            }
            remaining_chunks.append(final_chunk)
        
        # Process all remaining chunks
        for chunk_info in remaining_chunks:
            self._process_chunk_sync(chunk_info)
    
    def _finalize_transcript(self) -> None:
        """Finalize the transcript with intelligent merging."""
        # Sort all chunk results by ID
        sorted_chunks = sorted(self.chunk_transcripts.items())
        
        # Build final transcript with smart merging
        final_parts = []
        for chunk_id, result in sorted_chunks:
            if result['confidence'] >= self.confidence_threshold and result['transcript']:
                final_parts.append(result['transcript'])
        
        # Simple space-based joining for now
        # TODO: Could add overlap detection and smart word boundary merging
        self.final_transcript = " ".join(final_parts).strip()
        
        # Clean up any extra whitespace
        import re
        self.final_transcript = re.sub(r'\s+', ' ', self.final_transcript)
    
    def get_live_transcript(self) -> str:
        """Get the current live transcript."""
        return self.live_transcript
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        return {
            **self.stats,
            'is_processing': self.is_processing,
            'buffer_size': len(self.audio_buffer),
            'queue_size': self.chunk_queue.qsize(),
            'processed_chunk_count': len(self.chunk_transcripts),
            'live_transcript_length': len(self.live_transcript),
            'chunk_duration': self.chunk_duration,
            'overlap_duration': self.overlap_duration
        }
    
    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop_processing()
        
        # Ensure thread is properly cleaned up
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=1.0)
        
        # Clear all data
        self.audio_buffer.clear()
        self.chunk_transcripts.clear()
        
        # Clear queues properly
        while not self.chunk_queue.empty():
            try:
                self.chunk_queue.get_nowait()
                self.chunk_queue.task_done()
            except queue.Empty:
                break
        
        # Clear result queue
        while not self.result_queue.empty():
            try:
                self.result_queue.get_nowait()
            except queue.Empty:
                break
        
        logger.info("🧹 Live chunk processor cleaned up")


def create_live_chunk_processor(backend_instance, **kwargs) -> LiveChunkProcessor:
    """Create a live chunk processor with the given backend instance."""
    return LiveChunkProcessor(backend_instance, **kwargs)