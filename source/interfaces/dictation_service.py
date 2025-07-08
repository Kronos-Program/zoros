"""
Dictation Service - Decoupled Background Processing

This module provides a completely decoupled dictation service that runs independently
from the UI, using signal-slot communication for status updates and results.

Key Features:
- Background transcription service with hot-loading
- Memory and worker management
- Audio stream maintenance
- Queue-based processing
- Signal-based UI communication
- Always responsive UI

Architecture:
UI Process <--signals/slots--> Dictation Service Process
- UI stays responsive                - Model loading/caching
- Edit preservation                  - Memory management  
- Navigation between records         - Worker pool management
- Real-time status updates          - Audio processing
                                    - Error recovery

Author: ZorOS Development Team
Date: 2025-01-05
"""

import json
import sys
import time
import threading
import multiprocessing as mp
import queue
import signal
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import logging

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from PySide6.QtCore import QObject, Signal, QThread, QTimer
    from PySide6.QtWidgets import QApplication
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False
    # Dummy Signal class for non-Qt environments
    class Signal:
        def __init__(self, *args):
            pass
        def emit(self, *args):
            pass
        def connect(self, func):
            pass

logger = logging.getLogger(__name__)


class DictationStatus(Enum):
    """Status states for dictation operations."""
    IDLE = "idle"
    LOADING_MODEL = "loading_model"
    READY = "ready"
    RECORDING = "recording"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class DictationRequest:
    """Request object for dictation operations."""
    request_id: str
    audio_path: str
    backend: str = "MLXWhisper"
    model: str = "small"
    robust_mode: bool = True
    timeout: Optional[int] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class DictationResponse:
    """Response object for dictation results."""
    request_id: str
    status: DictationStatus
    transcript: str = ""
    confidence: float = 0.0
    processing_time: float = 0.0
    backend_used: str = ""
    error_message: str = ""
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ServiceStatus:
    """Status object for the dictation service."""
    status: DictationStatus
    loaded_models: List[str]
    available_memory: float
    active_workers: int
    queue_length: int
    last_update: str
    error_count: int = 0


