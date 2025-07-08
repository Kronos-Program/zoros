#!/usr/bin/env python3
"""Test long recording performance for optimization validation.

This script creates synthetic long audio files and tests transcription performance
across different backends to validate optimization improvements.

Usage:
    python scripts/test_long_recording_performance.py [--duration 300] [--backend MLXWhisper]
"""
import sys
import json
import time
import argparse
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional
import numpy as np
import soundfile as sf

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from source.interfaces.intake.main import transcribe_audio


def create_synthetic_audio(duration_seconds: float, sample_rate: int = 16000) -> np.ndarray:
    """Create synthetic audio for testing.
    
    Args:
        duration_seconds: Length of audio in seconds
        sample_rate: Audio sample rate
        
    Returns:
        Audio data as numpy array
    """
    # Create a simple sine wave with some variation
    t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds))
    
    # Create a speech-like signal (multiple frequencies)
    signal = (
        0.3 * np.sin(2 * np.pi * 200 * t) +  # Low frequency
        0.2 * np.sin(2 * np.pi * 800 * t) +  # Mid frequency  
        0.1 * np.sin(2 * np.pi * 2000 * t) + # High frequency
        0.05 * np.random.randn(len(t))       # Noise
    )
    
    # Normalize
    signal = signal / np.max(np.abs(signal)) * 0.8
    
    return signal


def test_backend_performance(audio_file: Path, backend: str, model: str = "large-v3-turbo") -> Dict[str, Any]:
    """Test performance of a specific backend.
    
    Args:
        audio_file: Path to audio file
        backend: Backend to test
        model: Model to use
        
    Returns:
        Performance metrics dictionary
    """
    print(f"Testing {backend}/{model} on {audio_file.name}")
    
    # Get audio info
    audio_info = sf.info(audio_file)
    audio_duration = audio_info.duration
    audio_size = audio_file.stat().st_size
    
    # Measure transcription time
    start_time = time.time()
    try:
        result = transcribe_audio(str(audio_file), backend, model)
        transcription_time = time.time() - start_time
        success = True
        error = None
    except Exception as e:
        transcription_time = time.time() - start_time
        result = ""
        success = False
        error = str(e)
    
    # Calculate metrics
    wav_ratio = audio_duration / transcription_time if transcription_time > 0 else 0
    words_per_second = len(result.split()) / transcription_time if transcription_time > 0 else 0
    
    return {
        'backend': backend,
        'model': model,
        'audio_file': audio_file.name,
        'audio_duration': audio_duration,
        'audio_size_kb': audio_size / 1024,
        'transcription_time': transcription_time,
        'wav_ratio': wav_ratio,
        'words_per_second': words_per_second,
        'result_length': len(result),
        'success': success,
        'error': error,
        'result_preview': result[:100] + "..." if len(result) > 100 else result
    }


def run_long_recording_tests(duration_seconds: float = 300, backends: Optional[List[str]] = None) -> Dict[str, Any]:
    """Run comprehensive long recording performance tests.
    
    Args:
        duration_seconds: Duration of test audio in seconds
        backends: List of backends to test (None for all available)
        
    Returns:
        Test results summary
    """
    print(f"Running long recording performance tests ({duration_seconds}s audio)")
    
    # Create synthetic audio
    print("Creating synthetic audio...")
    audio_data = create_synthetic_audio(duration_seconds)
    
    # Save to temporary file
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
        sf.write(tmp_file.name, audio_data, 16000)
        audio_file = Path(tmp_file.name)
    
    print(f"Created test audio: {audio_file} ({audio_file.stat().st_size / 1024:.1f} KB)")
    
    # Define backends to test
    if backends is None:
        backends = [
            "MLXWhisper",
            "ParallelMLXWhisper", 
            "QueueBasedStreamingMLXWhisper",
            "RealtimeStreamingMLXWhisper"
        ]
    
    # Test each backend
    results = []
    for backend in backends:
        print(f"\n{'='*60}")
        result = test_backend_performance(audio_file, backend)
        results.append(result)
        
        if result['success']:
            print(f"✅ {backend}: {result['transcription_time']:.2f}s ({result['wav_ratio']:.2f}x)")
        else:
            print(f"❌ {backend}: Failed - {result['error']}")
    
    # Clean up
    audio_file.unlink(missing_ok=True)
    
    # Generate summary
    successful_results = [r for r in results if r['success']]
    failed_results = [r for r in results if not r['success']]
    
    summary = {
        'test_configuration': {
            'audio_duration_seconds': duration_seconds,
            'backends_tested': backends,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        },
        'summary': {
            'total_tests': len(results),
            'successful_tests': len(successful_results),
            'failed_tests': len(failed_results),
            'success_rate': len(successful_results) / len(results) * 100 if results else 0
        },
        'performance_ranking': [],
        'detailed_results': results
    }
    
    # Rank successful results by performance
    if successful_results:
        ranked_results = sorted(successful_results, key=lambda x: x['transcription_time'])
        summary['performance_ranking'] = [
            {
                'rank': i + 1,
                'backend': r['backend'],
                'transcription_time': r['transcription_time'],
                'wav_ratio': r['wav_ratio'],
                'words_per_second': r['words_per_second']
            }
            for i, r in enumerate(ranked_results)
        ]
    
    return summary


