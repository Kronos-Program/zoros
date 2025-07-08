#!/usr/bin/env python3
"""Analyze transcription performance and suggest optimizations.

This script analyzes the transcription pipeline performance and provides
recommendations for improving speed and efficiency.

Usage:
    python scripts/analyze_transcription_performance.py [audio_file]
"""
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
import time

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from source.interfaces.intake.main import transcribe_audio


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


def run_performance_test(audio_file: str, backend: str = "MLXWhisper", model: str = "large-v3-turbo") -> Dict[str, Any]:
    """Run a performance test and return analysis."""
    print(f"Running performance test with {backend}/{model} on {audio_file}")
    
    start_time = time.time()
    result = transcribe_audio(audio_file, backend, model)
    total_time = time.time() - start_time
    
    # Find the latest timing report
    artifacts_dir = Path("artifacts")
    timing_files = list(artifacts_dir.glob(f"transcription_timing_{backend}_{model}_*.json"))
    
    if timing_files:
        latest_file = max(timing_files, key=lambda f: f.stat().st_mtime)
        return analyze_timing_report(latest_file)
    else:
        return {"error": "No timing report found"}


def compare_backends(audio_file: str, backends: Optional[List[str]] = None) -> Dict[str, Any]:
    """Compare performance across different backends."""
    if backends is None:
        backends = ["MLXWhisper", "FasterWhisper", "WhisperCPP"]
    
    results = {}
    
    for backend in backends:
        try:
            print(f"\n{'='*50}")
            print(f"Testing {backend}")
            print(f"{'='*50}")
            
            # Test with small model for fair comparison
            model = "small" if backend != "MLXWhisper" else "large-v3-turbo"
            analysis = run_performance_test(audio_file, backend, model)
            
            if "error" not in analysis:
                results[backend] = analysis
            else:
                print(f"Failed to test {backend}: {analysis['error']}")
                
        except Exception as e:
            print(f"Error testing {backend}: {e}")
            results[backend] = {"error": str(e)}
    
    return results


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
    parser = argparse.ArgumentParser(description="Analyze transcription performance")
    parser.add_argument("audio_file", nargs="?", help="Audio file to test")
    parser.add_argument("--backend", default="MLXWhisper", help="Backend to test")
    parser.add_argument("--model", default="large-v3-turbo", help="Model to test")
    parser.add_argument("--compare", action="store_true", help="Compare all backends")
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
    
    elif args.compare:
        if not args.audio_file:
            print("Error: Audio file required for backend comparison")
            return 1
        
        print("Comparing performance across backends...")
        results = compare_backends(args.audio_file)
        
        print(f"\n{'='*80}")
        print("BACKEND COMPARISON SUMMARY")
        print(f"{'='*80}")
        
        for backend, analysis in results.items():
            if "error" not in analysis:
                data = analysis['data']
                print(f"\n{backend}:")
                print(f"  Total Time: {data['total_time']:.3f}s")
                print(f"  WAV Ratio: {data.get('wav_to_transcription_ratio', 'Unknown'):.2f}x")
                print(f"  Words/Second: {data['words_per_second']:.1f}")
                print(f"  Main Bottleneck: {analysis['percentages']['transcription_core']:.1f}% transcription core")
            else:
                print(f"\n{backend}: ERROR - {analysis['error']}")
    
    elif args.audio_file:
        # Run single performance test
        analysis = run_performance_test(args.audio_file, args.backend, args.model)
        print_analysis_report(analysis, f"Performance Analysis: {args.backend}/{args.model}")
    
    else:
        print("No action specified. Use --help for options.")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main()) 