class DictationServiceProcess:
    """Background dictation service that runs in a separate process."""
    
    def __init__(self, request_queue: mp.Queue, response_queue: mp.Queue, status_queue: mp.Queue):
        self.request_queue = request_queue
        self.response_queue = response_queue
        self.status_queue = status_queue
        
        # Service state
        self.status = DictationStatus.IDLE
        self.loaded_models = {}
        self.worker_pool = None
        self.current_backend = None
        self.running = True
        
        # Performance tracking
        self.memory_usage = 0.0
        self.error_count = 0
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._shutdown_handler)
        signal.signal(signal.SIGINT, self._shutdown_handler)
    
    def run(self):
        """Main service loop."""
        logger.info("Dictation service started")
        
        try:
            self._initialize_service()
            
            while self.running:
                self._process_requests()
                self._update_status()
                time.sleep(0.1)  # Small delay to prevent busy waiting
                
        except Exception as e:
            logger.error(f"Service error: {e}")
            self.error_count += 1
        finally:
            self._cleanup_service()
    
    def _initialize_service(self):
        """Initialize the dictation service."""
        from concurrent.futures import ThreadPoolExecutor
        
        self.status = DictationStatus.LOADING_MODEL
        self.worker_pool = ThreadPoolExecutor(max_workers=2)
        
        # Pre-load default model
        try:
            self._load_model("MLXWhisper", "small")
            self.status = DictationStatus.READY
            logger.info("Service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize service: {e}")
            self.status = DictationStatus.ERROR
            self.error_count += 1
    
    def _process_requests(self):
        """Process incoming dictation requests."""
        try:
            # Non-blocking queue check
            request_dict = self.request_queue.get_nowait()
            request = DictationRequest(**request_dict)
            
            logger.info(f"Processing request: {request.request_id}")
            
            # Submit to worker pool
            future = self.worker_pool.submit(self._handle_dictation_request, request)
            
            # Note: In a production version, we'd track multiple concurrent requests
            # For now, we'll process one at a time for simplicity
            
        except queue.Empty:
            pass  # No requests to process
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            self.error_count += 1
    
    def _handle_dictation_request(self, request: DictationRequest) -> None:
        """Handle a single dictation request."""
        start_time = time.time()
        
        response = DictationResponse(
            request_id=request.request_id,
            status=DictationStatus.PROCESSING
        )
        
        try:
            # Send processing status
            self.response_queue.put(asdict(response))
            
            # Ensure model is loaded
            if not self._ensure_model_loaded(request.backend, request.model):
                raise RuntimeError(f"Failed to load model {request.backend}/{request.model}")
            
            # Perform transcription
            if request.robust_mode:
                transcript = self._robust_transcribe(request)
            else:
                transcript = self._simple_transcribe(request)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Send success response
            response.status = DictationStatus.COMPLETED
            response.transcript = transcript
            response.processing_time = processing_time
            response.backend_used = request.backend
            response.confidence = 0.95  # Mock confidence for now
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            response.status = DictationStatus.ERROR
            response.error_message = str(e)
            response.processing_time = time.time() - start_time
            self.error_count += 1
        
        # Send final response
        self.response_queue.put(asdict(response))
    
    def _ensure_model_loaded(self, backend: str, model: str) -> bool:
        """Ensure the specified model is loaded and ready."""
        model_key = f"{backend}_{model}"
        
        if model_key in self.loaded_models:
            return True
        
        try:
            self.status = DictationStatus.LOADING_MODEL
            success = self._load_model(backend, model)
            self.status = DictationStatus.READY if success else DictationStatus.ERROR
            return success
        except Exception as e:
            logger.error(f"Failed to load model {model_key}: {e}")
            return False
    
    def _load_model(self, backend: str, model: str) -> bool:
        """Load a specific model."""
        try:
            # Import here to avoid loading in main process
            from source.dictation_backends import get_available_backends
            
            if backend not in get_available_backends():
                raise ValueError(f"Backend {backend} not available")
            
            # Create backend instance
            if backend == "MLXWhisper":
                from source.dictation_backends.mlx_whisper_backend import MLXWhisperBackend
                backend_instance = MLXWhisperBackend(model)
            elif backend == "FasterWhisper":
                from source.dictation_backends.faster_whisper_backend import FasterWhisperBackend
                backend_instance = FasterWhisperBackend(model)
            else:
                # Other backends...
                raise NotImplementedError(f"Backend {backend} not implemented in service")
            
            # Test the model by transcribing silence
            test_audio = Path("/tmp/test_silence.wav")
            if not test_audio.exists():
                self._create_test_audio(test_audio)
            
            # Quick test transcription
            test_result = backend_instance.transcribe(str(test_audio))
            
            # Store loaded model
            model_key = f"{backend}_{model}"
            self.loaded_models[model_key] = backend_instance
            
            logger.info(f"Successfully loaded model: {model_key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load {backend}/{model}: {e}")
            return False
    
    def _create_test_audio(self, path: Path):
        """Create a small test audio file."""
        try:
            import soundfile as sf
            import numpy as np
            
            # Create 1 second of silence
            silence = np.zeros(16000, dtype=np.float32)
            sf.write(path, silence, 16000)
        except Exception as e:
            logger.warning(f"Could not create test audio: {e}")
    
    def _simple_transcribe(self, request: DictationRequest) -> str:
        """Perform simple transcription."""
        model_key = f"{request.backend}_{request.model}"
        backend_instance = self.loaded_models[model_key]
        
        return backend_instance.transcribe(request.audio_path)
    
    def _robust_transcribe(self, request: DictationRequest) -> str:
        """Perform robust transcription with fallbacks."""
        try:
            from source.interfaces.dictation_stability import get_stability_manager
            
            stability_manager = get_stability_manager()
            result = stability_manager.robust_transcribe(
                Path(request.audio_path),
                progress_callback=None,  # Could be enhanced to send progress
                max_retries=2
            )
            
            if result["success"]:
                return result["transcript"]
            else:
                raise RuntimeError("All transcription attempts failed")
                
        except ImportError:
            # Fallback to simple transcription
            return self._simple_transcribe(request)
    
    def _update_status(self):
        """Send status update to UI."""
        try:
            status = ServiceStatus(
                status=self.status,
                loaded_models=list(self.loaded_models.keys()),
                available_memory=self._get_memory_usage(),
                active_workers=1 if self.worker_pool else 0,  # Simplified
                queue_length=self.request_queue.qsize(),
                last_update=datetime.now().isoformat(),
                error_count=self.error_count
            )
            
            # Non-blocking status update
            try:
                self.status_queue.put_nowait(asdict(status))
            except queue.Full:
                pass  # Skip update if queue is full
                
        except Exception as e:
            logger.error(f"Error updating status: {e}")
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            return 0.0
    
    def _shutdown_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info("Received shutdown signal")
        self.running = False
    
    def _cleanup_service(self):
        """Clean up service resources."""
        if self.worker_pool:
            self.worker_pool.shutdown(wait=True)
        logger.info("Dictation service stopped")


