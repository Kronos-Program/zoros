#!/usr/bin/env python3
"""
Streaming Backend Benchmark Script

This script benchmarks all three MLX Whisper backends:
1. Standard MLX Whisper (baseline)
2. Parallel MLX Whisper (streaming with Metal GPU bug)
3. Queue-based Streaming MLX Whisper (Metal GPU safe)

Spec: docs/streaming_backend_plan.md#performance-testing
Tests: tests/test_transcription_performance.py
Integration: source/dictation_backends/

Usage:
    python scripts/benchmark_streaming_backends.py [audio_file]
    python scripts/benchmark_streaming_backends.py --list-files
    python scripts/benchmark_streaming_backends.py --generate-test 30
"""

import argparse
import json
import time
import statistics
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import sys

# Add source to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from source.dictation_backends import MLXWhisperBackend
from source.dictation_backends.parallel_mlx_whisper_backend import ParallelMLXWhisperBackend
from source.dictation_backends.queue_based_streaming_backend import QueueBasedStreamingBackend
from scripts.audio_file_manager import AudioFileManager


class StreamingBackendBenchmark:
    """Benchmark all three MLX Whisper backends."""
    
    def __init__(self):
        self.audio_manager = AudioFileManager()
        self.results: Dict[str, List[Dict]] = {}
        self.model = "small"  # Use small model for faster testing
        
    def get_test_audio_files(self) -> List[Path]:
        """Get available test audio files."""
        test_files = []
        
        # Check test assets directory
        test_assets = Path("tests/assets")
        if test_assets.exists():
            test_files.extend(test_assets.glob("*.wav"))
        
        # Check database dictations
        dictations = self.audio_manager.list_dictations_from_db()
        for dictation in dictations[:5]:  # Use first 5 dictations
            if dictation['file_exists'] and dictation['audio_path']:
                test_files.append(Path(dictation['audio_path']))
        
        return sorted(test_files, key=lambda f: f.stat().st_size)[:3]  # Use 3 smallest files
    
    def benchmark_backend(self, backend_name: str, backend_class, audio_file: Path, model: str = "small") -> Dict:
        """Benchmark a single backend with a single audio file."""
        print(f"🔍 Benchmarking {backend_name} with {audio_file.name}")
        
        try:
            # Initialize backend
            init_start = time.time()
            backend = backend_class(model)
            init_time = time.time() - init_start
            
            # Transcribe
            transcribe_start = time.time()
            result = backend.transcribe(str(audio_file))
            transcribe_time = time.time() - transcribe_start
            
            # Calculate metrics
            audio_duration = self.audio_manager.get_audio_duration(audio_file)
            speedup = audio_duration / transcribe_time if transcribe_time > 0 else 0
            words_per_second = len(result.split()) / transcribe_time if transcribe_time > 0 else 0
            
            benchmark_result = {
                'backend': backend_name,
                'audio_file': audio_file.name,
                'audio_duration': audio_duration,
                'audio_size_kb': audio_file.stat().st_size / 1024,
                'init_time': init_time,
                'transcribe_time': transcribe_time,
                'total_time': init_time + transcribe_time,
                'speedup': speedup,
                'words_per_second': words_per_second,
                'result_length': len(result),
                'result_preview': result[:100] + "..." if len(result) > 100 else result,
                'success': True,
                'error': None
            }
            
            print(f"✅ {backend_name}: {transcribe_time:.2f}s ({speedup:.1f}x speedup)")
            return benchmark_result
            
        except Exception as e:
            print(f"❌ {backend_name} failed: {e}")
            return {
                'backend': backend_name,
                'audio_file': audio_file.name,
                'audio_duration': self.audio_manager.get_audio_duration(audio_file),
                'audio_size_kb': audio_file.stat().st_size / 1024,
                'init_time': 0,
                'transcribe_time': 0,
                'total_time': 0,
                'speedup': 0,
                'words_per_second': 0,
                'result_length': 0,
                'result_preview': "",
                'success': False,
                'error': str(e)
            }
    
    def run_benchmarks(self, audio_files: List[Path], model: str = "small") -> List[Dict]:
        """Run benchmarks for all backends with all audio files."""
        print(f"🚀 Starting benchmarks with {len(audio_files)} audio files")
        print(f"📊 Model: {model}")
        print("=" * 80)
        
        backends = [
            ("StandardMLXWhisper", MLXWhisperBackend),
            ("ParallelMLXWhisper", ParallelMLXWhisperBackend),
            ("QueueBasedStreamingMLXWhisper", QueueBasedStreamingBackend),
        ]
        
        all_results = []
        
        for audio_file in audio_files:
            print(f"\n🎵 Testing with: {audio_file.name}")
            print(f"   Duration: {self.audio_manager.get_audio_duration(audio_file):.1f}s")
            print(f"   Size: {audio_file.stat().st_size / 1024:.1f} KB")
            print("-" * 60)
            
            for backend_name, backend_class in backends:
                result = self.benchmark_backend(backend_name, backend_class, audio_file, model)
                all_results.append(result)
                
                # Add small delay between backends to avoid GPU conflicts
                time.sleep(1)
        
        return all_results
    
    def analyze_results(self, results: List[Dict]) -> Dict:
        """Analyze benchmark results and generate statistics."""
        print(f"\n📈 Analyzing {len(results)} benchmark results")
        
        # Group results by backend
        backend_results = {}
        for result in results:
            backend = result['backend']
            if backend not in backend_results:
                backend_results[backend] = []
            backend_results[backend].append(result)
        
        analysis = {
            'summary': {},
            'detailed_results': results,
            'recommendations': []
        }
        
        for backend, backend_data in backend_results.items():
            successful_runs = [r for r in backend_data if r['success']]
            
            if successful_runs:
                # Calculate statistics
                transcribe_times = [r['transcribe_time'] for r in successful_runs]
                speedups = [r['speedup'] for r in successful_runs]
                words_per_second = [r['words_per_second'] for r in successful_runs]
                
                summary = {
                    'total_runs': len(backend_data),
                    'successful_runs': len(successful_runs),
                    'success_rate': len(successful_runs) / len(backend_data) * 100,
                    'avg_transcribe_time': statistics.mean(transcribe_times),
                    'min_transcribe_time': min(transcribe_times),
                    'max_transcribe_time': max(transcribe_times),
                    'avg_speedup': statistics.mean(speedups),
                    'avg_words_per_second': statistics.mean(words_per_second),
                    'errors': [r['error'] for r in backend_data if not r['success']]
                }
            else:
                summary = {
                    'total_runs': len(backend_data),
                    'successful_runs': 0,
                    'success_rate': 0,
                    'avg_transcribe_time': 0,
                    'min_transcribe_time': 0,
                    'max_transcribe_time': 0,
                    'avg_speedup': 0,
                    'avg_words_per_second': 0,
                    'errors': [r['error'] for r in backend_data if not r['success']]
                }
            
            analysis['summary'][backend] = summary
        
        # Generate recommendations
        successful_backends = [b for b, s in analysis['summary'].items() if s['success_rate'] > 0]
        
        if successful_backends:
            fastest_backend = max(successful_backends, 
                                key=lambda b: analysis['summary'][b]['avg_speedup'])
            most_reliable_backend = max(successful_backends,
                                      key=lambda b: analysis['summary'][b]['success_rate'])
            
            analysis['recommendations'].append(f"Fastest backend: {fastest_backend}")
            analysis['recommendations'].append(f"Most reliable backend: {most_reliable_backend}")
            
            # Check for Metal GPU issues
            parallel_results = analysis['summary'].get('ParallelMLXWhisper', {})
            if parallel_results.get('success_rate', 0) < 50:
                analysis['recommendations'].append("⚠️ ParallelMLXWhisper shows Metal GPU issues - use QueueBasedStreamingMLXWhisper")
        
        return analysis
    
    def print_summary(self, analysis: Dict) -> None:
        """Print a formatted summary of benchmark results."""
        print("\n" + "=" * 80)
        print("📊 BENCHMARK SUMMARY")
        print("=" * 80)
        
        for backend, summary in analysis['summary'].items():
            print(f"\n🔧 {backend}")
            print(f"   Success Rate: {summary['success_rate']:.1f}% ({summary['successful_runs']}/{summary['total_runs']})")
            
            if summary['successful_runs'] > 0:
                print(f"   Avg Transcribe Time: {summary['avg_transcribe_time']:.2f}s")
                print(f"   Time Range: {summary['min_transcribe_time']:.2f}s - {summary['max_transcribe_time']:.2f}s")
                print(f"   Avg Speedup: {summary['avg_speedup']:.1f}x")
                print(f"   Avg Words/Second: {summary['avg_words_per_second']:.1f}")
            
            if summary['errors']:
                print(f"   Errors: {len(summary['errors'])}")
                for error in summary['errors'][:2]:  # Show first 2 errors
                    print(f"     - {error[:80]}...")
        
        if analysis['recommendations']:
            print(f"\n💡 RECOMMENDATIONS")
            for rec in analysis['recommendations']:
                print(f"   {rec}")
    
    def save_results(self, analysis: Dict, output_file: str = "artifacts/streaming_benchmark_results.json") -> None:
        """Save benchmark results to JSON file."""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Add timestamp
        analysis['timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S')
        analysis['model'] = self.model
        
        with open(output_path, 'w') as f:
            json.dump(analysis, f, indent=2)
        
        print(f"\n💾 Results saved to: {output_path}")
    
    def list_available_files(self) -> None:
        """List available test audio files."""
        print("📁 Available test audio files:")
        
        # Test assets
        test_assets = Path("tests/assets")
        if test_assets.exists():
            print(f"\n📂 Test Assets ({test_assets}):")
            for file in sorted(test_assets.glob("*.wav")):
                duration = self.audio_manager.get_audio_duration(file)
                size_kb = file.stat().st_size / 1024
                print(f"   {file.name} ({duration:.1f}s, {size_kb:.1f} KB)")
        
        # Database dictations
        dictations = self.audio_manager.list_dictations_from_db()
        if dictations:
            print(f"\n🗄️ Database Dictations:")
            for dictation in dictations[:10]:  # Show first 10
                if dictation['file_exists']:
                    print(f"   {dictation['id'][:8]}... ({dictation['duration']:.1f}s, {dictation['file_size']:.1f} KB)")
    
    def generate_test_audio(self, duration: int) -> Optional[Path]:
        """Generate a test audio file."""
        print(f"🎵 Generating {duration}s test audio file...")
        return self.audio_manager.generate_test_audio(duration)


