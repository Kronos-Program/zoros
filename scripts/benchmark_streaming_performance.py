#!/usr/bin/env python3
"""
Streaming Backend Performance Benchmarking Script

This script performs comprehensive performance testing of all MLX Whisper backends:
- Standard MLX Whisper (baseline)
- StreamingMLXWhisper (parallel processing)
- RealtimeStreamingMLXWhisper (real-time streaming)

Spec: docs/streaming_backend_plan.md#performance-benchmarking
Tests: tests/test_transcription_performance.py
Integration: source/dictation_backends/

Usage:
    python scripts/benchmark_streaming_performance.py [audio_file]
"""

import argparse
import json
import time
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import soundfile as sf

from source.dictation_backends import (
    MLXWhisperBackend,
    get_available_backends,
    check_backend,
)
from source.dictation_backends.streaming_mlx_whisper_backend import StreamingMLXWhisperBackend
from source.dictation_backends.realtime_streaming_backend import RealtimeStreamingBackend


class PerformanceBenchmark:
    """Comprehensive performance benchmarking for MLX Whisper backends."""
    
    def __init__(self, model: str = "small"):
        self.model = model
        self.results: Dict[str, Dict] = {}
        self.available_backends = get_available_backends()
        
        print(f"Available backends: {self.available_backends}")
        print(f"Testing with model: {model}")
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            import psutil
            return psutil.Process().memory_info().rss / 1024 / 1024
        except ImportError:
            return 0.0
    
    def _get_audio_info(self, audio_path: Path) -> Dict:
        """Get audio file information."""
        try:
            info = sf.info(audio_path)
            return {
                "duration": info.duration,
                "sample_rate": info.samplerate,
                "channels": info.channels,
                "file_size_mb": audio_path.stat().st_size / 1024 / 1024,
            }
        except Exception as e:
            print(f"Error getting audio info: {e}")
            return {}
    
    def benchmark_standard_mlx_whisper(self, audio_path: Path) -> Dict:
        """Benchmark standard MLX Whisper backend."""
        print(f"\n=== Benchmarking Standard MLX Whisper ===")
        
        result = {
            "backend": "MLXWhisper",
            "model": self.model,
            "audio_file": str(audio_path),
            "success": False,
            "error": None,
            "timing": {},
            "memory": {},
            "transcript": "",
        }
        
        try:
            # Memory before
            mem_before = self._get_memory_usage()
            
            # Initialize backend
            init_start = time.time()
            backend = MLXWhisperBackend(self.model)
            init_time = time.time() - init_start
            
            # Memory after initialization
            mem_after_init = self._get_memory_usage()
            
            # Transcribe
            transcribe_start = time.time()
            transcript = backend.transcribe(str(audio_path))
            transcribe_time = time.time() - transcribe_start
            
            # Memory after transcription
            mem_after_transcribe = self._get_memory_usage()
            
            # Calculate metrics
            total_time = init_time + transcribe_time
            audio_info = self._get_audio_info(audio_path)
            ratio = audio_info.get("duration", 0) / total_time if total_time > 0 else 0
            
            result.update({
                "success": True,
                "timing": {
                    "initialization": init_time,
                    "transcription": transcribe_time,
                    "total": total_time,
                },
                "memory": {
                    "before": mem_before,
                    "after_init": mem_after_init,
                    "after_transcribe": mem_after_transcribe,
                    "init_delta": mem_after_init - mem_before,
                    "transcribe_delta": mem_after_transcribe - mem_after_init,
                    "total_delta": mem_after_transcribe - mem_before,
                },
                "transcript": transcript,
                "audio_info": audio_info,
                "performance_ratio": ratio,
                "words_per_second": len(transcript.split()) / total_time if total_time > 0 else 0,
            })
            
            print(f"✅ Standard MLX Whisper completed successfully")
            print(f"   Total time: {total_time:.2f}s")
            print(f"   Performance ratio: {ratio:.2f}x")
            print(f"   Memory delta: {result['memory']['total_delta']:.1f} MB")
            
        except Exception as e:
            result["error"] = str(e)
            print(f"❌ Standard MLX Whisper failed: {e}")
            traceback.print_exc()
        
        return result
    
    def benchmark_streaming_mlx_whisper(self, audio_path: Path) -> Dict:
        """Benchmark StreamingMLXWhisper (parallel processing) backend."""
        print(f"\n=== Benchmarking StreamingMLXWhisper (Parallel) ===")
        
        result = {
            "backend": "StreamingMLXWhisper",
            "model": self.model,
            "audio_file": str(audio_path),
            "success": False,
            "error": None,
            "timing": {},
            "memory": {},
            "transcript": "",
            "chunk_info": {},
        }
        
        try:
            # Memory before
            mem_before = self._get_memory_usage()
            
            # Initialize backend
            init_start = time.time()
            backend = StreamingMLXWhisperBackend(
                model_name=self.model,
                chunk_duration=10.0,  # 10-second chunks
                overlap_duration=2.0,  # 2-second overlap
                max_workers=2,  # 2 parallel workers
            )
            init_time = time.time() - init_start
            
            # Memory after initialization
            mem_after_init = self._get_memory_usage()
            
            # Transcribe
            transcribe_start = time.time()
            transcript = backend.transcribe(str(audio_path))
            transcribe_time = time.time() - transcribe_start
            
            # Memory after transcription
            mem_after_transcribe = self._get_memory_usage()
            
            # Calculate metrics
            total_time = init_time + transcribe_time
            audio_info = self._get_audio_info(audio_path)
            ratio = audio_info.get("duration", 0) / total_time if total_time > 0 else 0
            
            result.update({
                "success": True,
                "timing": {
                    "initialization": init_time,
                    "transcription": transcribe_time,
                    "total": total_time,
                },
                "memory": {
                    "before": mem_before,
                    "after_init": mem_after_init,
                    "after_transcribe": mem_after_transcribe,
                    "init_delta": mem_after_init - mem_before,
                    "transcribe_delta": mem_after_transcribe - mem_after_init,
                    "total_delta": mem_after_transcribe - mem_before,
                },
                "transcript": transcript,
                "audio_info": audio_info,
                "performance_ratio": ratio,
                "words_per_second": len(transcript.split()) / total_time if total_time > 0 else 0,
                "chunk_info": {
                    "chunk_duration": 10.0,
                    "overlap_duration": 2.0,
                    "max_workers": 2,
                },
            })
            
            print(f"✅ StreamingMLXWhisper completed successfully")
            print(f"   Total time: {total_time:.2f}s")
            print(f"   Performance ratio: {ratio:.2f}x")
            print(f"   Memory delta: {result['memory']['total_delta']:.1f} MB")
            
        except Exception as e:
            result["error"] = str(e)
            print(f"❌ StreamingMLXWhisper failed: {e}")
            traceback.print_exc()
        
        return result
    
    def benchmark_realtime_streaming_mlx_whisper(self, audio_path: Path) -> Dict:
        """Benchmark RealtimeStreamingMLXWhisper (real-time streaming) backend."""
        print(f"\n=== Benchmarking RealtimeStreamingMLXWhisper (Live Streaming) ===")
        
        result = {
            "backend": "RealtimeStreamingMLXWhisper",
            "model": self.model,
            "audio_file": str(audio_path),
            "success": False,
            "error": None,
            "timing": {},
            "memory": {},
            "transcript": "",
            "chunk_info": {},
        }
        
        try:
            # Memory before
            mem_before = self._get_memory_usage()
            
            # Initialize backend
            init_start = time.time()
            backend = RealtimeStreamingBackend(
                model_name=self.model,
                chunk_duration=5.0,  # 5-second chunks for real-time
                overlap_duration=1.0,  # 1-second overlap
                max_workers=1,  # Single worker for real-time
            )
            init_time = time.time() - init_start
            
            # Memory after initialization
            mem_after_init = self._get_memory_usage()
            
            # Simulate real-time processing by reading audio in chunks
            transcribe_start = time.time()
            
            # Read audio file
            audio_data, sample_rate = sf.read(audio_path)
            if len(audio_data.shape) > 1:
                audio_data = audio_data[:, 0]  # Convert to mono
            
            # Start streaming
            backend.start_streaming()
            
            # Process in chunks (simulate real-time)
            chunk_size = int(5.0 * sample_rate)  # 5-second chunks
            overlap_size = int(1.0 * sample_rate)  # 1-second overlap
            
            chunks_processed = 0
            total_chunks = len(audio_data) // (chunk_size - overlap_size)
            
            for i in range(0, len(audio_data), chunk_size - overlap_size):
                chunk = audio_data[i:i + chunk_size]
                if len(chunk) < chunk_size:
                    # Pad last chunk if needed
                    chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
                
                # Add chunk to backend (simulate real-time)
                current_time = i / sample_rate
                backend.add_audio_data(chunk, current_time)
                chunks_processed += 1
                
                # Small delay to simulate real-time
                time.sleep(0.1)
            
            # Stop streaming and get final result
            transcript = backend.stop_streaming()
            transcribe_time = time.time() - transcribe_start
            
            # Memory after transcription
            mem_after_transcribe = self._get_memory_usage()
            
            # Calculate metrics
            total_time = init_time + transcribe_time
            audio_info = self._get_audio_info(audio_path)
            ratio = audio_info.get("duration", 0) / total_time if total_time > 0 else 0
            
            result.update({
                "success": True,
                "timing": {
                    "initialization": init_time,
                    "transcription": transcribe_time,
                    "total": total_time,
                },
                "memory": {
                    "before": mem_before,
                    "after_init": mem_after_init,
                    "after_transcribe": mem_after_transcribe,
                    "init_delta": mem_after_init - mem_before,
                    "transcribe_delta": mem_after_transcribe - mem_after_init,
                    "total_delta": mem_after_transcribe - mem_before,
                },
                "transcript": transcript,
                "audio_info": audio_info,
                "performance_ratio": ratio,
                "words_per_second": len(transcript.split()) / total_time if total_time > 0 else 0,
                "chunk_info": {
                    "chunk_duration": 5.0,
                    "overlap_duration": 1.0,
                    "max_workers": 1,
                    "chunks_processed": chunks_processed,
                    "total_chunks": total_chunks,
                },
            })
            
            print(f"✅ RealtimeStreamingMLXWhisper completed successfully")
            print(f"   Total time: {total_time:.2f}s")
            print(f"   Performance ratio: {ratio:.2f}x")
            print(f"   Memory delta: {result['memory']['total_delta']:.1f} MB")
            print(f"   Chunks processed: {chunks_processed}")
            
        except Exception as e:
            result["error"] = str(e)
            print(f"❌ RealtimeStreamingMLXWhisper failed: {e}")
            traceback.print_exc()
        
        return result
    
    def run_benchmarks(self, audio_path: Path) -> Dict:
        """Run all benchmarks on the given audio file."""
        print(f"\n{'='*60}")
        print(f"PERFORMANCE BENCHMARKING")
        print(f"Audio file: {audio_path}")
        print(f"Model: {self.model}")
        print(f"{'='*60}")
        
        # Get audio info
        audio_info = self._get_audio_info(audio_path)
        print(f"Audio duration: {audio_info.get('duration', 0):.2f}s")
        print(f"File size: {audio_info.get('file_size_mb', 0):.1f} MB")
        
        # Run benchmarks
        benchmarks = [
            ("MLXWhisper", self.benchmark_standard_mlx_whisper),
            ("StreamingMLXWhisper", self.benchmark_streaming_mlx_whisper),
            ("RealtimeStreamingMLXWhisper", self.benchmark_realtime_streaming_mlx_whisper),
        ]
        
        for name, benchmark_func in benchmarks:
            if check_backend(name):
                result = benchmark_func(audio_path)
                self.results[name] = result
            else:
                print(f"\n⚠️  Backend {name} not available, skipping")
        
        return self.results
    
    def generate_report(self) -> str:
        """Generate a comprehensive performance report."""
        if not self.results:
            return "No benchmark results available."
        
        report = []
        report.append("# MLX Whisper Backend Performance Report")
        report.append("")
        report.append(f"**Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"**Model**: {self.model}")
        report.append("")
        
        # Summary table
        report.append("## Performance Summary")
        report.append("")
        report.append("| Backend | Status | Total Time (s) | Performance Ratio | Memory Delta (MB) | Words/sec |")
        report.append("|---------|--------|----------------|-------------------|-------------------|-----------|")
        
        for name, result in self.results.items():
            if result["success"]:
                status = "✅ Success"
                total_time = result["timing"]["total"]
                ratio = result["performance_ratio"]
                memory_delta = result["memory"]["total_delta"]
                words_per_sec = result["words_per_second"]
                report.append(f"| {name} | {status} | {total_time:.2f} | {ratio:.2f}x | {memory_delta:.1f} | {words_per_sec:.1f} |")
            else:
                status = f"❌ Failed: {result['error']}"
                report.append(f"| {name} | {status} | - | - | - | - |")
        
        report.append("")
        
        # Detailed results
        report.append("## Detailed Results")
        report.append("")
        
        for name, result in self.results.items():
            report.append(f"### {name}")
            report.append("")
            
            if result["success"]:
                report.append(f"- **Status**: ✅ Success")
                report.append(f"- **Total Time**: {result['timing']['total']:.2f}s")
                report.append(f"- **Initialization**: {result['timing']['initialization']:.2f}s")
                report.append(f"- **Transcription**: {result['timing']['transcription']:.2f}s")
                report.append(f"- **Performance Ratio**: {result['performance_ratio']:.2f}x")
                report.append(f"- **Memory Delta**: {result['memory']['total_delta']:.1f} MB")
                report.append(f"- **Words per Second**: {result['words_per_second']:.1f}")
                
                if "chunk_info" in result and result["chunk_info"]:
                    chunk_info = result["chunk_info"]
                    report.append(f"- **Chunk Duration**: {chunk_info.get('chunk_duration', 0)}s")
                    report.append(f"- **Overlap Duration**: {chunk_info.get('overlap_duration', 0)}s")
                    report.append(f"- **Max Workers**: {chunk_info.get('max_workers', 1)}")
                    if "chunks_processed" in chunk_info:
                        report.append(f"- **Chunks Processed**: {chunk_info['chunks_processed']}")
                
                report.append("")
                report.append("**Transcript Preview**:")
                transcript = result["transcript"]
                preview = transcript[:200] + "..." if len(transcript) > 200 else transcript
                report.append(f"```")
                report.append(preview)
                report.append(f"```")
            else:
                report.append(f"- **Status**: ❌ Failed")
                report.append(f"- **Error**: {result['error']}")
            
            report.append("")
        
        # Analysis
        report.append("## Analysis")
        report.append("")
        
        successful_results = [r for r in self.results.values() if r["success"]]
        if len(successful_results) >= 2:
            # Find fastest backend
            fastest = min(successful_results, key=lambda r: r["timing"]["total"])
            report.append(f"- **Fastest Backend**: {fastest['backend']} ({fastest['timing']['total']:.2f}s)")
            
            # Compare with baseline
            baseline = next((r for r in successful_results if r["backend"] == "MLXWhisper"), None)
            if baseline:
                for result in successful_results:
                    if result["backend"] != "MLXWhisper":
                        speedup = baseline["timing"]["total"] / result["timing"]["total"]
                        report.append(f"- **{result['backend']} vs MLXWhisper**: {speedup:.2f}x speedup")
            
            # Memory analysis
            highest_memory = max(successful_results, key=lambda r: r["memory"]["total_delta"])
            report.append(f"- **Highest Memory Usage**: {highest_memory['backend']} ({highest_memory['memory']['total_delta']:.1f} MB)")
        
        report.append("")
        report.append("## Recommendations")
        report.append("")
        
        # Generate recommendations based on results
        if any(r["success"] for r in self.results.values()):
            report.append("1. **For Real-time Use**: Consider RealtimeStreamingMLXWhisper if latency is critical")
            report.append("2. **For Batch Processing**: Use StreamingMLXWhisper for large files if GPU memory allows")
            report.append("3. **For Stability**: Standard MLXWhisper provides the most reliable performance")
            report.append("4. **Memory Management**: Monitor GPU memory usage with streaming backends")
        
        return "\n".join(report)
    
    def save_results(self, output_path: Path) -> None:
        """Save benchmark results to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Add metadata
        results_with_metadata = {
            "metadata": {
                "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
                "model": self.model,
                "available_backends": self.available_backends,
            },
            "results": self.results,
        }
        
        with open(output_path, 'w') as f:
            json.dump(results_with_metadata, f, indent=2)
        
        print(f"\nResults saved to: {output_path}")


def main():
    """Main function for the benchmarking script."""
    parser = argparse.ArgumentParser(description="Benchmark MLX Whisper streaming backends")
    parser.add_argument("audio_file", help="Path to audio file for testing")
    parser.add_argument("--model", default="small", help="Whisper model to use (default: small)")
    parser.add_argument("--output", help="Output file for results (default: artifacts/benchmark_results.json)")
    
    args = parser.parse_args()
    
    audio_path = Path(args.audio_file)
    if not audio_path.exists():
        print(f"Error: Audio file not found: {audio_path}")
        return 1
    
    # Create benchmark instance
    benchmark = PerformanceBenchmark(model=args.model)
    
    # Run benchmarks
    results = benchmark.run_benchmarks(audio_path)
    
    # Generate and print report
    report = benchmark.generate_report()
    print("\n" + "="*60)
    print("PERFORMANCE REPORT")
    print("="*60)
    print(report)
    
    # Save results
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path("artifacts") / f"benchmark_results_{int(time.time())}.json"
    
    benchmark.save_results(output_path)
    
    # Save report
    report_path = output_path.with_suffix('.md')
    with open(report_path, 'w') as f:
        f.write(report)
    
    print(f"Report saved to: {report_path}")
    
    return 0


if __name__ == "__main__":
    exit(main()) 