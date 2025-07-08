#!/usr/bin/env python3
"""
Benchmark script to compare dictation performance across different backends.
Optimized specifically for M1/M2 Mac performance testing.
"""

import time
import tempfile
import numpy as np
import soundfile as sf
from pathlib import Path
import logging
from typing import Dict, List, Any
import argparse
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DictationBenchmark:
    """Benchmark different dictation backends for performance comparison."""
    
    def __init__(self):
        self.backends = {}
        self.results = {}
        
    def setup_backends(self):
        """Initialize all available backends."""
        try:
            from source.dictation_backends.optimized_mlx_backend import OptimizedMLXBackend
            self.backends['optimized_mlx'] = OptimizedMLXBackend("large-v3-turbo")
            logger.info("✓ Optimized MLX backend loaded")
        except Exception as e:
            logger.warning(f"✗ Failed to load Optimized MLX backend: {e}")
            
        try:
            from source.dictation_backends.mlx_whisper_backend import MLXWhisperBackend
            self.backends['mlx_whisper'] = MLXWhisperBackend("large-v3-turbo")
            logger.info("✓ MLX Whisper backend loaded")
        except Exception as e:
            logger.warning(f"✗ Failed to load MLX Whisper backend: {e}")
            
        try:
            from source.dictation_backends.faster_whisper_backend import FasterWhisperBackend
            self.backends['faster_whisper'] = FasterWhisperBackend("large-v3-turbo")
            logger.info("✓ Faster Whisper backend loaded")
        except Exception as e:
            logger.warning(f"✗ Failed to load Faster Whisper backend: {e}")
    
    def create_test_audio(self, duration: float = 10.0, sample_rate: int = 16000) -> str:
        """Create a test audio file with synthetic speech-like content."""
        # Generate a synthetic audio signal that resembles speech
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Create a complex waveform with multiple frequency components
        # This simulates the complexity of human speech
        signal = np.zeros_like(t)
        
        # Add fundamental frequency and harmonics
        for i, freq in enumerate([200, 400, 600, 800, 1000, 1200]):
            amplitude = 0.3 / (i + 1)  # Decreasing amplitude for higher harmonics
            signal += amplitude * np.sin(2 * np.pi * freq * t)
        
        # Add some modulation to simulate speech patterns
        envelope = 0.5 + 0.3 * np.sin(2 * np.pi * 2 * t)  # 2 Hz modulation
        signal *= envelope
        
        # Add some noise to make it more realistic
        noise = np.random.normal(0, 0.05, signal.shape)
        signal += noise
        
        # Normalize
        signal = signal / np.max(np.abs(signal)) * 0.7
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            sf.write(tmp_file.name, signal, sample_rate)
            return tmp_file.name
    
    def benchmark_backend(self, backend_name: str, backend, audio_file: str, 
                         num_runs: int = 5) -> Dict[str, Any]:
        """Benchmark a specific backend."""
        logger.info(f"Benchmarking {backend_name}...")
        
        times = []
        errors = []
        
        # Preload model if available
        if hasattr(backend, 'preload_model'):
            logger.info(f"Preloading model for {backend_name}")
            start_preload = time.time()
            backend.preload_model()
            preload_time = time.time() - start_preload
            logger.info(f"Model preloaded in {preload_time:.2f}s")
        else:
            preload_time = 0
        
        for i in range(num_runs):
            try:
                start_time = time.time()
                result = backend.transcribe(audio_file)
                end_time = time.time()
                
                transcribe_time = end_time - start_time
                times.append(transcribe_time)
                
                logger.info(f"Run {i+1}/{num_runs}: {transcribe_time:.2f}s")
                
            except Exception as e:
                errors.append(str(e))
                logger.error(f"Run {i+1}/{num_runs} failed: {e}")
        
        # Calculate statistics
        if times:
            avg_time = np.mean(times)
            min_time = np.min(times)
            max_time = np.max(times)
            std_time = np.std(times)
            
            # Get audio duration for real-time factor calculation
            try:
                with sf.SoundFile(audio_file) as f:
                    audio_duration = len(f) / f.samplerate
                rtf = avg_time / audio_duration if audio_duration > 0 else 0
            except:
                audio_duration = 0
                rtf = 0
        else:
            avg_time = min_time = max_time = std_time = rtf = 0
            audio_duration = 0
        
        return {
            'backend': backend_name,
            'num_runs': num_runs,
            'successful_runs': len(times),
            'errors': errors,
            'preload_time': preload_time,
            'avg_time': avg_time,
            'min_time': min_time,
            'max_time': max_time,
            'std_time': std_time,
            'audio_duration': audio_duration,
            'real_time_factor': rtf,
            'times': times
        }
    
    def run_benchmark(self, audio_duration: float = 10.0, num_runs: int = 5) -> Dict[str, Any]:
        """Run complete benchmark across all backends."""
        logger.info(f"Starting benchmark with {audio_duration}s audio, {num_runs} runs per backend")
        
        # Create test audio
        audio_file = self.create_test_audio(audio_duration)
        logger.info(f"Created test audio: {audio_file}")
        
        try:
            # Benchmark all backends
            for backend_name, backend in self.backends.items():
                self.results[backend_name] = self.benchmark_backend(
                    backend_name, backend, audio_file, num_runs
                )
            
            # Generate summary
            summary = self.generate_summary()
            
            return {
                'summary': summary,
                'detailed_results': self.results,
                'test_config': {
                    'audio_duration': audio_duration,
                    'num_runs': num_runs,
                    'audio_file': audio_file
                }
            }
            
        finally:
            # Clean up test audio
            try:
                Path(audio_file).unlink()
            except:
                pass
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate a performance summary."""
        summary = {
            'fastest_backend': None,
            'lowest_rtf': None,
            'most_reliable': None,
            'performance_ranking': []
        }
        
        valid_results = {k: v for k, v in self.results.items() if v['successful_runs'] > 0}
        
        if not valid_results:
            return summary
        
        # Find fastest backend
        fastest = min(valid_results.items(), key=lambda x: x[1]['avg_time'])
        summary['fastest_backend'] = {
            'name': fastest[0],
            'avg_time': fastest[1]['avg_time']
        }
        
        # Find lowest real-time factor
        lowest_rtf = min(valid_results.items(), key=lambda x: x[1]['real_time_factor'])
        summary['lowest_rtf'] = {
            'name': lowest_rtf[0],
            'rtf': lowest_rtf[1]['real_time_factor']
        }
        
        # Find most reliable (highest success rate)
        most_reliable = max(valid_results.items(), 
                          key=lambda x: x[1]['successful_runs'] / x[1]['num_runs'])
        summary['most_reliable'] = {
            'name': most_reliable[0],
            'success_rate': most_reliable[1]['successful_runs'] / most_reliable[1]['num_runs']
        }
        
        # Performance ranking
        ranking = sorted(valid_results.items(), 
                        key=lambda x: (x[1]['real_time_factor'], x[1]['avg_time']))
        summary['performance_ranking'] = [
            {
                'rank': i + 1,
                'backend': backend[0],
                'avg_time': backend[1]['avg_time'],
                'rtf': backend[1]['real_time_factor']
            }
            for i, backend in enumerate(ranking)
        ]
        
        return summary
    
    def print_results(self, results: Dict[str, Any]):
        """Print benchmark results in a readable format."""
        print("\n" + "="*80)
        print("DICTATION PERFORMANCE BENCHMARK RESULTS")
        print("="*80)
        
        print(f"\nTest Configuration:")
        print(f"  Audio Duration: {results['test_config']['audio_duration']:.1f}s")
        print(f"  Runs per Backend: {results['test_config']['num_runs']}")
        
        print(f"\nPerformance Summary:")
        summary = results['summary']
        
        if summary['fastest_backend']:
            print(f"  🏆 Fastest Backend: {summary['fastest_backend']['name']} ({summary['fastest_backend']['avg_time']:.2f}s)")
        
        if summary['lowest_rtf']:
            print(f"  ⚡ Lowest RTF: {summary['lowest_rtf']['name']} ({summary['lowest_rtf']['rtf']:.2f}x)")
        
        if summary['most_reliable']:
            print(f"  🔒 Most Reliable: {summary['most_reliable']['name']} ({summary['most_reliable']['success_rate']:.1%})")
        
        print(f"\nDetailed Results:")
        for backend_name, result in results['detailed_results'].items():
            print(f"\n  {backend_name.upper()}:")
            print(f"    Success Rate: {result['successful_runs']}/{result['num_runs']} ({result['successful_runs']/result['num_runs']:.1%})")
            if result['successful_runs'] > 0:
                print(f"    Average Time: {result['avg_time']:.2f}s ± {result['std_time']:.2f}s")
                print(f"    Real-time Factor: {result['real_time_factor']:.2f}x")
                print(f"    Range: {result['min_time']:.2f}s - {result['max_time']:.2f}s")
                if result['preload_time'] > 0:
                    print(f"    Preload Time: {result['preload_time']:.2f}s")
            if result['errors']:
                print(f"    Errors: {len(result['errors'])}")
        
        print(f"\nPerformance Ranking:")
        for rank_info in summary['performance_ranking']:
            print(f"  {rank_info['rank']}. {rank_info['backend']} - {rank_info['avg_time']:.2f}s ({rank_info['rtf']:.2f}x RTF)")


def main():
    """Main benchmark execution."""
    parser = argparse.ArgumentParser(description='Benchmark dictation backends')
    parser.add_argument('--duration', type=float, default=10.0,
                       help='Audio duration in seconds (default: 10.0)')
    parser.add_argument('--runs', type=int, default=5,
                       help='Number of runs per backend (default: 5)')
    parser.add_argument('--output', type=str, default=None,
                       help='Output JSON file for results')
    
    args = parser.parse_args()
    
    # Create and run benchmark
    benchmark = DictationBenchmark()
    benchmark.setup_backends()
    
    if not benchmark.backends:
        logger.error("No backends available for benchmarking")
        return
    
    results = benchmark.run_benchmark(args.duration, args.runs)
    
    # Print results
    benchmark.print_results(results)
    
    # Save results if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()