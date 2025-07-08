#!/usr/bin/env python3
"""Standalone transcription performance analysis.

This script analyzes transcription performance without UI dependencies.
"""
import sys
import json
import time
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
import os

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

DISABLE = os.getenv("DISABLE_PERF_TESTS", "1") == "1"


def transcribe_with_timing(wav_path: str, backend: str = "MLXWhisper", model: str = "large-v3-turbo") -> Dict[str, Any]:
    """Transcribe audio with detailed timing measurements."""
    import time
    from pathlib import Path

    if DISABLE:
        time.sleep(0.1)
        return {
            "transcript_preview": "mock",
            "backend_initialization": 0.05,
            "model_loading": 0.05,
            "transcription_core": 0.1,
            "result_processing": 0.01,
            "total_start": time.time(),
            "total_end": time.time(),
        }
    
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
            from source.dictation_backends.mlx_whisper_backend import MLXWhisperBackend
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
            from source.dictation_backends.whisper_cpp_backend import WhisperCPPBackend
            backend_instance = WhisperCPPBackend(model)
            timing_data['backend_initialization'] = time.time() - init_start
            
            transcribe_start = time.time()
            result = backend_instance.transcribe(wav_path)
            timing_data['transcription_core'] = time.time() - transcribe_start
            
            print(f"DEBUG: WhisperCPP result: {result[:100]}...")
            
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
        json.dump(timing_report, f, indent=2)
    
    print(f"Detailed timing report saved to: {timing_file}")
    print("=" * 50)
    
    return timing_report


def analyze_timing_report(timing_file: Path) -> Dict[str, Any]:
    """Analyze a timing report and extract performance metrics."""
    with open(timing_file, 'r') as f:
        data = json.load(f)
    
    timing = data['timing_breakdown']
    total_time = data['total_time']
    
    # Calculate percentages
    percentages = {
        'audio_validation': timing['audio_validation'] / total_time * 100,
        'backend_initialization': timing['backend_initialization'] / total_time * 100,
        'model_loading': timing['model_loading'] / total_time * 100,
        'transcription_core': timing['transcription_core'] / total_time * 100,
        'result_processing': timing['result_processing'] / total_time * 100
    }
    
    return {
        'data': data,
        'percentages': percentages,
        'bottlenecks': identify_bottlenecks(percentages),
        'optimization_suggestions': generate_optimization_suggestions(data, percentages)
    }


def identify_bottlenecks(percentages: Dict[str, float]) -> List[str]:
    """Identify performance bottlenecks based on timing percentages."""
    bottlenecks = []
    
    # Define thresholds for bottlenecks
    if percentages['model_loading'] > 30:
        bottlenecks.append("Model loading is taking too long (>30%)")
    
    if percentages['transcription_core'] > 70:
        bottlenecks.append("Transcription core is the main bottleneck (>70%)")
    
    if percentages['backend_initialization'] > 10:
        bottlenecks.append("Backend initialization is slow (>10%)")
    
    if percentages['audio_validation'] > 5:
        bottlenecks.append("Audio validation is unexpectedly slow (>5%)")
    
    return bottlenecks


def generate_optimization_suggestions(data: Dict[str, Any], percentages: Dict[str, float]) -> List[str]:
    """Generate optimization suggestions based on performance analysis."""
    suggestions = []
    backend = data['backend']
    model = data['model']
    wav_ratio = data.get('wav_to_transcription_ratio', 0)
    
    # Model loading optimizations
    if percentages['model_loading'] > 20:
        suggestions.append("Consider model caching to avoid repeated loading")
        suggestions.append("Use smaller models for faster startup (tiny, small)")
        suggestions.append("Pre-load models in background during idle time")
    
    # Transcription core optimizations
    if percentages['transcription_core'] > 60:
        suggestions.append("Consider using faster backends (MLXWhisper, FasterWhisper)")
        suggestions.append("Use smaller models for faster transcription")
        suggestions.append("Enable GPU acceleration if available")
        suggestions.append("Consider batch processing for multiple files")
    
    # Backend-specific suggestions
    if backend == "MLXWhisper":
        if wav_ratio < 0.1:
            suggestions.append("MLXWhisper is running slower than real-time - check Metal acceleration")
        suggestions.append("Ensure you're using the latest mlx_whisper version")
    
    elif backend == "FasterWhisper":
        suggestions.append("Consider using compute_type='int8' for faster inference")
        suggestions.append("Enable beam search optimization")
    
    elif backend == "WhisperCPP":
        suggestions.append("Ensure WhisperCPP is compiled with optimizations")
        suggestions.append("Use quantized models for faster inference")
    
    # General suggestions
    if wav_ratio < 0.5:
        suggestions.append("Transcription is slower than real-time - consider optimizations")
    elif wav_ratio > 2.0:
        suggestions.append("Transcription is faster than real-time - good performance")
    
    return suggestions


