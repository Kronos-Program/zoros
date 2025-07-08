#!/usr/bin/env python3
"""
Test script for Streaming MLX Whisper Backend

This script tests the streaming transcription backend and compares its performance
with the standard MLX Whisper backend.

Specification: docs/requirements/dictation_requirements.md#streaming-testing
Architecture: docs/zoros_architecture.md#streaming-backend
Tests: tests/test_streaming_transcription.py
Integration: source/dictation_backends/streaming_mlx_whisper_backend.py

Related Modules:
- source/dictation_backends/streaming_mlx_whisper_backend.py - Streaming backend implementation
- source/dictation_backends/mlx_whisper_backend.py - Standard MLX Whisper backend
- docs/streaming_transcription.md - Streaming documentation

Dependencies:
- External libraries: mlx_whisper, numpy, soundfile, time
- Internal modules: source.dictation_backends
- Configuration: config/streaming_settings.json
"""

import sys
import time
import json
from pathlib import Path
from typing import Dict, Any, Optional

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from source.dictation_backends.mlx_whisper_backend import MLXWhisperBackend
from source.dictation_backends.streaming_mlx_whisper_backend import StreamingMLXWhisperBackend


def test_standard_backend(audio_path: str, model: str = "large-v3-turbo") -> Dict[str, Any]:
    """Test the standard MLX Whisper backend.
    
    Args:
        audio_path: Path to audio file
        model: Model to use
        
    Returns:
        Dictionary with results and timing information
        
    Spec: docs/requirements/dictation_requirements.md#standard-backend-testing
    Tests: tests/test_streaming_transcription.py#test_standard_backend
    """
    print(f"\n=== Testing Standard MLX Whisper Backend ===")
    print(f"Audio file: {audio_path}")
    print(f"Model: {model}")
    
    start_time = time.time()
    
    try:
        backend = MLXWhisperBackend(model)
        init_time = time.time() - start_time
        
        transcribe_start = time.time()
        result = backend.transcribe(audio_path)
        transcribe_time = time.time() - transcribe_start
        
        total_time = time.time() - start_time
        
        return {
            "backend": "StandardMLXWhisper",
            "model": model,
            "init_time": init_time,
            "transcribe_time": transcribe_time,
            "total_time": total_time,
            "result_length": len(result),
            "result_preview": result[:200] + "..." if len(result) > 200 else result,
            "success": True
        }
        
    except Exception as e:
        print(f"Error with standard backend: {e}")
        return {
            "backend": "StandardMLXWhisper",
            "model": model,
            "error": str(e),
            "success": False
        }


def test_streaming_backend(
    audio_path: str, 
    model: str = "large-v3-turbo",
    chunk_duration: float = 10.0,
    overlap_duration: float = 2.0,
    max_workers: int = 2
) -> Dict[str, Any]:
    """Test the streaming MLX Whisper backend.
    
    Args:
        audio_path: Path to audio file
        model: Model to use
        chunk_duration: Duration of each chunk in seconds
        overlap_duration: Overlap between chunks in seconds
        max_workers: Number of parallel workers
        
    Returns:
        Dictionary with results and timing information
        
    Spec: docs/requirements/dictation_requirements.md#streaming-backend-testing
    Tests: tests/test_streaming_transcription.py#test_streaming_backend
    """
    print(f"\n=== Testing Streaming MLX Whisper Backend ===")
    print(f"Audio file: {audio_path}")
    print(f"Model: {model}")
    print(f"Chunk duration: {chunk_duration}s")
    print(f"Overlap duration: {overlap_duration}s")
    print(f"Max workers: {max_workers}")
    
    start_time = time.time()
    
    try:
        backend = StreamingMLXWhisperBackend(
            model_name=model,
            chunk_duration=chunk_duration,
            overlap_duration=overlap_duration,
            max_workers=max_workers
        )
        init_time = time.time() - start_time
        
        transcribe_start = time.time()
        result = backend.transcribe(audio_path)
        transcribe_time = time.time() - transcribe_start
        
        # Get detailed metrics
        metrics = backend.get_performance_metrics()
        
        total_time = time.time() - start_time
        
        # Clean up
        backend.cleanup()
        
        return {
            "backend": "StreamingMLXWhisper",
            "model": model,
            "chunk_duration": chunk_duration,
            "overlap_duration": overlap_duration,
            "max_workers": max_workers,
            "init_time": init_time,
            "transcribe_time": transcribe_time,
            "total_time": total_time,
            "result_length": len(result),
            "result_preview": result[:200] + "..." if len(result) > 200 else result,
            "metrics": metrics,
            "success": True
        }
        
    except Exception as e:
        print(f"Error with streaming backend: {e}")
        return {
            "backend": "StreamingMLXWhisper",
            "model": model,
            "error": str(e),
            "success": False
        }


