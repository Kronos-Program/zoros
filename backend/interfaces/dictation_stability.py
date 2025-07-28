"""
Dictation Stability Enhancement Module

This module provides comprehensive stability improvements for the ZorOS dictation system,
including automatic recovery, intelligent backend fallbacks, and performance optimization.

Key Features:
- Automatic retry with different backends on failure
- Intelligent audio preprocessing and validation
- Progressive timeout handling
- Background transcription with UI responsiveness
- Comprehensive error recovery

Author: ZorOS Development Team
Date: 2025-01-05
"""

import json
import sys
import time
import threading
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
import logging

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Avoid circular imports by using late imports
try:
    from source.utils.resource_monitor import ResourceMonitor
    import soundfile as sf
    import numpy as np
    AUDIO_DEPS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Audio dependencies not available: {e}")
    AUDIO_DEPS_AVAILABLE = False

# Import functions that might cause circular imports
def get_available_backends():
    """Get available backends with late import to avoid circular dependencies."""
    try:
        from source.dictation_backends import get_available_backends as _get_available_backends
        return _get_available_backends()
    except ImportError:
        return ["MLXWhisper", "FasterWhisper", "StandardOpenAIWhisper"]

def transcribe_audio(audio_path: str, backend: str, model: str = "small"):
    """Transcribe audio with late import to avoid circular dependencies."""
    try:
        # Import backends directly to avoid circular imports
        if backend == "MLXWhisper":
            from source.dictation_backends.mlx_whisper_backend import MLXWhisperBackend
            backend_instance = MLXWhisperBackend(model)
        elif backend == "FasterWhisper":
            from source.dictation_backends.faster_whisper_backend import FasterWhisperBackend
            backend_instance = FasterWhisperBackend(model)
        elif backend == "StandardOpenAIWhisper":
            from source.dictation_backends.standard_openai_whisper_backend import StandardOpenAIWhisperBackend
            backend_instance = StandardOpenAIWhisperBackend(model)
        else:
            raise ValueError(f"Unknown backend: {backend}")
        
        return backend_instance.transcribe(audio_path)
    except Exception as e:
        raise RuntimeError(f"Transcription failed with {backend}: {e}")

logger = logging.getLogger(__name__)