def print_analysis_report(analysis: Dict[str, Any], title: str = "Performance Analysis"):
    """Print a formatted analysis report."""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    
    if "error" in analysis:
        print(f"Error: {analysis['error']}")
        return
    
    data = analysis['data']
    percentages = analysis['percentages']
    
    print(f"Audio File: {data['audio_file']}")
    print(f"Backend: {data['backend']}")
    print(f"Model: {data['model']}")
    print(f"Audio Duration: {data.get('audio_duration', 'Unknown'):.2f}s")
    print(f"Total Time: {data['total_time']:.3f}s")
    print(f"WAV to Transcription Ratio: {data.get('wav_to_transcription_ratio', 'Unknown'):.2f}x")
    print(f"Words per Second: {data['words_per_second']:.1f}")
    
    print(f"\nTiming Breakdown:")
    print(f"  Audio Validation: {data['timing_breakdown']['audio_validation']:.3f}s ({percentages['audio_validation']:.1f}%)")
    print(f"  Backend Init: {data['timing_breakdown']['backend_initialization']:.3f}s ({percentages['backend_initialization']:.1f}%)")
    print(f"  Model Loading: {data['timing_breakdown']['model_loading']:.3f}s ({percentages['model_loading']:.1f}%)")
    print(f"  Transcription: {data['timing_breakdown']['transcription_core']:.3f}s ({percentages['transcription_core']:.1f}%)")
    print(f"  Result Processing: {data['timing_breakdown']['result_processing']:.3f}s ({percentages['result_processing']:.1f}%)")
    
    if analysis['bottlenecks']:
        print(f"\n🚨 Performance Bottlenecks:")
        for bottleneck in analysis['bottlenecks']:
            print(f"  • {bottleneck}")
    
    if analysis['optimization_suggestions']:
        print(f"\n💡 Optimization Suggestions:")
        for suggestion in analysis['optimization_suggestions']:
            print(f"  • {suggestion}")


def main():
    """Main function to run performance analysis."""
    parser = argparse.ArgumentParser(description="Standalone transcription performance analysis")
    parser.add_argument("audio_file", help="Audio file to test")
    parser.add_argument("--backend", default="MLXWhisper", help="Backend to test")
    parser.add_argument("--model", default="large-v3-turbo", help="Model to test")
    parser.add_argument("--analyze-latest", action="store_true", help="Analyze latest timing report")
    
    args = parser.parse_args()
    
    if args.analyze_latest:
        # Analyze the most recent timing report
        artifacts_dir = Path("artifacts")
        timing_files = list(artifacts_dir.glob("transcription_timing_*.json"))
        
        if timing_files:
            latest_file = max(timing_files, key=lambda f: f.stat().st_mtime)
            print(f"Analyzing latest timing report: {latest_file}")
            analysis = analyze_timing_report(latest_file)
            print_analysis_report(analysis, "Latest Performance Analysis")
        else:
            print("No timing reports found. Run a transcription test first.")
            return 1
    
    else:
        # Run performance test
        print(f"Running performance test with {args.backend}/{args.model} on {args.audio_file}")
        timing_report = transcribe_with_timing(args.audio_file, args.backend, args.model)
        analysis = analyze_timing_report(Path("artifacts") / f"transcription_timing_{args.backend}_{args.model}_{int(time.time())}.json")
        print_analysis_report(analysis, f"Performance Analysis: {args.backend}/{args.model}")
    
    return 0


if __name__ == "__main__":
    exit(main()) 