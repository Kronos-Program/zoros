"""
Dictation Recovery and Performance Analysis Tool

This module provides comprehensive recovery capabilities for failed dictations
and performance analysis to improve the ZorOS dictation system.

Key Features:
- Automatic detection and recovery of lost audio files
- Performance benchmarking across backends
- Streamlit interface for batch reprocessing
- Recovery statistics and recommendations

Author: ZorOS Development Team
Date: 2025-01-05
"""

import json
import sys
import time
import glob
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import logging
import tempfile
import asyncio

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False

try:
    from source.interfaces.dictation_stability import get_stability_manager
    from source.interfaces.enhanced_fiberization import get_enhanced_fiberizer, FiberizationRequest, FiberizationLevel
    import soundfile as sf
    import numpy as np
    AUDIO_DEPS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Some dependencies not available: {e}")
    AUDIO_DEPS_AVAILABLE = False

# Avoid circular imports by importing transcription function differently
def transcribe_audio_safe(audio_path: str, backend: str, model: str = "small"):
    """Safe transcription that avoids circular imports."""
    try:
        from source.dictation_backends import get_available_backends
        
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


class DictationRecoveryManager:
    """Manages recovery and reprocessing of failed dictations."""
    
    def __init__(self):
        self.recovery_dir = Path.home() / ".zoros" / "recovery"
        self.recovery_log_path = self.recovery_dir / "recovery_log.json"
        self.performance_log_path = self.recovery_dir / "performance_log.json"
        self.recovery_dir.mkdir(parents=True, exist_ok=True)
        
        # Common temp directories to search
        self.temp_dirs = [
            Path("/var/folders"),  # macOS temp
            Path("/tmp"),          # Unix temp
            Path.home() / "Downloads",  # Common location
        ]
        
        # Initialize performance tracking
        self.performance_data = []
        self.load_performance_log()
    
    def load_recovery_log(self) -> List[Dict]:
        """Load the recovery log of failed transcriptions."""
        if not self.recovery_log_path.exists():
            return []
        
        try:
            with open(self.recovery_log_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading recovery log: {e}")
            return []
    
    def load_performance_log(self) -> None:
        """Load existing performance data."""
        if self.performance_log_path.exists():
            try:
                with open(self.performance_log_path, 'r') as f:
                    self.performance_data = json.load(f)
            except Exception as e:
                logger.warning(f"Error loading performance log: {e}")
                self.performance_data = []
    
    def save_performance_log(self) -> None:
        """Save performance data to log."""
        try:
            with open(self.performance_log_path, 'w') as f:
                json.dump(self.performance_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving performance log: {e}")
    
    def get_available_audio_files(self) -> List[Path]:
        """Get all available audio files for recovery."""
        audio_files = []
        
        # Get files from recovery directory
        audio_extensions = ['.wav', '.mp3', '.m4a', '.flac']
        for ext in audio_extensions:
            audio_files.extend(self.recovery_dir.glob(f"*{ext}"))
        
        # Also check standard audio intake directory
        intake_audio_dir = Path("audio/intake")
        if intake_audio_dir.exists():
            for ext in audio_extensions:
                audio_files.extend(intake_audio_dir.glob(f"*{ext}"))
        
        return sorted(audio_files, key=lambda x: x.stat().st_mtime, reverse=True)
    
    def find_lost_audio_files(self, hours_back: int = 24) -> List[Path]:
        """Find potentially lost audio files in temp directories."""
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        lost_files = []
        
        # Common temp file patterns for ZorOS
        patterns = [
            "**/tmp_*.wav",
            "**/temp_*.wav", 
            "**/zoros_*.wav",
            "**/intake_*.wav",
            "**/recording_*.wav"
        ]
        
        for temp_dir in self.temp_dirs:
            if not temp_dir.exists():
                continue
                
            for pattern in patterns:
                try:
                    for file_path in temp_dir.glob(pattern):
                        if not file_path.is_file():
                            continue
                            
                        # Check modification time
                        mod_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                        if mod_time >= cutoff_time:
                            # Quick audio validation
                            if self._is_valid_audio_file(file_path):
                                lost_files.append(file_path)
                                
                except Exception as e:
                    logger.warning(f"Error searching {temp_dir}: {e}")
        
        return sorted(lost_files, key=lambda f: f.stat().st_mtime, reverse=True)
    
    def _is_valid_audio_file(self, file_path: Path) -> bool:
        """Quick validation that file is a valid audio file."""
        if not AUDIO_DEPS_AVAILABLE:
            return file_path.suffix.lower() in ['.wav', '.mp3', '.m4a', '.flac']
        
        try:
            with sf.SoundFile(file_path) as f:
                return f.frames > 0 and f.samplerate > 0
        except Exception:
            return False
    
    def recover_audio_file(self, audio_path: Path, save_to_recovery: bool = True) -> Dict[str, Any]:
        """Recover a single audio file with transcription and analysis."""
        recovery_start = time.time()
        
        result = {
            "audio_path": str(audio_path),
            "recovery_time": datetime.now().isoformat(),
            "success": False,
            "transcript": "",
            "analysis": {},
            "recovery_location": None,
            "error": None
        }
        
        try:
            # Analyze the audio file
            audio_analysis = self.analyze_audio_file(audio_path)
            result["analysis"] = audio_analysis
            
            logger.info(f"Recovering audio: {audio_path}")
            logger.info(f"Duration: {audio_analysis.get('duration', 'unknown')}s")
            logger.info(f"File size: {audio_analysis.get('file_size_mb', 'unknown'):.1f}MB")
            
            # Copy to recovery directory if requested
            if save_to_recovery:
                recovery_filename = f"recovered_{int(time.time())}_{audio_path.name}"
                recovery_path = self.recovery_dir / recovery_filename
                recovery_path.write_bytes(audio_path.read_bytes())
                result["recovery_location"] = str(recovery_path)
                logger.info(f"Saved to recovery: {recovery_path}")
            
            # Attempt transcription with stability manager if available
            if get_stability_manager:
                try:
                    stability_manager = get_stability_manager()
                    transcription_result = stability_manager.robust_transcribe(
                        audio_path,
                        progress_callback=lambda msg, prog: logger.info(f"Recovery progress: {msg} ({prog:.1%})"),
                        max_retries=2
                    )
                    
                    if transcription_result["success"]:
                        result.update({
                            "success": True,
                            "transcript": transcription_result["transcript"],
                            "backend_used": transcription_result["backend_used"],
                            "total_attempts": transcription_result["total_attempts"],
                            "processing_time": transcription_result.get("transcription_time", 0)
                        })
                        logger.info("✅ Recovery successful!")
                        
                    else:
                        result["error"] = "All transcription attempts failed"
                        logger.error("❌ Recovery failed - no successful transcription")
                        
                except Exception as e:
                    # Fall back to simple transcription
                    logger.warning(f"Stability manager failed, trying simple transcription: {e}")
                    self._simple_transcription_recovery(audio_path, result)
            else:
                # Use simple transcription
                self._simple_transcription_recovery(audio_path, result)
                
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"❌ Recovery error: {e}")
        
        # Record performance data
        result["total_recovery_time"] = time.time() - recovery_start
        self.performance_data.append(result)
        self.save_performance_log()
        
        return result
    
    def _simple_transcription_recovery(self, audio_path: Path, result: Dict[str, Any]) -> None:
        """Simple transcription recovery fallback."""
        backends_to_try = ["MLXWhisper", "FasterWhisper", "StandardOpenAIWhisper"]
        
        for backend in backends_to_try:
            try:
                logger.info(f"Trying {backend} for recovery...")
                transcript = transcribe_audio_safe(str(audio_path), backend, "small")
                
                result.update({
                    "success": True,
                    "transcript": transcript,
                    "backend_used": backend,
                    "processing_time": 0  # Not tracked in simple mode
                })
                logger.info(f"✅ Recovery successful with {backend}!")
                return
                
            except Exception as e:
                logger.warning(f"❌ {backend} failed: {e}")
                continue
        
        result["error"] = "All recovery attempts failed"
    
    def analyze_audio_file(self, audio_path: Path) -> Dict[str, Any]:
        """Analyze audio file properties."""
        if not AUDIO_DEPS_AVAILABLE:
            file_size = audio_path.stat().st_size
            return {
                "file_size": file_size,
                "file_size_mb": file_size / (1024 * 1024),
                "error": "Audio analysis dependencies not available"
            }
        
        try:
            with sf.SoundFile(audio_path) as f:
                duration = len(f) / f.samplerate
                channels = f.channels
                samplerate = f.samplerate
                
            file_size = audio_path.stat().st_size
            
            return {
                "duration": duration,
                "channels": channels,
                "samplerate": samplerate,
                "file_size": file_size,
                "file_size_mb": file_size / (1024 * 1024)
            }
        except Exception as e:
            logger.error(f"Error analyzing audio file {audio_path}: {e}")
            return {"error": str(e)}
    
    def transcribe_with_performance_tracking(
        self, 
        audio_path: Path, 
        backend: str, 
        model: str = "small"
    ) -> Dict[str, Any]:
        """Transcribe audio with comprehensive performance tracking."""
        
        monitor = ResourceMonitor()
        audio_analysis = self.analyze_audio_file(audio_path)
        
        result = {
            "audio_path": str(audio_path),
            "backend": backend,
            "model": model,
            "timestamp": datetime.now().isoformat(),
            "audio_analysis": audio_analysis,
            "success": False,
            "transcript": "",
            "performance": {}
        }
        
        print(f"Starting transcription: {audio_path.name} with {backend}/{model}")
        
        try:
            with monitor.monitor_operation(f"transcribe_{backend}_{model}"):
                start_time = time.time()
                
                # Perform transcription
                transcript = transcribe_audio_safe(str(audio_path), backend, model)
                
                end_time = time.time()
                transcription_time = end_time - start_time
                
                # Calculate performance metrics
                duration = audio_analysis.get("duration", 0)
                realtime_factor = transcription_time / duration if duration > 0 else float('inf')
                words_per_second = len(transcript.split()) / transcription_time if transcription_time > 0 else 0
                
                result.update({
                    "success": True,
                    "transcript": transcript,
                    "performance": {
                        "transcription_time": transcription_time,
                        "audio_duration": duration,
                        "realtime_factor": realtime_factor,
                        "words_per_second": words_per_second,
                        "transcript_length": len(transcript),
                        "word_count": len(transcript.split())
                    }
                })
                
                print(f"✅ Success: {transcription_time:.2f}s ({realtime_factor:.2f}x realtime)")
                
        except Exception as e:
            result["error"] = str(e)
            result["performance"]["failed"] = True
            print(f"❌ Failed: {e}")
            logger.error(f"Transcription failed: {e}")
        
        # Store performance data
        self.performance_data.append(result)
        self.save_performance_log()
        
        return result
    
    def batch_transcribe_with_backends(
        self, 
        audio_path: Path, 
        backends: List[str],
        models: List[str] = ["small"]
    ) -> List[Dict[str, Any]]:
        """Transcribe audio file with multiple backends for comparison."""
        
        results = []
        
        print(f"\n🔄 Batch transcribing: {audio_path.name}")
        print(f"Backends: {backends}")
        print(f"Models: {models}")
        
        for backend in backends:
            for model in models:
                print(f"\n--- Testing {backend} with {model} ---")
                
                try:
                    result = self.transcribe_with_performance_tracking(
                        audio_path, backend, model
                    )
                    results.append(result)
                    
                    # Brief pause between transcriptions
                    time.sleep(1.0)
                    
                except Exception as e:
                    print(f"❌ Error with {backend}/{model}: {e}")
                    results.append({
                        "backend": backend,
                        "model": model,
                        "success": False,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    })
        
        return results
    
    def generate_performance_report(self) -> str:
        """Generate comprehensive performance analysis report."""
        
        if not self.performance_data:
            return "No performance data available."
        
        # Analyze performance by backend
        backend_stats = {}
        model_stats = {}
        
        successful_runs = [r for r in self.performance_data if r.get("success")]
        
        for run in successful_runs:
            backend = run["backend"]
            model = run["model"]
            perf = run["performance"]
            
            # Backend statistics
            if backend not in backend_stats:
                backend_stats[backend] = {
                    "runs": 0,
                    "total_time": 0,
                    "total_realtime_factor": 0,
                    "total_words_per_sec": 0
                }
            
            backend_stats[backend]["runs"] += 1
            backend_stats[backend]["total_time"] += perf.get("transcription_time", 0)
            backend_stats[backend]["total_realtime_factor"] += perf.get("realtime_factor", 0)
            backend_stats[backend]["total_words_per_sec"] += perf.get("words_per_second", 0)
        
        # Generate report
        report_lines = [
            "# ZorOS Dictation Performance Report",
            f"Generated: {datetime.now().isoformat()}",
            f"Total runs: {len(self.performance_data)}",
            f"Successful runs: {len(successful_runs)}",
            f"Success rate: {len(successful_runs)/len(self.performance_data)*100:.1f}%",
            "",
            "## Backend Performance Comparison",
            ""
        ]
        
        # Backend comparison table
        if backend_stats:
            report_lines.extend([
                "| Backend | Runs | Avg Time | Avg Realtime Factor | Avg Words/Sec |",
                "|---------|------|----------|-------------------|---------------|"
            ])
            
            for backend, stats in backend_stats.items():
                avg_time = stats["total_time"] / stats["runs"]
                avg_rtf = stats["total_realtime_factor"] / stats["runs"]
                avg_wps = stats["total_words_per_sec"] / stats["runs"]
                
                report_lines.append(
                    f"| {backend} | {stats['runs']} | {avg_time:.2f}s | {avg_rtf:.2f}x | {avg_wps:.1f} |"
                )
        
        # Recent failures
        failed_runs = [r for r in self.performance_data if not r.get("success")]
        if failed_runs:
            report_lines.extend([
                "",
                "## Recent Failures",
                ""
            ])
            
            for failure in failed_runs[-5:]:  # Last 5 failures
                timestamp = failure.get("timestamp", "unknown")
                backend = failure.get("backend", "unknown")
                error = failure.get("error", "unknown error")
                report_lines.append(f"- {timestamp}: {backend} - {error}")
        
        return "\n".join(report_lines)


def streamlit_recovery_interface():
    """Streamlit interface for dictation recovery."""
    
    if not STREAMLIT_AVAILABLE:
        st.error("Streamlit dependencies not available")
        return
    
    st.title("🔧 ZorOS Dictation Recovery")
    st.markdown("Recover and reprocess failed dictations with performance analysis")
    
    recovery_manager = DictationRecoveryManager()
    
    # Sidebar for options
    st.sidebar.header("Recovery Options")
    
    mode = st.sidebar.selectbox(
        "Recovery Mode",
        ["View Recovery Log", "Batch Reprocess", "Performance Analysis", "Manual Recovery"]
    )
    
    if mode == "View Recovery Log":
        st.header("Recovery Log")
        
        recovery_log = recovery_manager.load_recovery_log()
        
        if not recovery_log:
            st.info("No recovery entries found")
        else:
            for i, entry in enumerate(recovery_log):
                with st.expander(f"Recovery {i+1}: {entry.get('timestamp', 'Unknown')}"):
                    st.json(entry)
    
    elif mode == "Batch Reprocess":
        st.header("Batch Reprocessing")
        
        # Get available audio files
        audio_files = recovery_manager.get_available_audio_files()
        
        if not audio_files:
            st.warning("No audio files found for recovery")
            return
        
        # File selection
        selected_file = st.selectbox(
            "Select Audio File",
            audio_files,
            format_func=lambda x: f"{x.name} ({x.stat().st_size / (1024*1024):.1f} MB)"
        )
        
        # Backend selection
        try:
            available_backends = get_available_backends()
        except:
            available_backends = ["MLXWhisper", "FasterWhisper", "StandardOpenAIWhisper"]
        
        selected_backends = st.multiselect(
            "Select Backends",
            available_backends,
            default=available_backends[:2] if len(available_backends) >= 2 else available_backends
        )
        
        selected_models = st.multiselect(
            "Select Models",
            ["small", "medium", "large", "large-v3-turbo"],
            default=["small"]
        )
        
        if st.button("Start Batch Processing"):
            if selected_file and selected_backends:
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                total_combinations = len(selected_backends) * len(selected_models)
                
                results = []
                for i, backend in enumerate(selected_backends):
                    for j, model in enumerate(selected_models):
                        current = i * len(selected_models) + j + 1
                        
                        status_text.text(f"Processing {backend}/{model} ({current}/{total_combinations})")
                        progress_bar.progress(current / total_combinations)
                        
                        result = recovery_manager.transcribe_with_performance_tracking(
                            selected_file, backend, model
                        )
                        results.append(result)
                
                status_text.text("Processing complete!")
                
                # Display results
                st.subheader("Results")
                
                for result in results:
                    backend = result["backend"]
                    model = result["model"]
                    success = result.get("success", False)
                    
                    if success:
                        perf = result["performance"]
                        st.success(f"✅ {backend}/{model}: {perf['transcription_time']:.2f}s ({perf['realtime_factor']:.2f}x)")
                        
                        with st.expander(f"Transcript - {backend}/{model}"):
                            st.text(result["transcript"])
                    else:
                        error = result.get("error", "Unknown error")
                        st.error(f"❌ {backend}/{model}: {error}")
            else:
                st.error("Please select a file and at least one backend")
    
    elif mode == "Performance Analysis":
        st.header("Performance Analysis")
        
        report = recovery_manager.generate_performance_report()
        st.markdown(report)
        
        # Performance data download
        if recovery_manager.performance_data:
            performance_json = json.dumps(recovery_manager.performance_data, indent=2)
            st.download_button(
                "Download Performance Data",
                performance_json,
                file_name=f"performance_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
    
    elif mode == "Manual Recovery":
        st.header("Manual Recovery")
        
        # File upload
        uploaded_file = st.file_uploader(
            "Upload Audio File",
            type=['wav', 'mp3', 'm4a', 'flac']
        )
        
        if uploaded_file:
            # Save uploaded file temporarily
            temp_path = Path(f"/tmp/{uploaded_file.name}")
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # Analysis
            analysis = recovery_manager.analyze_audio_file(temp_path)
            st.subheader("Audio Analysis")
            st.json(analysis)
            
            # Backend selection
            backend = st.selectbox("Backend", ["MLXWhisper", "FasterWhisper", "StandardOpenAIWhisper"])
            model = st.selectbox("Model", ["small", "medium", "large", "large-v3-turbo"])
            
            if st.button("Transcribe"):
                with st.spinner("Transcribing..."):
                    result = recovery_manager.transcribe_with_performance_tracking(
                        temp_path, backend, model
                    )
                
                if result["success"]:
                    st.success("Transcription successful!")
                    st.text_area("Transcript", result["transcript"], height=200)
                    
                    perf = result["performance"]
                    st.metric("Transcription Time", f"{perf['transcription_time']:.2f}s")
                    st.metric("Realtime Factor", f"{perf['realtime_factor']:.2f}x")
                    st.metric("Words per Second", f"{perf['words_per_second']:.1f}")
                else:
                    st.error(f"Transcription failed: {result.get('error', 'Unknown error')}")
            
            # Cleanup
            if temp_path.exists():
                temp_path.unlink()


def main():
    """Main entry point for dictation recovery."""
    if len(sys.argv) > 1 and sys.argv[1] == "--streamlit":
        # Run Streamlit interface
        streamlit_recovery_interface()
    else:
        # Command line interface
        recovery_manager = DictationRecoveryManager()
        
        print("🔧 ZorOS Dictation Recovery Tool")
        print("=" * 40)
        
        # Show recovery log
        recovery_log = recovery_manager.load_recovery_log()
        print(f"Recovery entries: {len(recovery_log)}")
        
        # Show available audio files
        audio_files = recovery_manager.get_available_audio_files()
        print(f"Available audio files: {len(audio_files)}")
        
        # Generate performance report
        report = recovery_manager.generate_performance_report()
        print("\n" + report)


if __name__ == "__main__":
    main()