class DictationStabilityManager:
    """Enhanced stability management for dictation operations."""
    
    def __init__(self):
        self.recovery_dir = Path.home() / ".zoros" / "recovery"
        self.stability_log = self.recovery_dir / "stability_log.json"
        self.recovery_dir.mkdir(parents=True, exist_ok=True)
        
        # Performance configuration
        self.backend_priority = [
            "MLXWhisper",           # Fastest for Apple Silicon
            "FasterWhisper",        # GPU accelerated
            "StandardOpenAIWhisper", # Reliable fallback
            "OpenAIAPI"            # Cloud backup
        ]
        
        # Timeout configuration (seconds)
        self.timeout_config = {
            "short": (0, 30),      # 0-30s audio: 60s timeout
            "medium": (30, 120),   # 30-120s audio: 180s timeout  
            "long": (120, 300),    # 120-300s audio: 300s timeout
            "very_long": (300, float('inf'))  # 300s+ audio: 600s timeout
        }
        
        self.timeout_values = {
            "short": 60,
            "medium": 180,
            "long": 300,
            "very_long": 600
        }
        
        # Auto-recovery tracking
        self.failure_counts = {}
        self.success_rates = {}
        
        self.load_stability_log()
    
    def load_stability_log(self) -> None:
        """Load stability tracking data."""
        if self.stability_log.exists():
            try:
                with open(self.stability_log, 'r') as f:
                    data = json.load(f)
                    self.failure_counts = data.get("failure_counts", {})
                    self.success_rates = data.get("success_rates", {})
            except Exception as e:
                logger.warning(f"Error loading stability log: {e}")
    
    def save_stability_log(self) -> None:
        """Save stability tracking data."""
        try:
            data = {
                "failure_counts": self.failure_counts,
                "success_rates": self.success_rates,
                "last_updated": datetime.now().isoformat()
            }
            with open(self.stability_log, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving stability log: {e}")
    
    def analyze_audio_file(self, audio_path: Path) -> Dict[str, Any]:
        """Analyze audio file for preprocessing and optimization."""
        try:
            with sf.SoundFile(audio_path) as f:
                duration = len(f) / f.samplerate
                channels = f.channels
                samplerate = f.samplerate
                
                # Read a sample for analysis
                f.seek(0)
                sample_data = f.read(min(f.frames, int(f.samplerate * 5)))  # 5s sample
                
                # Audio quality metrics
                rms = np.sqrt(np.mean(sample_data**2))
                peak = np.max(np.abs(sample_data))
                
            file_size = audio_path.stat().st_size
            
            # Determine category for timeout selection
            category = self._get_duration_category(duration)
            
            return {
                "duration": duration,
                "channels": channels,
                "samplerate": samplerate,
                "file_size": file_size,
                "file_size_mb": file_size / (1024 * 1024),
                "rms_level": float(rms),
                "peak_level": float(peak),
                "category": category,
                "recommended_timeout": self.timeout_values[category],
                "quality_score": self._calculate_quality_score(rms, peak, duration)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing audio file {audio_path}: {e}")
            return {"error": str(e), "category": "medium", "recommended_timeout": 180}
    
    def _get_duration_category(self, duration: float) -> str:
        """Get duration category for timeout configuration."""
        for category, (min_dur, max_dur) in self.timeout_config.items():
            if min_dur <= duration < max_dur:
                return category
        return "very_long"
    
    def _calculate_quality_score(self, rms: float, peak: float, duration: float) -> float:
        """Calculate audio quality score (0-1, higher is better)."""
        try:
            # Normalize metrics
            signal_strength = min(rms / 0.1, 1.0)  # Good signal around 0.1 RMS
            dynamic_range = min(peak / rms, 10.0) / 10.0 if rms > 0 else 0
            duration_score = 1.0 if duration < 300 else max(0.5, 300/duration)
            
            # Weighted combination
            quality = (signal_strength * 0.4 + dynamic_range * 0.3 + duration_score * 0.3)
            return min(max(quality, 0.0), 1.0)
            
        except Exception:
            return 0.5  # Default medium quality
    
    def get_optimal_backend_order(self, audio_analysis: Dict[str, Any]) -> List[str]:
        """Get optimal backend order based on audio characteristics and historical performance."""
        
        available_backends = []
        try:
            available_backends = get_available_backends()
        except:
            available_backends = ["MLXWhisper", "FasterWhisper", "StandardOpenAIWhisper"]
        
        # Filter to available backends and add success rate weighting
        weighted_backends = []
        
        for backend in self.backend_priority:
            if backend in available_backends:
                # Get historical success rate
                success_rate = self.success_rates.get(backend, 0.8)  # Default 80%
                failure_count = self.failure_counts.get(backend, 0)
                
                # Quality-based adjustments
                quality_score = audio_analysis.get("quality_score", 0.5)
                duration = audio_analysis.get("duration", 60)
                
                # MLXWhisper is best for short, high-quality audio
                if backend == "MLXWhisper":
                    if quality_score > 0.7 and duration < 120:
                        success_rate += 0.1
                    elif duration > 300:
                        success_rate -= 0.2
                
                # FasterWhisper is good for medium length
                elif backend == "FasterWhisper":
                    if 30 < duration < 300:
                        success_rate += 0.1
                
                # OpenAI API is most reliable for difficult audio
                elif backend == "OpenAIAPI":
                    if quality_score < 0.5 or duration > 300:
                        success_rate += 0.2
                
                # Penalize backends with recent failures
                if failure_count > 3:
                    success_rate -= min(0.3, failure_count * 0.05)
                
                weighted_backends.append((backend, success_rate))
        
        # Sort by success rate (descending)
        weighted_backends.sort(key=lambda x: x[1], reverse=True)
        
        return [backend for backend, _ in weighted_backends]
    
    def preprocess_audio(self, audio_path: Path) -> Optional[Path]:
        """Preprocess audio to improve transcription success rate."""
        try:
            analysis = self.analyze_audio_file(audio_path)
            
            # Only preprocess if quality is poor or format is suboptimal
            if (analysis.get("quality_score", 1.0) > 0.7 and 
                analysis.get("samplerate") == 16000 and 
                analysis.get("channels") == 1):
                return audio_path  # No preprocessing needed
            
            # Create preprocessed version
            processed_path = audio_path.parent / f"processed_{audio_path.name}"
            
            with sf.SoundFile(audio_path) as f:
                data = f.read()
                original_sr = f.samplerate
            
            # Convert to mono if needed
            if len(data.shape) > 1:
                data = np.mean(data, axis=1)
            
            # Resample to 16kHz if needed
            if original_sr != 16000:
                # Simple resampling (for production, use proper resampling)
                target_length = int(len(data) * 16000 / original_sr)
                data = np.interp(np.linspace(0, len(data), target_length), 
                               np.arange(len(data)), data)
            
            # Normalize audio level
            if np.max(np.abs(data)) > 0:
                data = data / np.max(np.abs(data)) * 0.95
            
            # Save preprocessed audio
            sf.write(processed_path, data, 16000)
            
            logger.info(f"Audio preprocessed: {audio_path} -> {processed_path}")
            return processed_path
            
        except Exception as e:
            logger.error(f"Error preprocessing audio: {e}")
            return audio_path  # Return original on error
    
    def robust_transcribe(
        self, 
        audio_path: Path, 
        progress_callback: Optional[Callable[[str, float], None]] = None,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """Perform robust transcription with automatic retries and backend fallbacks."""
        
        # Analyze audio
        audio_analysis = self.analyze_audio_file(audio_path)
        optimal_backends = self.get_optimal_backend_order(audio_analysis)
        
        # Preprocess if needed
        processed_path = self.preprocess_audio(audio_path)
        
        result = {
            "success": False,
            "transcript": "",
            "backend_used": None,
            "attempts": [],
            "audio_analysis": audio_analysis,
            "preprocessing_applied": processed_path != audio_path
        }
        
        if progress_callback:
            progress_callback("Starting robust transcription...", 0.0)
        
        # Try each backend in order
        for i, backend in enumerate(optimal_backends):
            if progress_callback:
                progress = (i / len(optimal_backends)) * 0.9
                progress_callback(f"Trying {backend}...", progress)
            
            for attempt in range(max_retries):
                attempt_result = self._attempt_transcription(
                    processed_path, backend, audio_analysis, attempt + 1
                )
                
                result["attempts"].append(attempt_result)
                
                if attempt_result["success"]:
                    result.update({
                        "success": True,
                        "transcript": attempt_result["transcript"],
                        "backend_used": backend,
                        "transcription_time": attempt_result["transcription_time"],
                        "total_attempts": len(result["attempts"])
                    })
                    
                    # Update success tracking
                    self._update_success_tracking(backend, True)
                    
                    if progress_callback:
                        progress_callback("Transcription completed successfully!", 1.0)
                    
                    self.save_stability_log()
                    return result
                
                # Brief pause between attempts
                time.sleep(min(2.0 ** attempt, 10.0))  # Exponential backoff
            
            # Update failure tracking for this backend
            self._update_success_tracking(backend, False)
        
        # All backends failed
        if progress_callback:
            progress_callback("All transcription attempts failed", 1.0)
        
        self.save_stability_log()
        return result
    
    def _attempt_transcription(
        self, 
        audio_path: Path, 
        backend: str, 
        audio_analysis: Dict[str, Any], 
        attempt_num: int
    ) -> Dict[str, Any]:
        """Attempt transcription with a specific backend."""
        
        start_time = time.time()
        timeout = audio_analysis.get("recommended_timeout", 180)
        
        # Adjust timeout for attempt number
        attempt_timeout = timeout * (1.0 + 0.5 * (attempt_num - 1))
        
        result = {
            "backend": backend,
            "attempt": attempt_num,
            "success": False,
            "transcript": "",
            "error": None,
            "transcription_time": 0,
            "timeout_used": attempt_timeout
        }
        
        try:
            logger.info(f"Attempting transcription: {backend}, attempt {attempt_num}, timeout {attempt_timeout}s")
            
            # Use ThreadPoolExecutor with timeout
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(transcribe_audio, str(audio_path), backend, "small")
                
                try:
                    transcript = future.result(timeout=attempt_timeout)
                    end_time = time.time()
                    
                    result.update({
                        "success": True,
                        "transcript": transcript,
                        "transcription_time": end_time - start_time
                    })
                    
                    logger.info(f"✅ Success: {backend} in {end_time - start_time:.2f}s")
                    
                except TimeoutError:
                    end_time = time.time()
                    result.update({
                        "error": f"Timeout after {attempt_timeout}s",
                        "transcription_time": end_time - start_time
                    })
                    logger.warning(f"⏰ Timeout: {backend} after {attempt_timeout}s")
                    
                    # Cancel the future
                    future.cancel()
                    
        except Exception as e:
            end_time = time.time()
            result.update({
                "error": str(e),
                "transcription_time": end_time - start_time
            })
            logger.error(f"❌ Error: {backend} - {e}")
        
        return result
    
    def _update_success_tracking(self, backend: str, success: bool) -> None:
        """Update success rate tracking for a backend."""
        
        # Update failure counts
        if not success:
            self.failure_counts[backend] = self.failure_counts.get(backend, 0) + 1
        else:
            # Reset failure count on success
            self.failure_counts[backend] = 0
        
        # Update success rates (exponential moving average)
        current_rate = self.success_rates.get(backend, 0.8)
        alpha = 0.1  # Learning rate
        
        new_rate = current_rate * (1 - alpha) + (1.0 if success else 0.0) * alpha
        self.success_rates[backend] = new_rate
    
    def get_stability_report(self) -> str:
        """Generate stability analysis report."""
        
        report_lines = [
            "# ZorOS Dictation Stability Report",
            f"Generated: {datetime.now().isoformat()}",
            "",
            "## Backend Performance",
            ""
        ]
        
        if self.success_rates:
            report_lines.extend([
                "| Backend | Success Rate | Recent Failures |",
                "|---------|--------------|-----------------|"
            ])
            
            for backend in self.backend_priority:
                success_rate = self.success_rates.get(backend, 0.8)
                failure_count = self.failure_counts.get(backend, 0)
                
                report_lines.append(
                    f"| {backend} | {success_rate:.1%} | {failure_count} |"
                )
        
        report_lines.extend([
            "",
            "## Recommendations",
            ""
        ])
        
        # Add recommendations based on data
        if self.success_rates:
            best_backend = max(self.success_rates.items(), key=lambda x: x[1])
            worst_backend = min(self.success_rates.items(), key=lambda x: x[1])
            
            report_lines.extend([
                f"- **Best performing backend**: {best_backend[0]} ({best_backend[1]:.1%} success)",
                f"- **Needs attention**: {worst_backend[0]} ({worst_backend[1]:.1%} success)"
            ])
            
            # High failure rate warnings
            problematic_backends = [
                backend for backend, failures in self.failure_counts.items() 
                if failures > 5
            ]
            
            if problematic_backends:
                report_lines.extend([
                    f"- **High failure rate**: {', '.join(problematic_backends)}"
                ])
        
        return "\n".join(report_lines)


def create_stability_manager() -> DictationStabilityManager:
    """Create and return a global stability manager instance."""
    return DictationStabilityManager()


# Global instance for easy access
_stability_manager = None

def get_stability_manager() -> DictationStabilityManager:
    """Get or create global stability manager."""
    global _stability_manager
    if _stability_manager is None:
        _stability_manager = DictationStabilityManager()
    return _stability_manager


if __name__ == "__main__":
    # Demo/test functionality
    manager = DictationStabilityManager()
    report = manager.get_stability_report()
    print(report)