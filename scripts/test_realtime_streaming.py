#!/usr/bin/env python3
"""
Test script for Real-time Streaming MLX Whisper Backend

This script tests the real-time streaming transcription backend to ensure
it processes audio chunks as they're being recorded.

Specification: docs/requirements/dictation_requirements.md#realtime-testing
Architecture: docs/zoros_architecture.md#realtime-streaming-backend
Tests: tests/test_realtime_streaming.py
Integration: source/dictation_backends/realtime_streaming_backend.py

Related Modules:
- source/dictation_backends/realtime_streaming_backend.py - Real-time backend implementation
- source/dictation_backends/mlx_whisper_backend.py - Base MLX Whisper backend
- docs/realtime_streaming.md - Real-time streaming documentation

Dependencies:
- External libraries: numpy, soundfile, time, threading
- Internal modules: source.dictation_backends.realtime_streaming_backend
- Configuration: config/realtime_streaming_settings.json
"""

import argparse
import json
import time
from pathlib import Path
from typing import List

import numpy as np
import soundfile as sf

from source.dictation_backends.realtime_streaming_backend import RealtimeStreamingBackend


def test_realtime_streaming(audio_file: str, model: str = "large-v3-turbo", 
                           chunk_duration: float = 5.0, overlap_duration: float = 1.0) -> None:
    """Test real-time streaming with a pre-recorded audio file.
    
    Args:
        audio_file: Path to audio file to test
        model: MLX Whisper model to use
        chunk_duration: Duration of each chunk in seconds
        overlap_duration: Overlap between chunks in seconds
        
    Spec: docs/requirements/dictation_requirements.md#realtime-testing
    Tests: tests/test_realtime_streaming.py#test_realtime_streaming
    """
    print(f"Testing real-time streaming with {audio_file}")
    print(f"Model: {model}, Chunk duration: {chunk_duration}s, Overlap: {overlap_duration}s")
    
    # Load audio file
    audio_data, sample_rate = sf.read(audio_file)
    if len(audio_data.shape) > 1:
        audio_data = audio_data[:, 0]  # Convert to mono
    
    print(f"Audio duration: {len(audio_data) / sample_rate:.2f}s")
    print(f"Sample rate: {sample_rate}Hz")
    
    # Create real-time backend
    backend = RealtimeStreamingBackend(
        model_name=model,
        chunk_duration=chunk_duration,
        overlap_duration=overlap_duration,
        max_workers=1,
        callback=on_transcription_callback
    )
    
    # Start streaming
    backend.start_streaming()
    
    # Simulate real-time audio input
    chunk_size = int(chunk_duration * sample_rate)
    overlap_size = int(overlap_duration * sample_rate)
    step_size = chunk_size - overlap_size
    
    print(f"Processing audio in real-time chunks...")
    start_time = time.time()
    
    for i in range(0, len(audio_data), step_size):
        chunk_start = i
        chunk_end = min(i + chunk_size, len(audio_data))
        chunk_data = audio_data[chunk_start:chunk_end]
        
        # Simulate real-time timestamp
        timestamp = time.time() - start_time
        
        # Add audio data to backend
        backend.add_audio_data(chunk_data, timestamp)
        
        # Small delay to simulate real-time processing
        time.sleep(0.1)
        
        print(f"Added chunk {i//step_size + 1} at {timestamp:.2f}s")
    
    # Stop streaming and get final result
    print(f"Stopping real-time streaming...")
    final_transcription = backend.stop_streaming()
    
    total_time = time.time() - start_time
    audio_duration = len(audio_data) / sample_rate
    
    print(f"\n=== REAL-TIME STREAMING RESULTS ===")
    print(f"Audio duration: {audio_duration:.2f}s")
    print(f"Processing time: {total_time:.2f}s")
    print(f"Real-time ratio: {total_time/audio_duration:.2f}x")
    print(f"Final transcription: {final_transcription}")
    
    # Get performance metrics
    metrics = backend.get_performance_metrics()
    print(f"\nPerformance metrics:")
    for key, value in metrics.items():
        print(f"  {key}: {value}")
    
    # Save results
    results = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'audio_file': audio_file,
        'model': model,
        'chunk_duration': chunk_duration,
        'overlap_duration': overlap_duration,
        'audio_duration': audio_duration,
        'processing_time': total_time,
        'realtime_ratio': total_time/audio_duration,
        'final_transcription': final_transcription,
        'performance_metrics': metrics
    }
    
    artifacts_dir = Path("artifacts")
    artifacts_dir.mkdir(exist_ok=True)
    
    results_file = artifacts_dir / f"realtime_streaming_test_{int(time.time())}.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to: {results_file}")


def on_transcription_callback(transcription: str, latency: float) -> None:
    """Callback function for real-time transcription results.
    
    Args:
        transcription: Transcribed text from the chunk
        latency: Processing latency in seconds
        
    Spec: docs/requirements/dictation_requirements.md#realtime-callback
    Tests: tests/test_realtime_streaming.py#test_callback
    """
    if transcription.strip():
        print(f"  Real-time: {transcription[:100]}... (latency: {latency:.2f}s)")


def main() -> None:
    """Main function for testing real-time streaming.
    
    Spec: docs/requirements/dictation_requirements.md#realtime-testing
    Tests: tests/test_realtime_streaming.py#test_main
    """
    parser = argparse.ArgumentParser(description="Test real-time streaming MLX Whisper backend")
    parser.add_argument("audio_file", help="Path to audio file to test")
    parser.add_argument("--model", default="large-v3-turbo", help="MLX Whisper model to use")
    parser.add_argument("--chunk-duration", type=float, default=5.0, help="Chunk duration in seconds")
    parser.add_argument("--overlap-duration", type=float, default=1.0, help="Overlap duration in seconds")
    
    args = parser.parse_args()
    
    if not Path(args.audio_file).exists():
        print(f"Error: Audio file not found: {args.audio_file}")
        return
    
    try:
        test_realtime_streaming(
            args.audio_file,
            model=args.model,
            chunk_duration=args.chunk_duration,
            overlap_duration=args.overlap_duration
        )
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 