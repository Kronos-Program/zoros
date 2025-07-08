"""
Standalone transcription function for performance testing.

This module provides transcription capabilities without UI dependencies,
making it suitable for performance testing and analysis.

Spec: docs/requirements/dictation_requirements.md#transcription-requirements
Tests: tests/test_transcription_performance.py#test_transcription_backend_performance
Integration: source/dictation_backends/ for backend implementations
"""
import time
from pathlib import Path
from typing import Dict, Any, Optional
from zoros.logger import get_logger

# Configure logging via unified logger
logger = get_logger(__name__)


def transcribe_audio_standalone(wav_path: str, backend: str = "StandardWhisper", model: str = "small") -> str:
    """Transcribe audio file using specified backend and model.
    
    This function provides transcription capabilities using various Whisper backends
    without UI dependencies. It includes detailed timing measurements for performance analysis.
    
    Args:
        wav_path: Path to the audio file to transcribe
        backend: Whisper backend to use (MLXWhisper, FasterWhisper, etc.)
        model: Model size/type to use (small, medium, large, large-v3-turbo)
        
    Returns:
        Transcribed text as string
        
    Spec: docs/requirements/dictation_requirements.md#transcription-requirements
    Tests: tests/test_transcription_performance.py#test_transcription_backend_performance
    Integration: source/dictation_backends/ for backend implementations
    """
    # Initialize timing measurements
    timing_data = {
        'total_start': time.time(),
        'audio_validation': 0,
        'backend_initialization': 0,
        'model_loading': 0,
        'transcription_core': 0,
        'result_processing': 0,
        'total_end': 0
    }
    
    # Step 1: Audio file validation
    validation_start = time.time()
    audio_path = Path(wav_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {wav_path}")
    
    # Get audio file info for analysis
    audio_size = audio_path.stat().st_size
    timing_data['audio_validation'] = time.time() - validation_start
    
    print(f"DEBUG: Attempting transcription with backend: {backend}, model: {model}")
    print(f"DEBUG: Audio file path: {wav_path}")
    print(f"DEBUG: Audio file size: {audio_size / 1024:.1f} KB")
    
    result = ""
    
    try:
        # Step 2: Backend initialization
        init_start = time.time()
        
        if backend == "MLXWhisper":
            print("DEBUG: Trying MLXWhisper backend...")
            from .mlx_whisper_backend import MLXWhisperBackend
            backend_instance = MLXWhisperBackend(model)
            timing_data['backend_initialization'] = time.time() - init_start
            
            # Step 3: Model loading (for MLXWhisper, this happens during first transcription)
            model_start = time.time()
            result = backend_instance.transcribe(wav_path)
            model_time = time.time() - model_start
            
            # For MLXWhisper, we can't easily separate model loading from transcription
            # So we'll estimate based on typical model loading times
            if "large-v3-turbo" in model:
                estimated_model_load = 2.0  # seconds for large model
                timing_data['model_loading'] = estimated_model_load
                timing_data['transcription_core'] = model_time - estimated_model_load
            else:
                estimated_model_load = 0.5  # seconds for smaller models
                timing_data['model_loading'] = estimated_model_load
                timing_data['transcription_core'] = model_time - estimated_model_load
            
            print(f"DEBUG: MLXWhisper result: {result[:100]}...")
            
        elif backend == "FasterWhisper":
            print("DEBUG: Trying FasterWhisper backend...")
            from faster_whisper import WhisperModel  # type: ignore
            
            model_start = time.time()
            wm = WhisperModel(model)
            timing_data['model_loading'] = time.time() - model_start
            timing_data['backend_initialization'] = time.time() - init_start
            
            transcribe_start = time.time()
            segments, _ = wm.transcribe(wav_path)
            result = " ".join(seg.text for seg in segments).strip()
            timing_data['transcription_core'] = time.time() - transcribe_start
            
            print(f"DEBUG: FasterWhisper result: {result[:100]}...")
            
        elif backend == "WhisperCPP":
            print("DEBUG: Trying WhisperCPP backend...")
            from .whisper_cpp_backend import WhisperCPPBackend
            backend_instance = WhisperCPPBackend(model)
            timing_data['backend_initialization'] = time.time() - init_start
            
            transcribe_start = time.time()
            result = backend_instance.transcribe(wav_path)
            timing_data['transcription_core'] = time.time() - transcribe_start
            
            print(f"DEBUG: WhisperCPP result: {result[:100]}...")
            
        elif backend == "StandardWhisper":
            print("DEBUG: Trying StandardWhisper backend...")
            import whisper  # type: ignore
            
            model_start = time.time()
            wmodel = whisper.load_model(model)
            timing_data['model_loading'] = time.time() - model_start
            timing_data['backend_initialization'] = time.time() - init_start
            
            transcribe_start = time.time()
            result = wmodel.transcribe(wav_path)
            text_result = result.get("text", "").strip()
            timing_data['transcription_core'] = time.time() - transcribe_start
            
            print(f"DEBUG: StandardWhisper result: {text_result[:100]}...")
            result = text_result
            
        else:
            raise ValueError(f"Unknown backend: {backend}")
            
    except Exception as e:
        print(f"DEBUG: {backend} failed with error: {e}")
        import traceback
        traceback.print_exc()
        result = ""
    
    # Step 4: Result processing
    processing_start = time.time()
    if result:
        result = result.strip()
    timing_data['result_processing'] = time.time() - processing_start
    timing_data['total_end'] = time.time()
    
    # Calculate total time and percentages
    total_time = timing_data['total_end'] - timing_data['total_start']
    
    # Get audio duration for ratio calculation
    try:
        import soundfile as sf
        audio_info = sf.info(wav_path)
        audio_duration = audio_info.duration
        wav_to_transcription_ratio = audio_duration / total_time if total_time > 0 else 0
    except Exception:
        audio_duration = None
        wav_to_transcription_ratio = None
    
    # Print detailed timing analysis
    print(f"\n=== TRANSCRIPTION PIPELINE TIMING ANALYSIS ===")
    print(f"Audio file: {audio_path.name}")
    print(f"Audio size: {audio_size / 1024:.1f} KB")
    if audio_duration:
        print(f"Audio duration: {audio_duration:.2f}s")
        print(f"WAV time to transcription time ratio: {wav_to_transcription_ratio:.2f}x")
    print(f"Backend: {backend}")
    print(f"Model: {model}")
    print(f"Total time: {total_time:.3f}s")
    print(f"\nComponent breakdown:")
    print(f"  Audio validation: {timing_data['audio_validation']:.3f}s ({timing_data['audio_validation']/total_time*100:.1f}%)")
    print(f"  Backend initialization: {timing_data['backend_initialization']:.3f}s ({timing_data['backend_initialization']/total_time*100:.1f}%)")
    print(f"  Model loading: {timing_data['model_loading']:.3f}s ({timing_data['model_loading']/total_time*100:.1f}%)")
    print(f"  Transcription core: {timing_data['transcription_core']:.3f}s ({timing_data['transcription_core']/total_time*100:.1f}%)")
    print(f"  Result processing: {timing_data['result_processing']:.3f}s ({timing_data['result_processing']/total_time*100:.1f}%)")
    print(f"  Transcription efficiency: {len(result.split()) / total_time:.1f} words/second")
    
    # Save timing data for analysis
    timing_report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'audio_file': str(audio_path),
        'audio_size_kb': audio_size / 1024,
        'audio_duration': audio_duration,
        'backend': backend,
        'model': model,
        'wav_to_transcription_ratio': wav_to_transcription_ratio,
        'total_time': total_time,
        'timing_breakdown': timing_data,
        'result_length': len(result),
        'words_per_second': len(result.split()) / total_time if total_time > 0 else 0,
        'transcript_preview': result[:200] + "..." if len(result) > 200 else result
    }
    
    # Save to artifacts directory
    artifacts_dir = Path("artifacts")
    artifacts_dir.mkdir(exist_ok=True)
    
    timing_file = artifacts_dir / f"transcription_timing_{backend}_{model}_{int(time.time())}.json"
    with open(timing_file, 'w') as f:
        import json
        json.dump(timing_report, f, indent=2)
    
    print(f"Detailed timing report saved to: {timing_file}")
    print("=" * 50)
    
    return result 