def compare_backends(audio_path: str, model: str = "large-v3-turbo") -> Dict[str, Any]:
    """Compare standard and streaming backends.
    
    Args:
        audio_path: Path to audio file
        model: Model to use
        
    Returns:
        Dictionary with comparison results
        
    Spec: docs/requirements/dictation_requirements.md#backend-comparison
    Tests: tests/test_streaming_transcription.py#test_backend_comparison
    """
    print(f"\n{'='*60}")
    print(f"COMPARING TRANSCRIPTION BACKENDS")
    print(f"{'='*60}")
    
    # Test standard backend
    standard_result = test_standard_backend(audio_path, model)
    
    # Test streaming backend with different configurations
    streaming_configs = [
        {"chunk_duration": 10.0, "overlap_duration": 2.0, "max_workers": 2},
        {"chunk_duration": 15.0, "overlap_duration": 3.0, "max_workers": 2},
        {"chunk_duration": 8.0, "overlap_duration": 1.5, "max_workers": 3},
    ]
    
    streaming_results = []
    for config in streaming_configs:
        result = test_streaming_backend(
            audio_path, 
            model,
            chunk_duration=config["chunk_duration"],
            overlap_duration=config["overlap_duration"],
            max_workers=config["max_workers"]
        )
        streaming_results.append(result)
    
    # Calculate improvements
    if standard_result["success"]:
        standard_time = standard_result["total_time"]
        
        for i, streaming_result in enumerate(streaming_results):
            if streaming_result["success"]:
                speedup = standard_time / streaming_result["total_time"]
                streaming_results[i]["speedup"] = speedup
                streaming_results[i]["time_saved"] = standard_time - streaming_result["total_time"]
    
    comparison = {
        "audio_file": audio_path,
        "model": model,
        "standard_result": standard_result,
        "streaming_results": streaming_results,
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"COMPARISON SUMMARY")
    print(f"{'='*60}")
    
    if standard_result["success"]:
        print(f"Standard MLX Whisper:")
        print(f"  Total time: {standard_result['total_time']:.2f}s")
        print(f"  Result length: {standard_result['result_length']} chars")
        print(f"  Preview: {standard_result['result_preview']}")
    
    print(f"\nStreaming MLX Whisper Results:")
    for i, result in enumerate(streaming_results):
        if result["success"]:
            config = streaming_configs[i]
            print(f"  Config {i+1} (chunk={config['chunk_duration']}s, overlap={config['overlap_duration']}s, workers={config['max_workers']}):")
            print(f"    Total time: {result['total_time']:.2f}s")
            print(f"    Speedup: {result.get('speedup', 0):.2f}x")
            print(f"    Time saved: {result.get('time_saved', 0):.2f}s")
            print(f"    Result length: {result['result_length']} chars")
            print(f"    Preview: {result['result_preview']}")
    
    return comparison


def save_results(comparison: Dict[str, Any], output_dir: str = "artifacts") -> None:
    """Save comparison results to file.
    
    Args:
        comparison: Comparison results dictionary
        output_dir: Directory to save results
        
    Spec: docs/requirements/dictation_requirements.md#result-saving
    Tests: tests/test_streaming_transcription.py#test_result_saving
    """
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    filename = f"streaming_comparison_{timestamp}.json"
    filepath = output_path / filename
    
    with open(filepath, 'w') as f:
        json.dump(comparison, f, indent=2)
    
    print(f"\nResults saved to: {filepath}")


def main():
    """Main function to run the streaming transcription tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Streaming MLX Whisper Backend")
    parser.add_argument("audio_file", help="Path to audio file to transcribe")
    parser.add_argument("--model", default="large-v3-turbo", help="MLX Whisper model to use")
    parser.add_argument("--output-dir", default="artifacts", help="Directory to save results")
    parser.add_argument("--compare", action="store_true", help="Compare with standard backend")
    
    args = parser.parse_args()
    
    audio_path = Path(args.audio_file)
    if not audio_path.exists():
        print(f"Error: Audio file not found: {audio_path}")
        sys.exit(1)
    
    print(f"Testing streaming transcription with:")
    print(f"  Audio file: {audio_path}")
    print(f"  Model: {args.model}")
    print(f"  Output directory: {args.output_dir}")
    
    if args.compare:
        # Run full comparison
        comparison = compare_backends(str(audio_path), args.model)
        save_results(comparison, args.output_dir)
    else:
        # Test only streaming backend
        result = test_streaming_backend(str(audio_path), args.model)
        if result["success"]:
            print(f"\nStreaming transcription completed successfully!")
            print(f"Total time: {result['total_time']:.2f}s")
            print(f"Result: {result['result_preview']}")
        else:
            print(f"\nStreaming transcription failed: {result['error']}")


if __name__ == "__main__":
    main() 