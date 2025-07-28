"""
Improved Transcription Service with Enhanced Threading Architecture

This module implements the threading improvements outlined in the architectural analysis:
1. QMutex and QWaitCondition for better thread synchronization
2. Enhanced thread pool management with proper cleanup and monitoring
3. Qt signals for transcription communication instead of callbacks
4. Enhanced resource monitoring and automatic cleanup

Based on: docs/threading_vs_subprocess_analysis.md#threading-improvements
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from PySide6.QtCore import QObject, Signal, QMutex, QWaitCondition, QThread, QMutexLocker, QTimer
from PySide6.QtWidgets import QApplication

logger = logging.getLogger(__name__)


class TranscriptionState(Enum):
    """Transcription job states."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TranscriptionJob:
    """Represents a transcription job with metadata."""
    job_id: str
    audio_path: Path
    backend: str
    model: str
    state: TranscriptionState = TranscriptionState.PENDING
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    result: str = ""
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> Optional[float]:
        """Get job processing duration."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None


class TranscriptionWorker(QObject):
    """
    Qt-based transcription worker that runs in a separate thread.
    
    Uses Qt's signal/slot mechanism for thread-safe communication
    and proper resource management.
    """
    
    # Signals for thread-safe communication
    job_started = Signal(str)  # job_id
    job_completed = Signal(str, str)  # job_id, result
    job_failed = Signal(str, str)  # job_id, error_message
    progress_update = Signal(str, float)  # job_id, progress (0-1)
    
    def __init__(self):
        super().__init__()
        self.jobs_queue = []
        self.current_job: Optional[TranscriptionJob] = None
        self.is_running = False
        
        # Thread synchronization primitives
        self.queue_mutex = QMutex()
        self.queue_condition = QWaitCondition()
        self.shutdown_mutex = QMutex()
        
        # Resource tracking
        self.processed_jobs = 0
        self.failed_jobs = 0
        self.total_processing_time = 0.0
    
    def add_job(self, job: TranscriptionJob) -> None:
        """Add a transcription job to the queue thread-safely."""
        with QMutexLocker(self.queue_mutex):
            self.jobs_queue.append(job)
            logger.info(f"Added transcription job {job.job_id} to queue")
            self.queue_condition.wakeOne()
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending job."""
        with QMutexLocker(self.queue_mutex):
            for job in self.jobs_queue:
                if job.job_id == job_id and job.state == TranscriptionState.PENDING:
                    job.state = TranscriptionState.CANCELLED
                    self.jobs_queue.remove(job)
                    logger.info(f"Cancelled job {job_id}")
                    return True
            return False
    
    def start_processing(self) -> None:
        """Start the worker processing loop."""
        with QMutexLocker(self.shutdown_mutex):
            if self.is_running:
                return
            self.is_running = True
        
        logger.info("Starting transcription worker processing loop")
        self._processing_loop()
    
    def stop_processing(self) -> None:
        """Stop the worker processing loop."""
        with QMutexLocker(self.shutdown_mutex):
            self.is_running = False
        
        # Wake up the processing loop to check shutdown condition
        with QMutexLocker(self.queue_mutex):
            self.queue_condition.wakeOne()
        
        logger.info("Stopped transcription worker processing")
    
    def _processing_loop(self) -> None:
        """Main processing loop for the worker."""
        while True:
            job = self._get_next_job()
            if job is None:
                # Check if we should shutdown
                with QMutexLocker(self.shutdown_mutex):
                    if not self.is_running:
                        break
                continue
            
            self._process_job(job)
    
    def _get_next_job(self) -> Optional[TranscriptionJob]:
        """Get the next job from the queue, waiting if necessary."""
        with QMutexLocker(self.queue_mutex):
            while len(self.jobs_queue) == 0:
                # Check if we should shutdown
                with QMutexLocker(self.shutdown_mutex):
                    if not self.is_running:
                        return None
                
                # Wait for new jobs or shutdown signal
                self.queue_condition.wait(self.queue_mutex, 1000)  # 1 second timeout
                
                # Check shutdown again after wait
                with QMutexLocker(self.shutdown_mutex):
                    if not self.is_running:
                        return None
            
            # Get the next job
            job = self.jobs_queue.pop(0)
            job.state = TranscriptionState.PROCESSING
            self.current_job = job
            return job
    
    def _process_job(self, job: TranscriptionJob) -> None:
        """Process a single transcription job."""
        job.start_time = time.time()
        logger.info(f"Processing transcription job {job.job_id}: {job.audio_path}")
        
        try:
            # Emit job started signal
            self.job_started.emit(job.job_id)
            
            # Import and get the backend
            from backend.services.dictation import get_backend_class
            
            backend_class = get_backend_class(job.backend)
            if not backend_class:
                raise ValueError(f"Backend not found: {job.backend}")
            
            # Create backend instance
            backend_instance = backend_class(job.model)
            
            # Progress simulation (real backends could provide actual progress)
            self.progress_update.emit(job.job_id, 0.1)
            
            # Perform transcription
            if hasattr(backend_instance, 'transcribe'):
                result = backend_instance.transcribe(str(job.audio_path))
            else:
                raise AttributeError(f"Backend {job.backend} does not have transcribe method")
            
            # Update job state
            job.end_time = time.time()
            job.result = result
            job.state = TranscriptionState.COMPLETED
            
            # Update statistics
            self.processed_jobs += 1
            if job.duration:
                self.total_processing_time += job.duration
            
            # Emit completion signal
            self.job_completed.emit(job.job_id, result)
            self.progress_update.emit(job.job_id, 1.0)
            
            logger.info(f"Completed job {job.job_id} in {job.duration:.2f}s")
            
        except Exception as e:
            # Handle job failure
            job.end_time = time.time()
            job.error = str(e)
            job.state = TranscriptionState.FAILED
            self.failed_jobs += 1
            
            logger.error(f"Job {job.job_id} failed: {e}")
            self.job_failed.emit(job.job_id, str(e))
            
        finally:
            self.current_job = None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get worker statistics."""
        avg_time = (self.total_processing_time / self.processed_jobs 
                   if self.processed_jobs > 0 else 0.0)
        
        return {
            "processed_jobs": self.processed_jobs,
            "failed_jobs": self.failed_jobs,
            "total_processing_time": self.total_processing_time,
            "average_processing_time": avg_time,
            "current_job": self.current_job.job_id if self.current_job else None,
            "queue_length": len(self.jobs_queue),
            "is_running": self.is_running
        }


class ImprovedTranscriptionService(QObject):
    """
    Improved transcription service with enhanced threading architecture.
    
    Features:
    - Qt-based thread management with proper cleanup
    - Signal-based communication instead of callbacks
    - Enhanced resource monitoring
    - Automatic thread pool scaling
    """
    
    # Service-level signals
    job_queued = Signal(str)  # job_id
    job_started = Signal(str)  # job_id
    job_completed = Signal(str, str)  # job_id, result
    job_failed = Signal(str, str)  # job_id, error
    progress_update = Signal(str, float)  # job_id, progress
    service_error = Signal(str)  # error_message
    
    def __init__(self, max_workers: int = 2):
        super().__init__()
        self.max_workers = max_workers
        self.workers: Dict[str, TranscriptionWorker] = {}
        self.worker_threads: Dict[str, QThread] = {}
        self.jobs: Dict[str, TranscriptionJob] = {}
        
        # Service state
        self.is_running = False
        self.next_job_id = 0
        
        # Resource monitoring
        self.resource_monitor_timer = QTimer()
        self.resource_monitor_timer.timeout.connect(self._monitor_resources)
        self.resource_monitor_timer.start(5000)  # Check every 5 seconds
        
        # Cleanup timer for completed jobs
        self.cleanup_timer = QTimer()
        self.cleanup_timer.timeout.connect(self._cleanup_completed_jobs)
        self.cleanup_timer.start(30000)  # Cleanup every 30 seconds
        
        logger.info(f"Initialized improved transcription service with {max_workers} workers")
    
    def start_service(self) -> None:
        """Start the transcription service."""
        if self.is_running:
            return
        
        self.is_running = True
        
        # Create initial worker threads
        for i in range(min(1, self.max_workers)):  # Start with 1 worker
            self._create_worker(f"worker_{i}")
        
        logger.info("Transcription service started")
    
    def stop_service(self) -> None:
        """Stop the transcription service and cleanup resources."""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Stop all workers
        for worker_id in list(self.workers.keys()):
            self._destroy_worker(worker_id)
        
        # Stop timers
        self.resource_monitor_timer.stop()
        self.cleanup_timer.stop()
        
        logger.info("Transcription service stopped")
    
    def submit_transcription(
        self, 
        audio_path: Path, 
        backend: str, 
        model: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Submit a transcription job.
        
        Returns:
            job_id: Unique identifier for tracking the job
        """
        if not self.is_running:
            raise RuntimeError("Transcription service is not running")
        
        # Generate unique job ID
        job_id = f"job_{self.next_job_id}"
        self.next_job_id += 1
        
        # Create job
        job = TranscriptionJob(
            job_id=job_id,
            audio_path=audio_path,
            backend=backend,
            model=model,
            metadata=metadata or {}
        )
        
        # Store job
        self.jobs[job_id] = job
        
        # Get or create an available worker
        worker = self._get_available_worker()
        if worker:
            worker.add_job(job)
            self.job_queued.emit(job_id)
            logger.info(f"Submitted transcription job {job_id}")
        else:
            job.state = TranscriptionState.FAILED
            job.error = "No available workers"
            self.job_failed.emit(job_id, "No available workers")
        
        return job_id
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a transcription job."""
        job = self.jobs.get(job_id)
        if not job:
            return False
        
        if job.state in [TranscriptionState.COMPLETED, TranscriptionState.FAILED]:
            return False
        
        # Try to cancel from workers
        for worker in self.workers.values():
            if worker.cancel_job(job_id):
                job.state = TranscriptionState.CANCELLED
                return True
        
        return False
    
    def get_job_status(self, job_id: str) -> Optional[TranscriptionJob]:
        """Get the status of a transcription job."""
        return self.jobs.get(job_id)
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get comprehensive service statistics."""
        worker_stats = {}
        total_processed = 0
        total_failed = 0
        total_time = 0.0
        
        for worker_id, worker in self.workers.items():
            stats = worker.get_stats()
            worker_stats[worker_id] = stats
            total_processed += stats["processed_jobs"]
            total_failed += stats["failed_jobs"]
            total_time += stats["total_processing_time"]
        
        return {
            "is_running": self.is_running,
            "active_workers": len(self.workers),
            "max_workers": self.max_workers,
            "total_jobs": len(self.jobs),
            "total_processed": total_processed,
            "total_failed": total_failed,
            "total_processing_time": total_time,
            "average_processing_time": total_time / total_processed if total_processed > 0 else 0.0,
            "worker_stats": worker_stats,
            "jobs_by_state": self._get_jobs_by_state()
        }
    
    def _create_worker(self, worker_id: str) -> None:
        """Create a new worker thread."""
        if worker_id in self.workers:
            return
        
        # Create worker
        worker = TranscriptionWorker()
        
        # Create thread
        thread = QThread()
        worker.moveToThread(thread)
        
        # Connect signals
        worker.job_started.connect(self.job_started)
        worker.job_completed.connect(self._on_job_completed)
        worker.job_failed.connect(self._on_job_failed)
        worker.progress_update.connect(self.progress_update)
        
        # Connect thread lifecycle
        thread.started.connect(worker.start_processing)
        thread.finished.connect(lambda: self._on_worker_finished(worker_id))
        
        # Store references
        self.workers[worker_id] = worker
        self.worker_threads[worker_id] = thread
        
        # Start thread
        thread.start()
        
        logger.info(f"Created worker {worker_id}")
    
    def _destroy_worker(self, worker_id: str) -> None:
        """Destroy a worker thread."""
        worker = self.workers.get(worker_id)
        thread = self.worker_threads.get(worker_id)
        
        if worker:
            worker.stop_processing()
        
        if thread:
            thread.quit()
            if not thread.wait(5000):  # 5 second timeout
                logger.warning(f"Worker {worker_id} thread did not terminate gracefully")
                thread.terminate()
                thread.wait(1000)
        
        # Remove references
        self.workers.pop(worker_id, None)
        self.worker_threads.pop(worker_id, None)
        
        logger.info(f"Destroyed worker {worker_id}")
    
    def _get_available_worker(self) -> Optional[TranscriptionWorker]:
        """Get an available worker or create one if needed."""
        # Find worker with shortest queue
        best_worker = None
        min_queue_length = float('inf')
        
        for worker in self.workers.values():
            queue_length = len(worker.jobs_queue)
            if queue_length < min_queue_length:
                min_queue_length = queue_length
                best_worker = worker
        
        # If all workers are busy and we can create more, do so
        if (best_worker is None or min_queue_length > 2) and len(self.workers) < self.max_workers:
            worker_id = f"worker_{len(self.workers)}"
            self._create_worker(worker_id)
            best_worker = self.workers.get(worker_id)
        
        return best_worker
    
    def _on_job_completed(self, job_id: str, result: str) -> None:
        """Handle job completion."""
        job = self.jobs.get(job_id)
        if job:
            job.result = result
            job.state = TranscriptionState.COMPLETED
        
        self.job_completed.emit(job_id, result)
    
    def _on_job_failed(self, job_id: str, error: str) -> None:
        """Handle job failure."""
        job = self.jobs.get(job_id)
        if job:
            job.error = error
            job.state = TranscriptionState.FAILED
        
        self.job_failed.emit(job_id, error)
    
    def _on_worker_finished(self, worker_id: str) -> None:
        """Handle worker thread finishing."""
        logger.info(f"Worker {worker_id} finished")
    
    def _monitor_resources(self) -> None:
        """Monitor resource usage and scale workers if needed."""
        if not self.is_running:
            return
        
        stats = self.get_service_stats()
        
        # Log statistics periodically
        logger.debug(f"Service stats: {stats['total_processed']} processed, "
                    f"{stats['active_workers']} workers, "
                    f"avg time: {stats['average_processing_time']:.2f}s")
        
        # Auto-scaling logic could go here
        # For now, we keep it simple with manual worker management
    
    def _cleanup_completed_jobs(self) -> None:
        """Clean up old completed/failed jobs to prevent memory leaks."""
        current_time = time.time()
        cleanup_age = 300  # 5 minutes
        
        jobs_to_remove = []
        for job_id, job in self.jobs.items():
            if (job.state in [TranscriptionState.COMPLETED, TranscriptionState.FAILED, TranscriptionState.CANCELLED] 
                and job.end_time 
                and current_time - job.end_time > cleanup_age):
                jobs_to_remove.append(job_id)
        
        for job_id in jobs_to_remove:
            del self.jobs[job_id]
            logger.debug(f"Cleaned up job {job_id}")
    
    def _get_jobs_by_state(self) -> Dict[str, int]:
        """Get count of jobs by state."""
        state_counts = {}
        for job in self.jobs.values():
            state_counts[job.state.value] = state_counts.get(job.state.value, 0) + 1
        return state_counts


# Global service instance
_transcription_service: Optional[ImprovedTranscriptionService] = None


def get_transcription_service() -> ImprovedTranscriptionService:
    """Get the global improved transcription service instance."""
    global _transcription_service
    if _transcription_service is None:
        _transcription_service = ImprovedTranscriptionService()
        _transcription_service.start_service()
    return _transcription_service


def shutdown_transcription_service() -> None:
    """Shutdown the global transcription service."""
    global _transcription_service
    if _transcription_service:
        _transcription_service.stop_service()
        _transcription_service = None