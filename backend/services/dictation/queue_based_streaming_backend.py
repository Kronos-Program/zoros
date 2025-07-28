"""
Queue-Based Streaming MLX Whisper Backend

This backend implements a queue-based approach to avoid Metal GPU command buffer
conflicts by processing chunks sequentially with proper resource management.

The key improvements:
1. Single MLX Whisper model instance shared across all operations
2. Sequential chunk processing to avoid GPU contention
3. Proper resource cleanup between chunks
4. Queue-based job management with configurable concurrency

Spec: docs/streaming_backend_plan.md#model-sharing-architecture
Tests: tests/test_transcription_performance.py
Integration: source/dictation_backends/streaming_mlx_whisper_backend.py

Dependencies:
- mlx_whisper for transcription
- numpy for audio processing
- soundfile for audio I/O
- threading for queue management
"""

import time
import tempfile
import threading
from pathlib import Path
from typing import List, Optional, Callable, Dict, Any
from queue import Queue, Empty
import numpy as np
import soundfile as sf
import mlx_whisper

from source.dictation_backends.mlx_whisper_backend import MLXWhisperBackend


class ChunkJob:
    """Represents a chunk transcription job."""
    
    def __init__(self, chunk_id: int, audio_data: np.ndarray, start_time: float, 
                 sample_rate: int, temp_dir: Path):
        self.chunk_id = chunk_id
        self.audio_data = audio_data
        self.start_time = start_time
        self.sample_rate = sample_rate
        self.temp_dir = temp_dir
        self.result = None
        self.error = None
        self.completed = threading.Event()
    
    def __str__(self):
        return f"ChunkJob(id={self.chunk_id}, samples={len(self.audio_data)}, start_time={self.start_time:.2f})"


