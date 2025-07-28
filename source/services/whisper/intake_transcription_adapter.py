"""
Intake Transcription Adapter

This module provides an adapter that integrates the improved transcription service
with the existing IntakeWindow, replacing callback-based communication with Qt signals.

The adapter maintains backward compatibility while providing the enhanced threading
architecture benefits.

Based on: docs/threading_vs_subprocess_analysis.md#threading-improvements
"""

import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal, QTimer

from .improved_transcription_service import (
    get_transcription_service, 
    ImprovedTranscriptionService,
    TranscriptionJob
)
from .enhanced_resource_monitor import get_resource_monitor

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionRequest:
    """Simplified transcription request for the adapter."""
    audio_path: Path
    backend: str
    model: str
    metadata: Optional[Dict[str, Any]] = None


class IntakeTranscriptionAdapter(QObject):
    """
    Adapter that connects the improved transcription service to IntakeWindow.
    
    This adapter provides a clean interface that replaces the old ThreadPoolExecutor
    approach with the new signal-based transcription service, while maintaining
    backward compatibility with existing UI code.
    
    Features:
    - Signal-based communication instead of callbacks
    - Automatic progress tracking
    - Resource monitoring integration
    - Timeout handling
    - Cancellation support
    """
    
    # Signals that match the existing IntakeWindow expectations
    transcription_started = Signal()
    transcription_completed = Signal(str)  # result
    transcription_failed = Signal(str)  # error_message
    transcription_progress = Signal(float)  # progress (0.0 to 1.0)
    transcription_timeout = Signal()
    
    # Additional monitoring signals
    resource_warning = Signal(str, str)  # resource_type, message
    service_stats_updated = Signal(dict)  # service statistics
    
    def __init__(self, timeout_seconds: int = 60):
        super().__init__()
        
        self.timeout_seconds = timeout_seconds
        
        # Get service instances
        self.transcription_service = get_transcription_service()
        self.resource_monitor = get_resource_monitor()
        
        # Current job tracking
        self.current_job_id: Optional[str] = None
        self.current_request: Optional[TranscriptionRequest] = None
        self.start_time: Optional[float] = None
        
        # Timeout timer
        self.timeout_timer = QTimer()
        self.timeout_timer.setSingleShot(True)
        self.timeout_timer.timeout.connect(self._handle_timeout)
        
        # Statistics timer
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self._update_statistics)
        self.stats_timer.start(10000)  # Update every 10 seconds
        
        # Connect to transcription service signals
        self._connect_service_signals()
        
        # Connect to resource monitor signals
        self._connect_resource_signals()
        
        # Start resource monitoring
        self.resource_monitor.start_monitoring()
        
        # Register cleanup callbacks
        self._register_cleanup_callbacks()
        
        logger.info(f"Intake transcription adapter initialized with {timeout_seconds}s timeout")
    
    def submit_transcription(self, 
                           audio_path: Path, 
                           backend: str, 
                           model: str,
                           metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Submit a transcription request.
        
        Returns:
            bool: True if submission was successful, False if already processing
        """
        if self.current_job_id:
            logger.warning("Transcription already in progress, ignoring new request")
            return False
        
        try:
            # Create request
            request = TranscriptionRequest(
                audio_path=audio_path,
                backend=backend,
                model=model,
                metadata=metadata or {}
            )
            
            # Submit to service
            job_id = self.transcription_service.submit_transcription(
                audio_path=audio_path,
                backend=backend,
                model=model,
                metadata=request.metadata
            )
            
            # Track current job
            self.current_job_id = job_id
            self.current_request = request
            self.start_time = time.time()
            
            # Start timeout timer
            self.timeout_timer.start(self.timeout_seconds * 1000)
            
            logger.info(f"Submitted transcription job {job_id} for {audio_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to submit transcription: {e}")
            self.transcription_failed.emit(f"Failed to submit transcription: {e}")
            return False
    
    def cancel_current_transcription(self) -> bool:
        """Cancel the current transcription if one is in progress."""
        if not self.current_job_id:
            return False
        
        success = self.transcription_service.cancel_job(self.current_job_id)
        if success:
            self._cleanup_current_job()
            logger.info(f"Cancelled transcription job {self.current_job_id}")
        
        return success
    
    def get_current_status(self) -> Optional[Dict[str, Any]]:
        """Get status of current transcription job."""
        if not self.current_job_id:
            return None
        
        job = self.transcription_service.get_job_status(self.current_job_id)
        if not job:
            return None
        
        elapsed_time = time.time() - self.start_time if self.start_time else 0
        
        return {
            "job_id": job.job_id,
            "state": job.state.value,
            "elapsed_time": elapsed_time,
            "estimated_progress": min(elapsed_time / self.timeout_seconds, 0.9),  # Conservative estimate
            "audio_path": str(job.audio_path),
            "backend": job.backend,
            "model": job.model
        }
    
    def get_service_statistics(self) -> Dict[str, Any]:
        """Get comprehensive service statistics."""
        return self.transcription_service.get_service_stats()
    
    def get_resource_statistics(self) -> Dict[str, Any]:
        """Get resource monitoring statistics."""
        return self.resource_monitor.get_statistics()
    
    def force_cleanup(self) -> None:
        """Force cleanup of all resources."""
        # Cancel current job if any
        self.cancel_current_transcription()
        
        # Force resource cleanup
        self.resource_monitor.force_cleanup()
        
        logger.info("Forced cleanup completed")
    
    def _connect_service_signals(self) -> None:
        """Connect to transcription service signals."""
        self.transcription_service.job_started.connect(self._on_job_started)
        self.transcription_service.job_completed.connect(self._on_job_completed)
        self.transcription_service.job_failed.connect(self._on_job_failed)
        self.transcription_service.progress_update.connect(self._on_progress_update)
    
    def _connect_resource_signals(self) -> None:
        """Connect to resource monitor signals."""
        self.resource_monitor.resource_warning.connect(self._on_resource_warning)
        self.resource_monitor.resource_critical.connect(self._on_resource_critical)
        self.resource_monitor.cleanup_triggered.connect(self._on_cleanup_triggered)
    
    def _register_cleanup_callbacks(self) -> None:
        """Register cleanup callbacks with resource monitor."""
        # Register transcription service cleanup
        self.resource_monitor.register_cleanup_callback(
            "transcription_service",
            self._cleanup_transcription_service
        )
        
        # Register memory cleanup
        self.resource_monitor.register_cleanup_callback(
            "memory",
            self._cleanup_memory
        )
        
        # Register thread cleanup
        self.resource_monitor.register_cleanup_callback(
            "threads",
            self._cleanup_threads
        )
    
    def _on_job_started(self, job_id: str) -> None:
        """Handle job started signal."""
        if job_id == self.current_job_id:
            self.transcription_started.emit()
            logger.info(f"Transcription job {job_id} started")
    
    def _on_job_completed(self, job_id: str, result: str) -> None:
        """Handle job completed signal."""
        if job_id == self.current_job_id:
            # Stop timeout timer
            self.timeout_timer.stop()
            
            # Calculate timing
            elapsed = time.time() - self.start_time if self.start_time else 0
            
            # Emit completion signal
            self.transcription_completed.emit(result)
            
            # Cleanup
            self._cleanup_current_job()
            
            logger.info(f"Transcription job {job_id} completed in {elapsed:.2f}s")
    
    def _on_job_failed(self, job_id: str, error: str) -> None:
        """Handle job failed signal."""
        if job_id == self.current_job_id:
            # Stop timeout timer
            self.timeout_timer.stop()
            
            # Emit failure signal
            self.transcription_failed.emit(error)
            
            # Cleanup
            self._cleanup_current_job()
            
            logger.error(f"Transcription job {job_id} failed: {error}")
    
    def _on_progress_update(self, job_id: str, progress: float) -> None:
        """Handle progress update signal."""
        if job_id == self.current_job_id:
            self.transcription_progress.emit(progress)
    
    def _on_resource_warning(self, resource_type: str, message: str) -> None:
        """Handle resource warning."""
        self.resource_warning.emit(resource_type, message)
        logger.warning(f"Resource warning - {resource_type}: {message}")
    
    def _on_resource_critical(self, resource_type: str, message: str) -> None:
        """Handle critical resource issue."""
        self.resource_warning.emit(resource_type, f"CRITICAL: {message}")
        logger.error(f"CRITICAL resource issue - {resource_type}: {message}")
        
        # For critical issues, consider cancelling current transcription
        if self.current_job_id and "memory" in resource_type:
            logger.warning("Cancelling transcription due to critical memory issue")
            self.cancel_current_transcription()
    
    def _on_cleanup_triggered(self, cleanup_type: str) -> None:
        """Handle cleanup triggered event."""
        logger.info(f"Cleanup triggered for {cleanup_type}")
    
    def _handle_timeout(self) -> None:
        """Handle transcription timeout."""
        if self.current_job_id:
            logger.warning(f"Transcription job {self.current_job_id} timed out after {self.timeout_seconds}s")
            
            # Try to cancel the job
            self.cancel_current_transcription()
            
            # Emit timeout signal
            self.transcription_timeout.emit()
    
    def _update_statistics(self) -> None:
        """Update and emit service statistics."""
        try:
            stats = self.get_service_statistics()
            self.service_stats_updated.emit(stats)
        except Exception as e:
            logger.error(f"Failed to update statistics: {e}")
    
    def _cleanup_current_job(self) -> None:
        """Clean up current job tracking."""
        self.current_job_id = None
        self.current_request = None
        self.start_time = None
        self.timeout_timer.stop()
    
    def _cleanup_transcription_service(self) -> None:
        """Cleanup transcription service resources."""
        try:
            # Cancel current job if any
            if self.current_job_id:
                self.transcription_service.cancel_job(self.current_job_id)
            
            # The service has its own cleanup mechanisms
            logger.info("Transcription service cleanup completed")
            
        except Exception as e:
            logger.error(f"Transcription service cleanup failed: {e}")
    
    def _cleanup_memory(self) -> None:
        """Cleanup memory resources."""
        try:
            import gc
            collected = gc.collect()
            logger.info(f"Memory cleanup collected {collected} objects")
            
        except Exception as e:
            logger.error(f"Memory cleanup failed: {e}")
    
    def _cleanup_threads(self) -> None:
        """Cleanup thread resources."""
        try:
            # Cancel current transcription to free up threads
            if self.current_job_id:
                self.cancel_current_transcription()
            
            logger.info("Thread cleanup completed")
            
        except Exception as e:
            logger.error(f"Thread cleanup failed: {e}")


# Convenience function for easy integration
def create_intake_adapter(timeout_seconds: int = 60) -> IntakeTranscriptionAdapter:
    """Create an intake transcription adapter with default settings."""
    return IntakeTranscriptionAdapter(timeout_seconds=timeout_seconds)