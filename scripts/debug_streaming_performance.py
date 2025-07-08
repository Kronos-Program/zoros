#!/usr/bin/env python3
"""
Debug Streaming Performance Script

This script tests the streaming MLX Whisper backend with detailed debugging
output to identify performance bottlenecks and chunking issues.

Specification: docs/requirements/dictation_requirements.md#performance-debugging
Architecture: docs/zoros_architecture.md#streaming-backend
Tests: tests/test_streaming_transcription.py#test_debug_performance

Usage:
    python scripts/debug_streaming_performance.py <audio_file> [options]

Example:
    python scripts/debug_streaming_performance.py audio/intake/latest.wav --model large-v3-turbo
"""

import argparse
import time
import sys
from pathlib import Path

# Add source to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from source.dictation_backends.streaming_mlx_whisper_backend import StreamingMLXWhisperBackend
from source.dictation_backends.mlx_whisper_backend import MLXWhisperBackend


def test_streaming_debug(audio_path: str, model: str = "large-v3-turbo", 
                        chunk_duration: float = 10.0, overlap_duration: float = 2.0,
                        max_workers: int = 2) -> None:
    """Test streaming backend with detailed debugging output.
    
    Args:
        audio_path: Path to audio file
        model: MLX Whisper model to use
        chunk_duration: Duration of each chunk in seconds
        overlap_duration: Overlap between chunks in seconds
        max_workers: Number of parallel workers
    """
    print("=" * 80)
    print("STREAMING PERFORMANCE DEBUG TEST")
    print("=" * 80)
    print(f"Audio file: {audio_path}")
    print(f"Model: {model}")
    print(f"Chunk duration: {chunk_duration}s")
    print(f"Overlap duration: {overlap_duration}s")
    print(f"Max workers: {max_workers}")
    print("=" * 80)
    
    # Test 1: Standard MLX Whisper (baseline)
    print("\n" + "=" * 40)
    print("TEST 1: STANDARD MLX WHISPER (BASELINE)")
    print("=" * 40)
    
    start_time = time.time()
    try:
        standard_backend = MLXWhisperBackend(model)
        standard_init_time = time.time() - start_time
        
        transcribe_start = time.time()
        standard_result = standard_backend.transcribe(audio_path)
        standard_transcribe_time = time.time() - transcribe_start
        
        standard_total_time = time.time() - start_time
        
        print(f"Standard MLX Whisper Results:")
        print(f"  Init time: {standard_init_time:.2f}s")
        print(f"  Transcribe time: {standard_transcribe_time:.2f}s")
        print(f"  Total time: {standard_total_time:.2f}s")
        print(f"  Result length: {len(standard_result)} chars")
        print(f"  Result preview: {standard_result[:100]}...")
        
    except Exception as e:
        print(f"Standard backend failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test 2: Streaming MLX Whisper (with debugging)
    print("\n" + "=" * 40)
    print("TEST 2: STREAMING MLX WHISPER (DEBUG)")
    print("=" * 40)
    
    start_time = time.time()
    try:
        streaming_backend = StreamingMLXWhisperBackend(
            model_name=model,
            chunk_duration=chunk_duration,
            overlap_duration=overlap_duration,
            max_workers=max_workers
        )
        streaming_init_time = time.time() - start_time
        
        transcribe_start = time.time()
        streaming_result = streaming_backend.transcribe(audio_path)
        streaming_transcribe_time = time.time() - transcribe_start
        
        streaming_total_time = time.time() - start_time
        
        # Get performance metrics
        metrics = streaming_backend.get_performance_metrics()
        
        print(f"\nStreaming MLX Whisper Results:")
        print(f"  Init time: {streaming_init_time:.2f}s")
        print(f"  Transcribe time: {streaming_transcribe_time:.2f}s")
        print(f"  Total time: {streaming_total_time:.2f}s")
        print(f"  Result length: {len(streaming_result)} chars")
        print(f"  Result preview: {streaming_result[:100]}...")
        
        print(f"\nPerformance Metrics:")
        print(f"  Total processed chunks: {metrics.get('total_processed_chunks', 0)}")
        print(f"  Average chunk time: {metrics.get('average_chunk_time', 0):.2f}s")
        print(f"  Average merge time: {metrics.get('average_merge_time', 0):.2f}s")
        print(f"  Chunk duration: {metrics.get('chunk_duration', 0)}s")
        print(f"  Overlap duration: {metrics.get('overlap_duration', 0)}s")
        print(f"  Max workers: {metrics.get('max_workers', 0)}")
        
        # Clean up
        streaming_backend.cleanup()
        
    except Exception as e:
        print(f"Streaming backend failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Performance comparison
    print("\n" + "=" * 40)
    print("PERFORMANCE COMPARISON")
    print("=" * 40)
    
    speedup = standard_transcribe_time / streaming_transcribe_time if streaming_transcribe_time > 0 else 0
    time_ratio = streaming_transcribe_time / standard_transcribe_time if standard_transcribe_time > 0 else 0
    
    print(f"Standard transcription time: {standard_transcribe_time:.2f}s")
    print(f"Streaming transcription time: {streaming_transcribe_time:.2f}s")
    print(f"Speedup: {speedup:.2f}x")
    print(f"Time ratio: {time_ratio:.2f}x")
    
    if speedup > 1.0:
        print(f"✅ Streaming is {speedup:.2f}x FASTER than standard")
    else:
        print(f"❌ Streaming is {1/speedup:.2f}x SLOWER than standard")
    
    # Quality comparison
    print(f"\nQuality Comparison:")
    print(f"Standard result length: {len(standard_result)} chars")
    print(f"Streaming result length: {len(streaming_result)} chars")
    
    if len(standard_result) > 0 and len(streaming_result) > 0:
        similarity = min(len(standard_result), len(streaming_result)) / max(len(standard_result), len(streaming_result))
        print(f"Length similarity: {similarity:.2f}")
        
        if similarity > 0.8:
            print("✅ Results are similar in length")
        else:
            print("⚠️  Results differ significantly in length")
    
    print("\n" + "=" * 80)
    print("DEBUG TEST COMPLETED")
    print("=" * 80)


def main():
    """Main function for the debug script."""
    parser = argparse.ArgumentParser(description="Debug streaming performance")
    parser.add_argument("audio_file", help="Path to audio file to test")
    parser.add_argument("--model", default="large-v3-turbo", help="MLX Whisper model to use")
    parser.add_argument("--chunk-duration", type=float, default=10.0, help="Chunk duration in seconds")
    parser.add_argument("--overlap-duration", type=float, default=2.0, help="Overlap duration in seconds")
    parser.add_argument("--max-workers", type=int, default=2, help="Maximum number of workers")
    
    args = parser.parse_args()
    
    if not Path(args.audio_file).exists():
        print(f"Error: Audio file not found: {args.audio_file}")
        sys.exit(1)
    
    test_streaming_debug(
        audio_path=args.audio_file,
        model=args.model,
        chunk_duration=args.chunk_duration,
        overlap_duration=args.overlap_duration,
        max_workers=args.max_workers
    )


if __name__ == "__main__":
    main() 