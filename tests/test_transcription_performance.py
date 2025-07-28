#!/usr/bin/env python3
"""Performance tests for the transcription pipeline.

This module tests the performance of the complete transcription workflow
using audio files from tests/assets, measuring various metrics including
transcription time, memory usage, and pipeline efficiency.

Spec: docs/requirements/dictation_requirements.md#transcription-pipeline
Integration: source/interfaces/intake/main.py#transcribe_audio
"""
import json
import tempfile
import unittest
import pytest
from pathlib import Path
from time import perf_counter
from typing import Dict, List, Any, Optional
import sqlite3
import shutil

pytest.skip("Performance tests not suitable for headless CI", allow_module_level=True)

# Try to import the modules we want to test
try:
    from scripts.standalone_performance_analysis import transcribe_with_timing
    # Use the standalone transcription function
    def transcribe_audio(wav_path: str, backend: str = "StandardWhisper", model: str = "small") -> str:
        timing_report = transcribe_with_timing(wav_path, backend, model)
        return timing_report.get('transcript_preview', '').replace('...', '')
except ImportError:
    # Fallback to mock functions if imports fail
    def transcribe_audio(wav_path: str, backend: str = "StandardWhisper", model: str = "small") -> str:
        return f"Mock transcription for {wav_path} using {backend}/{model}"

def insert_intake(content: str, audio_path: Optional[str], correction: Optional[str] = None, fiber_type: str = "dictation", db: Optional[Path] = None, **kwargs) -> str:
    return "mock-fiber-id"

def _ensure_db(db: Optional[Path] = None) -> None:
    pass

DB_PATH = Path("mock_db.db")

# Try to import optional modules
try:
    AUDIO_DIR = Path("audio")
    DICTATIONS_DIR = Path("dictations")
except NameError:
    AUDIO_DIR = Path("audio")
    DICTATIONS_DIR = Path("dictations")


def _mem_usage_mb() -> float:
    """Return current process memory in MB."""
    try:
        import psutil
        return psutil.Process().memory_info().rss / 1024 / 1024
    except Exception:
        try:
            import resource
            import sys
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            if sys.platform == "darwin":
                rss /= 1024 * 1024
            else:
                rss /= 1024
            return float(rss)
        except Exception:
            return 0.0  # Fallback if we can't measure memory