class QueueBasedStreamingBackend(MLXWhisperBackend):
    """
    Queue-based streaming backend that processes chunks sequentially to avoid GPU conflicts.
    
    This backend addresses the Metal GPU command buffer issue by:
    1. Using a single MLX Whisper model instance
    2. Processing chunks sequentially through a job queue
    3. Proper resource cleanup between chunks
    4. Configurable processing strategies
    """
    
    def __init__(self, model_name: str = "small", 
                 chunk_duration: float = 10.0,
                 overlap_duration: float = 2.0,
                 max_queue_size: int = 10,
                 processing_strategy: str = "sequential",
                 enable_gpu_cleanup: bool = True):
        """
        Initialize the queue-based streaming backend.
        
        Args:
            model_name: MLX Whisper model to use
            chunk_duration: Duration of each chunk in seconds
            overlap_duration: Overlap between chunks in seconds
            max_queue_size: Maximum number of jobs in the queue
            processing_strategy: "sequential" or "batched"
            enable_gpu_cleanup: Whether to perform GPU cleanup between chunks
        """
        super().__init__(model_name)
        
        self.chunk_duration = chunk_duration
        self.overlap_duration = overlap_duration
        self.max_queue_size = max_queue_size
        self.processing_strategy = processing_strategy
        self.enable_gpu_cleanup = enable_gpu_cleanup
        
        # Queue and threading
        self.job_queue = Queue(maxsize=max_queue_size)
        self.worker_thread = None
        self.shutdown_event = threading.Event()
        
        # Processing state
        self.is_processing = False
        self.processed_chunks = 0
        self.failed_chunks = 0
        
        # Performance tracking
        self.processing_times = []
        self.gpu_cleanup_times = []
        
        # Temporary directory tracking for cleanup
        self._temp_dirs = set()
        
        print(f"DEBUG: QueueBasedStreamingBackend initialized")
        print(f"  Model: {model_name}")
        print(f"  Chunk duration: {chunk_duration}s")
        print(f"  Overlap: {overlap_duration}s")
        print(f"  Strategy: {processing_strategy}")
        print(f"  GPU cleanup: {enable_gpu_cleanup}")
    
    def start_processing(self):
        """Start the background processing thread."""
        if self.worker_thread and self.worker_thread.is_alive():
            print("DEBUG: Worker thread already running")
            return
        
        self.shutdown_event.clear()
        self.worker_thread = threading.Thread(target=self._process_jobs, daemon=True)
        self.worker_thread.start()
        self.is_processing = True
        print(f"DEBUG: Started background processing thread")
    
    def stop_processing(self):
        """Stop the background processing thread."""
        if not self.worker_thread:
            return
        
        print(f"DEBUG: Stopping background processing thread")
        self.shutdown_event.set()
        
        # Wait for thread to finish
        if self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5.0)
        
        self.is_processing = False
        print(f"DEBUG: Background processing thread stopped")
    
    def _process_jobs(self):
        """Background thread that processes jobs from the queue."""
        print(f"DEBUG: Job processing thread started")
        
        while not self.shutdown_event.is_set():
            try:
                # Get job from queue with timeout
                job = self.job_queue.get(timeout=1.0)
                print(f"DEBUG: Processing job: {job}")
                
                # Process the job
                self._process_single_job(job)
                
                # Mark job as done
                self.job_queue.task_done()
                
            except Empty:
                # No jobs in queue, continue loop
                continue
            except Exception as e:
                print(f"DEBUG: Error in job processing thread: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"DEBUG: Job processing thread finished")
    
    def _process_single_job(self, job: ChunkJob):
        """Process a single chunk job."""
        start_time = time.time()
        
        try:
            print(f"DEBUG: Processing chunk {job.chunk_id}")
            
            # Save chunk to temporary file
            temp_file = job.temp_dir / f"chunk_{job.chunk_id}.wav"
            sf.write(temp_file, job.audio_data, job.sample_rate)
            
            # Transcribe chunk
            transcription_start = time.time()
            result = self.transcribe(str(temp_file))
            transcription_time = time.time() - transcription_start
            
            # Store result
            job.result = result
            job.completed.set()
            
            # Update statistics
            self.processed_chunks += 1
            self.processing_times.append(transcription_time)
            
            print(f"DEBUG: Chunk {job.chunk_id} completed in {transcription_time:.2f}s")
            print(f"DEBUG: Result: {result[:50]}...")
            
            # GPU cleanup if enabled
            if self.enable_gpu_cleanup:
                cleanup_start = time.time()
                self._perform_gpu_cleanup()
                cleanup_time = time.time() - cleanup_start
                self.gpu_cleanup_times.append(cleanup_time)
                print(f"DEBUG: GPU cleanup took {cleanup_time:.2f}s")
            
            # Clean up temporary file and directory
            temp_file.unlink(missing_ok=True)
            try:
                # Also remove the temp directory
                import shutil
                if job.temp_dir.exists():
                    shutil.rmtree(job.temp_dir, ignore_errors=True)
                    self._temp_dirs.discard(job.temp_dir)
                    print(f"DEBUG: Cleaned up temp directory for chunk {job.chunk_id}")
            except Exception as cleanup_error:
                print(f"DEBUG: Error cleaning temp directory for chunk {job.chunk_id}: {cleanup_error}")
            
        except Exception as e:
            print(f"DEBUG: Error processing chunk {job.chunk_id}: {e}")
            import traceback
            traceback.print_exc()
            
            job.error = str(e)
            job.completed.set()
            self.failed_chunks += 1
        
        total_time = time.time() - start_time
        print(f"DEBUG: Total chunk {job.chunk_id} processing time: {total_time:.2f}s")
    
    def _perform_gpu_cleanup(self):
        """Perform GPU cleanup to avoid command buffer conflicts."""
        try:
            # Force garbage collection
            import gc
            gc.collect()
            
            # Small delay to allow GPU operations to complete
            time.sleep(0.1)
            
            # Additional cleanup if needed
            # This is a placeholder for more sophisticated GPU cleanup
            pass
            
        except Exception as e:
            print(f"DEBUG: GPU cleanup error: {e}")
    
    def add_chunk(self, audio_data: np.ndarray, start_time: float, 
                  sample_rate: int = 16000) -> ChunkJob:
        """
        Add a chunk to the processing queue.
        
        Args:
            audio_data: Audio data as numpy array
            start_time: Start time of the chunk
            sample_rate: Sample rate of the audio
            
        Returns:
            ChunkJob object that can be used to wait for completion
        """
        if not self.is_processing:
            self.start_processing()
        
        # Create temporary directory for this chunk
        temp_dir = Path(tempfile.mkdtemp())
        self._temp_dirs.add(temp_dir)  # Track for cleanup
        
        # Create job
        job = ChunkJob(
            chunk_id=self.processed_chunks + self.failed_chunks,
            audio_data=audio_data,
            start_time=start_time,
            sample_rate=sample_rate,
            temp_dir=temp_dir
        )
        
        # Add to queue
        try:
            self.job_queue.put(job, timeout=5.0)
            print(f"DEBUG: Added chunk {job.chunk_id} to queue")
            return job
        except Exception as e:
            print(f"DEBUG: Failed to add chunk to queue: {e}")
            job.error = str(e)
            job.completed.set()
            return job
    
    def wait_for_chunk(self, job: ChunkJob, timeout: float = 30.0) -> Optional[str]:
        """
        Wait for a chunk job to complete.
        
        Args:
            job: ChunkJob to wait for
            timeout: Maximum time to wait in seconds
            
        Returns:
            Transcription result or None if failed
        """
        if job.completed.wait(timeout=timeout):
            if job.error:
                print(f"DEBUG: Chunk {job.chunk_id} failed: {job.error}")
                return None
            else:
                print(f"DEBUG: Chunk {job.chunk_id} completed successfully")
                return job.result
        else:
            print(f"DEBUG: Timeout waiting for chunk {job.chunk_id}")
            return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get processing statistics."""
        return {
            "processed_chunks": self.processed_chunks,
            "failed_chunks": self.failed_chunks,
            "queue_size": self.job_queue.qsize(),
            "is_processing": self.is_processing,
            "avg_processing_time": np.mean(self.processing_times) if self.processing_times else 0,
            "avg_cleanup_time": np.mean(self.gpu_cleanup_times) if self.gpu_cleanup_times else 0,
            "total_processing_time": sum(self.processing_times),
            "total_cleanup_time": sum(self.gpu_cleanup_times),
        }
    
    def transcribe_streaming(self, audio_path: str, callback: Optional[Callable] = None) -> str:
        """
        Transcribe audio file using streaming approach with queue-based processing.
        
        Args:
            audio_path: Path to audio file
            callback: Optional callback function for progress updates
            
        Returns:
            Complete transcription text
        """
        print(f"DEBUG: Starting queue-based streaming transcription of {audio_path}")
        
        try:
            # Load audio file
            print(f"DEBUG: Loading audio file...")
            audio_data, sample_rate = sf.read(audio_path)
            if len(audio_data.shape) > 1:
                audio_data = audio_data[:, 0]  # Convert to mono
            
            print(f"DEBUG: Audio loaded - shape: {audio_data.shape}, sample_rate: {sample_rate}")
            
            # Split into chunks
            chunks = self._split_audio_into_chunks(audio_data, sample_rate)
            print(f"DEBUG: Split audio into {len(chunks)} chunks")
            
            # Start processing
            self.start_processing()
            
            # Submit all chunks
            jobs = []
            for i, (chunk_data, start_time) in enumerate(chunks):
                job = self.add_chunk(chunk_data, start_time, sample_rate)
                jobs.append(job)
                
                if callback:
                    callback(f"Submitted chunk {i+1}/{len(chunks)}")
            
            # Wait for all chunks to complete
            results = []
            for i, job in enumerate(jobs):
                result = self.wait_for_chunk(job)
                if result:
                    results.append((job.start_time, result))
                else:
                    print(f"DEBUG: Chunk {i} failed")
                
                if callback:
                    callback(f"Completed chunk {i+1}/{len(chunks)}")
            
            # Stop processing
            self.stop_processing()
            
            # Merge results
            final_result = self._merge_chunk_results(results)
            
            # Print statistics
            stats = self.get_statistics()
            print(f"DEBUG: Processing complete")
            print(f"  Processed chunks: {stats['processed_chunks']}")
            print(f"  Failed chunks: {stats['failed_chunks']}")
            print(f"  Average processing time: {stats['avg_processing_time']:.2f}s")
            print(f"  Average cleanup time: {stats['avg_cleanup_time']:.2f}s")
            
            return final_result
            
        except Exception as e:
            print(f"DEBUG: Error in streaming transcription: {e}")
            import traceback
            traceback.print_exc()
            self.stop_processing()
            return ""
    
    def _split_audio_into_chunks(self, audio_data: np.ndarray, sample_rate: int) -> List[tuple]:
        """Split audio data into overlapping chunks."""
        chunk_size = int(self.chunk_duration * sample_rate)
        overlap_size = int(self.overlap_duration * sample_rate)
        step_size = chunk_size - overlap_size
        
        chunks = []
        for i in range(0, len(audio_data), step_size):
            start_sample = i
            end_sample = min(i + chunk_size, len(audio_data))
            
            # Extract chunk
            chunk_data = audio_data[start_sample:end_sample]
            
            # Pad if necessary
            if len(chunk_data) < chunk_size:
                chunk_data = np.pad(chunk_data, (0, chunk_size - len(chunk_data)))
            
            # Calculate start time
            start_time = start_sample / sample_rate
            
            chunks.append((chunk_data, start_time))
        
        return chunks
    
    def _merge_chunk_results(self, results: List[tuple]) -> str:
        """Merge chunk results into final transcription."""
        if not results:
            return ""
        
        # Sort by start time
        results.sort(key=lambda x: x[0])
        
        # Simple concatenation for now
        # TODO: Implement more sophisticated merging with overlap handling
        merged_text = " ".join(result[1] for result in results)
        
        return merged_text.strip()
    
    def cleanup_temp_directories(self):
        """Clean up any remaining temporary directories."""
        import shutil
        import sys
        import gc
        
        try:
            # Force cleanup of any remaining temp directories
            temp_dirs = getattr(self, '_temp_dirs', set())
            for temp_dir in temp_dirs:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    print(f"DEBUG: Cleaned up temp directory: {temp_dir}")
            
            # Clear the set
            self._temp_dirs = set()
            
            # Platform-specific memory cleanup
            gc.collect()
            if sys.platform == "win32":
                # Windows-specific: Force multiple GC cycles and explicit memory cleanup
                for _ in range(3):
                    gc.collect()
                    
        except Exception as e:
            print(f"DEBUG: Error during temp directory cleanup: {e}")
    
    def __del__(self):
        """Cleanup when object is destroyed."""
        try:
            self.stop_processing()
            self.cleanup_temp_directories()
        except Exception as e:
            print(f"DEBUG: Error in __del__: {e}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.stop_processing()
        self.cleanup_temp_directories() 