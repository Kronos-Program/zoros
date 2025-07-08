#!/usr/bin/env python3
"""
Simple test for Real-time Streaming MLX Whisper Backend

This script tests the real-time streaming with minimal configuration
to avoid multiprocessing and memory issues.

Specification: docs/requirements/dictation_requirements.md#realtime-testing
Architecture: docs/zoros_architecture.md#realtime-streaming-backend
Tests: tests/test_realtime_streaming.py
Integration: source/dictation_backends/realtime_streaming_backend.py

Related Modules:
- source/dictation_backends/realtime_streaming_backend.py - Real-time backend implementation
- source/dictation_backends/mlx_whisper_backend.py - Base MLX Whisper backend
- docs/realtime_streaming.md - Real-time streaming documentation

Dependencies:
- External libraries: numpy, soundfile, time
- Internal modules: source.dictation_backends.realtime_streaming_backend
- Configuration: config/realtime_streaming_settings.json
"""

import time
from pathlib import Path

import numpy as np
import soundfile as sf

from source.dictation_backends.realtime_streaming_backend import RealtimeStreamingBackend


def test_simple_realtime() -> None:
    """Test real-time streaming with minimal configuration.
    
    Spec: docs/requirements/dictation_requirements.md#realtime-testing
    Tests: tests/test_realtime_streaming.py#test_simple_realtime
    """
    print("Testing simple real-time streaming...")
    
    # Create a simple test audio (1 second of silence)
    sample_rate = 16000
    duration = 1.0
    audio_data = np.zeros(int(sample_rate * duration))
    
    print(f"Created test audio: {duration}s at {sample_rate}Hz")
    
    # Create real-time backend with minimal settings
    backend = RealtimeStreamingBackend(
        model_name="tiny",  # Use tiny model to avoid memory issues
        chunk_duration=2.0,  # 2-second chunks
        overlap_duration=0.5,  # 0.5-second overlap
        max_workers=1,  # Single worker
        callback=simple_callback
    )
    
    print("Created real-time backend")
    
    try:
        # Start streaming
        backend.start_streaming()
        print("Started streaming")
        
        # Add audio data in small chunks
        chunk_size = int(0.5 * sample_rate)  # 0.5-second chunks
        start_time = time.time()
        
        for i in range(0, len(audio_data), chunk_size):
            chunk_data = audio_data[i:i+chunk_size]
            timestamp = time.time() - start_time
            
            backend.add_audio_data(chunk_data, timestamp)
            print(f"Added chunk at {timestamp:.2f}s")
            
            time.sleep(0.1)  # Small delay
        
        # Stop streaming
        print("Stopping streaming...")
        final_result = backend.stop_streaming()
        
        print(f"Final result: {final_result}")
        print("Test completed successfully!")
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up
        backend.cleanup()


def simple_callback(transcription: str, latency: float) -> None:
    """Simple callback for real-time transcription.
    
    Args:
        transcription: Transcribed text
        latency: Processing latency
        
    Spec: docs/requirements/dictation_requirements.md#realtime-callback
    Tests: tests/test_realtime_streaming.py#test_simple_callback
    """
    print(f"  Callback: {transcription[:50]}... (latency: {latency:.2f}s)")


if __name__ == "__main__":
    test_simple_realtime() 