class TestTranscriptionPerformance(unittest.TestCase):
    """Performance tests for transcription pipeline."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directories for testing
        self.test_db = Path(tempfile.mktemp(suffix='.db'))
        self.test_audio_dir = Path(tempfile.mkdtemp())
        self.test_dictations_dir = Path(tempfile.mkdtemp())
        
        # Ensure test database is created
        _ensure_db(self.test_db)
        
        # Get test audio files
        self.assets_dir = Path(__file__).parent / "assets"
        self.test_audio_files = list(self.assets_dir.glob("*.wav"))
        
        if not self.test_audio_files:
            self.skipTest("No test audio files found in tests/assets/")
        
        # Configuration attributes (will be set by test runner)
        self.mode_config = getattr(self, 'mode_config', {})
        self.global_config = getattr(self, 'global_config', {})
        self.intake_settings = getattr(self, 'intake_settings', {})
    
    def tearDown(self):
        """Clean up test environment."""
        # Clean up test files
        if self.test_db.exists():
            self.test_db.unlink()
        if self.test_audio_dir.exists():
            shutil.rmtree(self.test_audio_dir)
        if self.test_dictations_dir.exists():
            shutil.rmtree(self.test_dictations_dir)
    
    def test_main_configuration_performance(self):
        """Test performance of the main production configuration.
        
        This test uses the configuration from config/intake_settings.json
        to test the main production setup with MLXWhisper and large-v3-turbo.
        """
        self.setUp()  # Ensure setup is called
        print("\n=== Main Configuration Performance Test ===")
        
        if not self.intake_settings:
            self.skipTest("No intake settings provided for main configuration test")
        
        backend = self.intake_settings.get("WhisperBackend", "MLXWhisper")
        model = self.intake_settings.get("WhisperModel", "large-v3-turbo")
        
        print(f"Testing main configuration: {backend}/{model}")
        
        # Use the first test audio file
        audio_file = self.test_audio_files[0]
        print(f"Testing with: {audio_file.name}")
        
        try:
            # Measure transcription time
            transcription_start = perf_counter()
            transcript = transcribe_audio(str(audio_file), backend, model)
            transcription_time = perf_counter() - transcription_start
            
            # Measure memory usage
            mem_before = _mem_usage_mb()
            mem_after = _mem_usage_mb()
            memory_used = mem_after - mem_before
            
            # Calculate metrics
            transcript_length = len(transcript)
            words_per_second = transcript_length / transcription_time if transcription_time > 0 else 0
            
            result = {
                'configuration': 'main',
                'backend': backend,
                'model': model,
                'audio_file': audio_file.name,
                'audio_size_kb': audio_file.stat().st_size / 1024,
                'transcription_time': transcription_time,
                'memory_used_mb': memory_used,
                'transcript_length': transcript_length,
                'words_per_second': words_per_second,
                'success': bool(transcript),
                'transcript_preview': transcript[:100] + "..." if transcript else "",
                'intake_settings': self.intake_settings
            }
            
            print(f"  Transcription: {transcription_time:.2f}s")
            print(f"  Memory: {memory_used:.1f}MB")
            print(f"  Length: {transcript_length}")
            print(f"  WPS: {words_per_second:.1f}")
            
            # Save results
            artifacts_dir = Path(self.global_config.get("test_parameters", {}).get("artifacts_directory", "artifacts"))
            artifacts_dir.mkdir(exist_ok=True)
            
            results_file = artifacts_dir / "main_performance_results.json"
            with open(results_file, 'w') as f:
                json.dump(result, f, indent=2)
            
            print(f"\nMain configuration results saved to: {results_file}")
            
            # Assertions
            self.assertGreater(len(transcript), 0, "No transcript was generated")
            self.assertLess(transcription_time, 300, f"Transcription took too long: {transcription_time:.2f}s")
            
        except Exception as e:
            print(f"Main configuration test failed: {e}")
            self.fail(f"Main configuration test failed: {e}")
    
    def test_transcription_backend_performance(self):
        """Test performance of different transcription backends."""
        print("\n=== Transcription Backend Performance Test ===")
        
        # Use configuration if available, otherwise use defaults
        backends = self.mode_config.get("backends", ["StandardWhisper", "FasterWhisper", "WhisperCPP", "MLXWhisper"])
        models = self.mode_config.get("models", ["tiny", "small", "medium"])
        
        results = []
        
        for audio_file in self.test_audio_files:
            print(f"\nTesting audio file: {audio_file.name}")
            
            # Get audio file info
            audio_size = audio_file.stat().st_size
            print(f"Audio file size: {audio_size / 1024:.1f} KB")
            
            for backend in backends:
                for model in models:
                    print(f"  Testing {backend}/{model}...")
                    
                    try:
                        # Measure memory before
                        mem_before = _mem_usage_mb()
                        
                        # Measure transcription time
                        start_time = perf_counter()
                        transcript = transcribe_audio(str(audio_file), backend, model)
                        transcription_time = perf_counter() - start_time
                        
                        # Measure memory after
                        mem_after = _mem_usage_mb()
                        memory_used = mem_after - mem_before
                        
                        # Calculate metrics
                        transcript_length = len(transcript)
                        words_per_second = transcript_length / transcription_time if transcription_time > 0 else 0
                        
                        result = {
                            'audio_file': audio_file.name,
                            'audio_size_kb': audio_size / 1024,
                            'backend': backend,
                            'model': model,
                            'transcription_time': transcription_time,
                            'memory_used_mb': memory_used,
                            'transcript_length': transcript_length,
                            'words_per_second': words_per_second,
                            'success': bool(transcript),
                            'transcript_preview': transcript[:100] + "..." if transcript else ""
                        }
                        
                        results.append(result)
                        
                        print(f"    Time: {transcription_time:.2f}s, Memory: {memory_used:.1f}MB, "
                              f"Length: {transcript_length}, WPS: {words_per_second:.1f}")
                        
                    except Exception as e:
                        print(f"    Failed: {e}")
                        results.append({
                            'audio_file': audio_file.name,
                            'backend': backend,
                            'model': model,
                            'error': str(e),
                            'success': False
                        })
        
        # Save results to file
        artifacts_dir = Path(self.global_config.get("test_parameters", {}).get("artifacts_directory", "artifacts"))
        artifacts_dir.mkdir(exist_ok=True)
        
        results_file = artifacts_dir / "transcription_performance_results.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\nResults saved to: {results_file}")
        
        # Assert that at least some transcriptions succeeded
        successful_results = [r for r in results if r.get('success', False)]
        self.assertGreater(len(successful_results), 0, "No transcriptions succeeded")
        
        # Print summary
        print(f"\n=== Performance Summary ===")
        print(f"Total tests: {len(results)}")
        print(f"Successful: {len(successful_results)}")
        print(f"Failed: {len(results) - len(successful_results)}")
        
        if successful_results:
            avg_time = sum(r['transcription_time'] for r in successful_results) / len(successful_results)
            avg_memory = sum(r['memory_used_mb'] for r in successful_results) / len(successful_results)
            print(f"Average transcription time: {avg_time:.2f}s")
            print(f"Average memory usage: {avg_memory:.1f}MB")
    
    def test_complete_pipeline_performance(self):
        """Test performance of the complete intake pipeline."""
        print("\n=== Complete Pipeline Performance Test ===")
        
        # Use the first test audio file
        audio_file = self.test_audio_files[0]
        print(f"Testing with: {audio_file.name}")
        
        pipeline_results = []
        
        # Test different backends
        backends = ["StandardWhisper", "FasterWhisper"]
        
        for backend in backends:
            print(f"\nTesting {backend} pipeline...")
            
            try:
                # Step 1: Measure transcription time
                transcription_start = perf_counter()
                transcript = transcribe_audio(str(audio_file), backend, "small")
                transcription_time = perf_counter() - transcription_start
                
                # Step 2: Measure database insertion time
                db_start = perf_counter()
                fiber_id = insert_intake(
                    content=transcript,
                    audio_path=str(audio_file),
                    correction=transcript,
                    fiber_type="dictation",
                    db=self.test_db,
                    submitted=False
                )
                db_time = perf_counter() - db_start
                
                # Step 3: Measure file operations (simulate audio copy)
                file_start = perf_counter()
                temp_audio = self.test_audio_dir / f"{fiber_id}.wav"
                shutil.copy(audio_file, temp_audio)
                file_time = perf_counter() - file_start
                
                # Step 4: Measure total pipeline time
                total_time = transcription_time + db_time + file_time
                
                result = {
                    'backend': backend,
                    'transcription_time': transcription_time,
                    'database_time': db_time,
                    'file_operations_time': file_time,
                    'total_pipeline_time': total_time,
                    'transcript_length': len(transcript),
                    'success': bool(transcript)
                }
                
                pipeline_results.append(result)
                
                print(f"  Transcription: {transcription_time:.2f}s")
                print(f"  Database: {db_time:.3f}s")
                print(f"  File ops: {file_time:.3f}s")
                print(f"  Total: {total_time:.2f}s")
                
            except Exception as e:
                print(f"  Pipeline failed: {e}")
                pipeline_results.append({
                    'backend': backend,
                    'error': str(e),
                    'success': False
                })
        
        # Save pipeline results
        pipeline_file = Path("artifacts") / "pipeline_performance_results.json"
        with open(pipeline_file, 'w') as f:
            json.dump(pipeline_results, f, indent=2)
        
        print(f"\nPipeline results saved to: {pipeline_file}")
        
        # Assertions
        successful_pipelines = [r for r in pipeline_results if r.get('success', False)]
        self.assertGreater(len(successful_pipelines), 0, "No pipelines succeeded")
        
        if successful_pipelines:
            # Check that transcription is the dominant time component
            for result in successful_pipelines:
                transcription_ratio = result['transcription_time'] / result['total_pipeline_time']
                self.assertGreater(transcription_ratio, 0.5, 
                                 f"Transcription should be >50% of total time, got {transcription_ratio:.1%}")
    
    def test_memory_usage_over_multiple_transcriptions(self):
        """Test memory usage over multiple consecutive transcriptions."""
        print("\n=== Memory Usage Over Multiple Transcriptions ===")
        
        audio_file = self.test_audio_files[0]
        backend = "StandardWhisper"
        model = "small"
        
        memory_measurements = []
        
        for i in range(5):  # Test 5 consecutive transcriptions
            print(f"Transcription {i+1}/5...")
            
            # Force garbage collection before measurement
            import gc
            gc.collect()
            
            # Measure memory before
            mem_before = _mem_usage_mb()
            
            # Perform transcription
            start_time = perf_counter()
            transcript = transcribe_audio(str(audio_file), backend, model)
            transcription_time = perf_counter() - start_time
            
            # Measure memory after
            mem_after = _mem_usage_mb()
            memory_delta = mem_after - mem_before
            
            measurement = {
                'iteration': i + 1,
                'memory_before_mb': mem_before,
                'memory_after_mb': mem_after,
                'memory_delta_mb': memory_delta,
                'transcription_time': transcription_time,
                'transcript_length': len(transcript)
            }
            
            memory_measurements.append(measurement)
            
            print(f"  Memory: {mem_before:.1f}MB -> {mem_after:.1f}MB (delta: {memory_delta:+.1f}MB)")
            print(f"  Time: {transcription_time:.2f}s")
        
        # Save memory results
        memory_file = Path("artifacts") / "memory_usage_results.json"
        with open(memory_file, 'w') as f:
            json.dump(memory_measurements, f, indent=2)
        
        print(f"\nMemory results saved to: {memory_file}")
        
        # Check for memory leaks (cumulative memory growth should be reasonable)
        total_memory_growth = sum(m['memory_delta_mb'] for m in memory_measurements)
        self.assertLess(total_memory_growth, 100,  # Should not grow more than 100MB over 5 transcriptions
                       f"Excessive memory growth: {total_memory_growth:.1f}MB")
        
        print(f"Total memory growth: {total_memory_growth:.1f}MB")
    
    def test_backend_availability(self):
        """Test which backends are available on the current system."""
        print("\n=== Backend Availability Test ===")
        
        from backend.services.dictation import get_available_backends, check_backend
        
        available_backends = get_available_backends()
        print(f"Available backends: {available_backends}")
        
        # Test each backend individually
        all_backends = ["StandardWhisper", "FasterWhisper", "WhisperCPP", "MLXWhisper", "OpenAIAPI", "Mock"]
        
        availability_results = {}
        
        for backend in all_backends:
            is_available = check_backend(backend)
            availability_results[backend] = is_available
            print(f"  {backend}: {'✓' if is_available else '✗'}")
        
        # Save availability results
        availability_file = Path("artifacts") / "backend_availability.json"
        with open(availability_file, 'w') as f:
            json.dump(availability_results, f, indent=2)
        
        print(f"\nAvailability results saved to: {availability_file}")
        
        # Assert that at least one backend is available
        self.assertGreater(len(available_backends), 0, "No transcription backends are available")


def run_performance_tests():
    """Run all performance tests and generate a comprehensive report."""
    print("Running ZorOS Transcription Performance Tests")
    print("=" * 50)
    
    # Create artifacts directory
    artifacts_dir = Path("artifacts")
    artifacts_dir.mkdir(exist_ok=True)
    
    # Run tests
    import sys
    from unittest import TextTestRunner, TestLoader
    
    loader = TestLoader()
    suite = loader.loadTestsFromTestCase(TestTranscriptionPerformance)
    
    runner = TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    
    # Generate summary report
    report = {
        'timestamp': __import__('datetime').datetime.now().isoformat(),
        'tests_run': result.testsRun,
        'tests_failed': len(result.failures),
        'tests_errored': len(result.errors),
        'success_rate': (result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun if result.testsRun > 0 else 0
    }
    
    report_file = artifacts_dir / "performance_test_report.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\nPerformance test report saved to: {report_file}")
    print(f"Success rate: {report['success_rate']:.1%}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_performance_tests()
    exit(0 if success else 1) 