def print_performance_report(summary: Dict[str, Any]):
    """Print a formatted performance report.
    
    Args:
        summary: Test results summary
    """
    print(f"\n{'='*80}")
    print("LONG RECORDING PERFORMANCE TEST REPORT")
    print(f"{'='*80}")
    
    config = summary['test_configuration']
    stats = summary['summary']
    
    print(f"Test Configuration:")
    print(f"  Audio Duration: {config['audio_duration_seconds']}s ({config['audio_duration_seconds']/60:.1f} minutes)")
    print(f"  Backends Tested: {', '.join(config['backends_tested'])}")
    print(f"  Timestamp: {config['timestamp']}")
    
    print(f"\nTest Results:")
    print(f"  Total Tests: {stats['total_tests']}")
    print(f"  Successful: {stats['successful_tests']}")
    print(f"  Failed: {stats['failed_tests']}")
    print(f"  Success Rate: {stats['success_rate']:.1f}%")
    
    if summary['performance_ranking']:
        print(f"\nPerformance Ranking:")
        for rank in summary['performance_ranking']:
            print(f"  {rank['rank']}. {rank['backend']}: {rank['transcription_time']:.2f}s "
                  f"({rank['wav_ratio']:.2f}x, {rank['words_per_second']:.1f} wps)")
    
    # Check if performance meets targets
    print(f"\nPerformance Analysis:")
    if summary['performance_ranking']:
        best_result = summary['performance_ranking'][0]
        audio_duration = summary['test_configuration']['audio_duration_seconds']
        
        # Calculate if performance meets targets
        target_time = audio_duration / 4  # Target 4x WAV ratio for long recordings
        if best_result['transcription_time'] <= target_time:
            print(f"  ✅ Best performance meets target: {best_result['transcription_time']:.2f}s <= {target_time:.2f}s")
        else:
            print(f"  ❌ Best performance below target: {best_result['transcription_time']:.2f}s > {target_time:.2f}s")
        
        # Check if 10-minute recording would be acceptable
        if audio_duration >= 300:  # 5+ minutes
            ten_min_estimate = (600 / audio_duration) * best_result['transcription_time']
            if ten_min_estimate <= 150:  # 2.5 minutes
                print(f"  ✅ 10-minute recording estimate: {ten_min_estimate:.1f}s (acceptable)")
            else:
                print(f"  ❌ 10-minute recording estimate: {ten_min_estimate:.1f}s (too slow)")
    
    print(f"{'='*80}")


def main():
    """Main function to run long recording performance tests."""
    parser = argparse.ArgumentParser(description="Test long recording performance")
    parser.add_argument("--duration", type=float, default=300, 
                       help="Duration of test audio in seconds (default: 300)")
    parser.add_argument("--backend", type=str, 
                       help="Specific backend to test (default: all available)")
    parser.add_argument("--output", type=str, 
                       help="Output file for results (default: artifacts/long_recording_test.json)")
    
    args = parser.parse_args()
    
    # Validate duration
    if args.duration < 30:
        print("Warning: Duration < 30s may not provide meaningful long recording data")
    
    # Determine backends to test
    backends = [args.backend] if args.backend else None
    
    # Run tests
    print(f"Starting long recording performance tests...")
    summary = run_long_recording_tests(args.duration, backends)
    
    # Print report
    print_performance_report(summary)
    
    # Save results
    output_file = args.output or f"artifacts/long_recording_test_{int(time.time())}.json"
    output_path = Path(output_file)
    output_path.parent.mkdir(exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\nResults saved to: {output_path}")
    
    return 0 if summary['summary']['success_rate'] > 0 else 1


if __name__ == "__main__":
    sys.exit(main()) 