def main():
    """Main function for the benchmark script."""
    parser = argparse.ArgumentParser(description="Benchmark MLX Whisper streaming backends")
    parser.add_argument("audio_file", nargs="?", help="Specific audio file to test")
    parser.add_argument("--list-files", action="store_true", help="List available test files")
    parser.add_argument("--generate-test", type=int, metavar="SECONDS", help="Generate test audio file")
    parser.add_argument("--model", default="small", choices=["tiny", "small", "medium", "large"], 
                       help="Whisper model to use")
    parser.add_argument("--output", default="artifacts/streaming_benchmark_results.json",
                       help="Output file for results")
    
    args = parser.parse_args()
    
    benchmark = StreamingBackendBenchmark()
    benchmark.model = args.model
    
    if args.list_files:
        benchmark.list_available_files()
        return
    
    if args.generate_test:
        test_file = benchmark.generate_test_audio(args.generate_test)
        print(f"✅ Generated test file: {test_file}")
        return
    
    # Get audio files to test
    if args.audio_file:
        audio_files = [Path(args.audio_file)]
        if not audio_files[0].exists():
            print(f"❌ Audio file not found: {args.audio_file}")
            return
    else:
        audio_files = benchmark.get_test_audio_files()
        if not audio_files:
            print("❌ No test audio files found. Use --list-files to see available files.")
            return
    
    print(f"🎯 Testing with {len(audio_files)} audio files")
    for file in audio_files:
        print(f"   - {file.name}")
    
    # Run benchmarks
    results = benchmark.run_benchmarks(audio_files, args.model)
    
    # Analyze results
    analysis = benchmark.analyze_results(results)
    
    # Print summary
    benchmark.print_summary(analysis)
    
    # Save results
    benchmark.save_results(analysis, args.output)


if __name__ == "__main__":
    main() 