class DictationServiceInterface(QObject if QT_AVAILABLE else object):
    """Qt interface for communicating with the dictation service."""
    
    # Signals for UI communication
    if QT_AVAILABLE:
        status_updated = Signal(dict)
        transcription_completed = Signal(str, str)  # request_id, transcript
        transcription_failed = Signal(str, str)     # request_id, error
        progress_updated = Signal(str, float)        # message, progress
    
    def __init__(self):
        if QT_AVAILABLE:
            super().__init__()
        
        # IPC queues
        self.request_queue = mp.Queue(maxsize=10)
        self.response_queue = mp.Queue(maxsize=50)
        self.status_queue = mp.Queue(maxsize=5)
        
        # Service process
        self.service_process = None
        self.running = False
        
        # UI polling timer
        if QT_AVAILABLE:
            self.poll_timer = QTimer()
            self.poll_timer.timeout.connect(self._poll_responses)
            self.poll_timer.setInterval(100)  # 100ms polling
        
        # Current status
        self.current_status = ServiceStatus(
            status=DictationStatus.IDLE,
            loaded_models=[],
            available_memory=0.0,
            active_workers=0,
            queue_length=0,
            last_update=datetime.now().isoformat()
        )
    
    def start_service(self) -> bool:
        """Start the background dictation service."""
        if self.running:
            return True
        
        try:
            # Start service process
            self.service_process = mp.Process(
                target=self._run_service_process,
                args=(self.request_queue, self.response_queue, self.status_queue)
            )
            self.service_process.start()
            
            # Start polling timer
            if QT_AVAILABLE:
                self.poll_timer.start()
            
            self.running = True
            logger.info("Dictation service interface started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start service: {e}")
            return False
    
    def stop_service(self):
        """Stop the background dictation service."""
        if not self.running:
            return
        
        try:
            # Stop polling
            if QT_AVAILABLE:
                self.poll_timer.stop()
            
            # Terminate service process
            if self.service_process and self.service_process.is_alive():
                self.service_process.terminate()
                self.service_process.join(timeout=5.0)
                
                if self.service_process.is_alive():
                    self.service_process.kill()
            
            self.running = False
            logger.info("Dictation service interface stopped")
            
        except Exception as e:
            logger.error(f"Error stopping service: {e}")
    
    def submit_transcription(self, audio_path: str, **kwargs) -> str:
        """Submit a transcription request and return request ID."""
        if not self.running:
            raise RuntimeError("Service not running")
        
        request_id = f"req_{int(time.time() * 1000)}"
        
        request = DictationRequest(
            request_id=request_id,
            audio_path=audio_path,
            **kwargs
        )
        
        try:
            self.request_queue.put_nowait(asdict(request))
            logger.info(f"Submitted transcription request: {request_id}")
            return request_id
        except queue.Full:
            raise RuntimeError("Service queue is full")
    
    def cancel_transcription(self, request_id: str) -> bool:
        """Cancel a transcription request (if possible)."""
        # Note: In a full implementation, we'd need a cancellation mechanism
        # For now, this is a placeholder
        logger.info(f"Cancellation requested for: {request_id}")
        return True
    
    def get_service_status(self) -> ServiceStatus:
        """Get current service status."""
        return self.current_status
    
    def restart_service(self) -> bool:
        """Restart the dictation service."""
        logger.info("Restarting dictation service")
        self.stop_service()
        time.sleep(1.0)
        return self.start_service()
    
    def _run_service_process(self, req_queue, resp_queue, status_queue):
        """Entry point for the service process."""
        service = DictationServiceProcess(req_queue, resp_queue, status_queue)
        service.run()
    
    def _poll_responses(self):
        """Poll for responses from the service."""
        # Poll responses
        while True:
            try:
                response_dict = self.response_queue.get_nowait()
                response = DictationResponse(**response_dict)
                self._handle_response(response)
            except queue.Empty:
                break
        
        # Poll status updates
        try:
            status_dict = self.status_queue.get_nowait()
            self.current_status = ServiceStatus(**status_dict)
            if QT_AVAILABLE:
                self.status_updated.emit(status_dict)
        except queue.Empty:
            pass
    
    def _handle_response(self, response: DictationResponse):
        """Handle a response from the service."""
        if QT_AVAILABLE:
            if response.status == DictationStatus.COMPLETED:
                self.transcription_completed.emit(response.request_id, response.transcript)
            elif response.status == DictationStatus.ERROR:
                self.transcription_failed.emit(response.request_id, response.error_message)
        
        logger.info(f"Response received: {response.request_id} - {response.status}")


# Global service interface instance
_service_interface = None

def get_dictation_service() -> DictationServiceInterface:
    """Get or create the global dictation service interface."""
    global _service_interface
    if _service_interface is None:
        _service_interface = DictationServiceInterface()
    return _service_interface


def start_dictation_service() -> bool:
    """Start the global dictation service."""
    service = get_dictation_service()
    return service.start_service()


def stop_dictation_service():
    """Stop the global dictation service."""
    service = get_dictation_service()
    service.stop_service()


if __name__ == "__main__":
    # Test the service
    import tempfile
    
    service = DictationServiceInterface()
    
    if service.start_service():
        print("Service started successfully")
        
        # Create a test audio file
        test_audio = Path(tempfile.mktemp(suffix=".wav"))
        # ... create test audio ...
        
        # Submit test request
        # request_id = service.submit_transcription(str(test_audio))
        # print(f"Submitted request: {request_id}")
        
        time.sleep(5)  # Let it run for a bit
        
        service.stop_service()
        print("Service stopped")
    else:
        print("Failed to start service")