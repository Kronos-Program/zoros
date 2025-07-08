#!/usr/bin/env python3
"""
Semaphore Leak Diagnostic Tool for ZorOS Intake System

This script provides comprehensive debugging and monitoring for semaphore leaks
in the audio recording and transcription pipeline.

Usage:
    python scripts/diagnose_semaphore_leaks.py
    python scripts/diagnose_semaphore_leaks.py --monitor
    python scripts/diagnose_semaphore_leaks.py --stress-test

Author: ZorOS Claude Code
Date: 2025-07-05
"""

import os
import sys
import time
import threading
import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor
import argparse
import json
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import sounddevice as sd
    import numpy as np
    from source.interfaces.intake.main import Recorder
    from source.dictation_backends.realtime_streaming_backend import RealtimeStreamingBackend
    from source.dictation_backends.queue_based_streaming_backend import QueueBasedStreamingMLXWhisper
except ImportError as e:
    print(f"ERROR: Could not import required modules: {e}")
    print("Please ensure you're running from the project root and dependencies are installed")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('semaphore_leak_diagnosis.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SemaphoreLeakDiagnostic:
    """Comprehensive diagnostic tool for semaphore leak detection."""
    
    def __init__(self):
        self.monitoring = False
        self.leak_events = []
        self.system_stats = {}
        self.test_results = {}
        
    def get_system_resources(self) -> Dict:
        """Get current system resource usage."""
        try:
            # Get semaphore count (macOS specific)
            result = subprocess.run(['sysctl', 'kern.sysv.semmns'], 
                                  capture_output=True, text=True)
            semaphores_used = None
            if result.returncode == 0:
                semaphores_used = result.stdout.strip().split()[-1]
            
            # Get thread count for current process
            result = subprocess.run(['ps', '-M', str(os.getpid())], 
                                  capture_output=True, text=True)
            thread_count = len(result.stdout.strip().split('\n')) - 1 if result.returncode == 0 else None
            
            # Get open file descriptors
            result = subprocess.run(['lsof', '-p', str(os.getpid())], 
                                  capture_output=True, text=True)
            fd_count = len(result.stdout.strip().split('\n')) - 1 if result.returncode == 0 else None
            
            return {
                'timestamp': datetime.now().isoformat(),
                'pid': os.getpid(),
                'semaphores_used': semaphores_used,
                'thread_count': thread_count,
                'file_descriptors': fd_count,
                'active_threads': threading.active_count()
            }
        except Exception as e:
            logger.error(f"Error getting system resources: {e}")
            return {'error': str(e)}
    
    def test_recorder_lifecycle(self, iterations: int = 5) -> Dict:
        """Test recorder start/stop lifecycle for resource leaks."""
        logger.info(f"Testing recorder lifecycle for {iterations} iterations")
        
        results = {
            'test_name': 'recorder_lifecycle',
            'iterations': iterations,
            'baseline_resources': self.get_system_resources(),
            'iteration_results': [],
            'leaks_detected': False,
            'errors': []
        }
        
        try:
            for i in range(iterations):
                logger.info(f"Recorder test iteration {i+1}/{iterations}")
                iteration_start = self.get_system_resources()
                
                # Create and test recorder
                recorder = Recorder()
                
                try:
                    # Start recording
                    recorder.start()
                    time.sleep(0.5)  # Brief recording
                    
                    # Stop with keep_stream=False
                    temp_path = Path("/tmp/test_recording.wav")
                    recorder.stop(temp_path, keep_stream=False)
                    
                    # Clean up temp file
                    if temp_path.exists():
                        temp_path.unlink()
                        
                except Exception as e:
                    logger.error(f"Recorder test iteration {i+1} failed: {e}")
                    results['errors'].append(f"Iteration {i+1}: {str(e)}")
                    
                    # Force cleanup
                    if hasattr(recorder, 'stream') and recorder.stream:
                        try:
                            recorder.stream.stop()
                            recorder.stream.close()
                            recorder.stream = None
                        except:
                            pass
                
                iteration_end = self.get_system_resources()
                results['iteration_results'].append({
                    'iteration': i+1,
                    'start_resources': iteration_start,
                    'end_resources': iteration_end
                })
                
                # Brief pause between iterations
                time.sleep(0.1)
                
        except Exception as e:
            logger.error(f"Recorder lifecycle test failed: {e}")
            results['errors'].append(f"Test failure: {str(e)}")
        
        # Analyze for leaks
        if len(results['iteration_results']) > 1:
            first_iter = results['iteration_results'][0]['end_resources']
            last_iter = results['iteration_results'][-1]['end_resources']
            
            # Check for increasing thread count
            if (first_iter.get('active_threads') and last_iter.get('active_threads') and
                last_iter['active_threads'] > first_iter['active_threads'] + 2):
                results['leaks_detected'] = True
                results['leak_type'] = 'thread_leak'
        
        results['final_resources'] = self.get_system_resources()
        return results
    
    def test_streaming_backend_lifecycle(self, backend_type: str = 'realtime') -> Dict:
        """Test streaming backend lifecycle for resource leaks."""
        logger.info(f"Testing {backend_type} streaming backend lifecycle")
        
        results = {
            'test_name': f'{backend_type}_streaming_lifecycle',
            'backend_type': backend_type,
            'baseline_resources': self.get_system_resources(),
            'errors': [],
            'leaks_detected': False
        }
        
        try:
            if backend_type == 'realtime':
                backend = RealtimeStreamingBackend(model_name="small")
            else:
                backend = QueueBasedStreamingMLXWhisper(model_name="small")
            
            # Test streaming lifecycle
            results['after_creation'] = self.get_system_resources()
            
            # Start streaming
            if hasattr(backend, 'start_streaming'):
                backend.start_streaming()
                results['after_start'] = self.get_system_resources()
                
                time.sleep(1.0)  # Let it run briefly
                
                # Stop streaming
                if hasattr(backend, 'stop_streaming'):
                    backend.stop_streaming()
                results['after_stop'] = self.get_system_resources()
            
            # Cleanup
            if hasattr(backend, 'cleanup'):
                backend.cleanup()
            results['after_cleanup'] = self.get_system_resources()
            
        except Exception as e:
            logger.error(f"Streaming backend test failed: {e}")
            results['errors'].append(str(e))
        
        return results
    
    def test_executor_cleanup(self, iterations: int = 3) -> Dict:
        """Test ThreadPoolExecutor cleanup for resource leaks."""
        logger.info(f"Testing ThreadPoolExecutor cleanup for {iterations} iterations")
        
        results = {
            'test_name': 'executor_cleanup',
            'iterations': iterations,
            'baseline_resources': self.get_system_resources(),
            'iteration_results': [],
            'errors': []
        }
        
        for i in range(iterations):
            logger.info(f"Executor test iteration {i+1}/{iterations}")
            
            try:
                # Create executor
                executor = ThreadPoolExecutor(max_workers=2)
                
                # Submit some work
                futures = []
                for j in range(5):
                    future = executor.submit(time.sleep, 0.1)
                    futures.append(future)
                
                # Wait for completion
                for future in futures:
                    future.result()
                
                resources_before_shutdown = self.get_system_resources()
                
                # Test different shutdown methods
                if i == 0:
                    # Standard shutdown with wait=True
                    executor.shutdown(wait=True)
                elif i == 1:
                    # Shutdown with wait=False (current intake behavior)
                    executor.shutdown(wait=False)
                else:
                    # Force shutdown with context manager
                    with executor:
                        pass
                
                resources_after_shutdown = self.get_system_resources()
                
                results['iteration_results'].append({
                    'iteration': i+1,
                    'before_shutdown': resources_before_shutdown,
                    'after_shutdown': resources_after_shutdown,
                    'shutdown_method': ['wait=True', 'wait=False', 'context_manager'][i]
                })
                
            except Exception as e:
                logger.error(f"Executor test iteration {i+1} failed: {e}")
                results['errors'].append(f"Iteration {i+1}: {str(e)}")
            
            time.sleep(0.5)  # Pause between tests
        
        results['final_resources'] = self.get_system_resources()
        return results
    
    def monitor_continuous(self, duration: int = 60):
        """Continuously monitor for resource leaks."""
        logger.info(f"Starting continuous monitoring for {duration} seconds")
        
        self.monitoring = True
        start_time = time.time()
        
        while self.monitoring and (time.time() - start_time) < duration:
            current_resources = self.get_system_resources()
            self.system_stats[time.time()] = current_resources
            
            # Log every 10 seconds
            if len(self.system_stats) % 10 == 0:
                logger.info(f"Resources: threads={current_resources.get('active_threads')}, "
                          f"fds={current_resources.get('file_descriptors')}")
            
            time.sleep(1)
        
        self.monitoring = False
        logger.info("Continuous monitoring completed")
    
    def run_stress_test(self):
        """Run comprehensive stress test to trigger semaphore leaks."""
        logger.info("Running comprehensive stress test")
        
        stress_results = {
            'test_start': datetime.now().isoformat(),
            'baseline': self.get_system_resources(),
            'tests': {}
        }
        
        # Test 1: Recorder lifecycle
        stress_results['tests']['recorder'] = self.test_recorder_lifecycle(iterations=10)
        
        # Test 2: Streaming backend
        stress_results['tests']['realtime_streaming'] = self.test_streaming_backend_lifecycle('realtime')
        stress_results['tests']['queue_streaming'] = self.test_streaming_backend_lifecycle('queue')
        
        # Test 3: Executor cleanup
        stress_results['tests']['executor'] = self.test_executor_cleanup(iterations=5)
        
        stress_results['final_resources'] = self.get_system_resources()
        stress_results['test_end'] = datetime.now().isoformat()
        
        # Save results
        results_file = Path('stress_test_results.json')
        with open(results_file, 'w') as f:
            json.dump(stress_results, f, indent=2)
        
        logger.info(f"Stress test completed. Results saved to {results_file}")
        return stress_results
    
    def generate_report(self) -> str:
        """Generate comprehensive diagnostic report."""
        report = [
            "# ZorOS Semaphore Leak Diagnostic Report",
            f"Generated: {datetime.now().isoformat()}",
            "",
            "## Potential Root Causes",
            "",
            "### 1. **Incomplete Audio Stream Cleanup**",
            "- **Location**: `source/interfaces/intake/main.py:826-845` (Recorder.stop)",
            "- **Issue**: Stream may not be properly closed in persistent mode",
            "- **Risk**: High - Direct cause of semaphore leaks",
            "",
            "### 2. **ThreadPoolExecutor Shutdown Issues**", 
            "- **Location**: `source/interfaces/intake/main.py:2585` (closeEvent)",
            "- **Issue**: Using `wait=False` may leave threads running",
            "- **Risk**: Medium - Can cause thread/semaphore accumulation",
            "",
            "### 3. **Streaming Backend Resource Management**",
            "- **Location**: `source/dictation_backends/realtime_streaming_backend.py:366-390`",
            "- **Issue**: Cleanup may not be called consistently", 
            "- **Risk**: Medium - ThreadPoolExecutor in streaming backends",
            "",
            "### 4. **sounddevice Callback Persistence**",
            "- **Location**: `source/interfaces/intake/main.py:786-792` (_callback)",
            "- **Issue**: Callbacks may continue after stream.stop()",
            "- **Risk**: High - Can cause continuous semaphore allocation",
            "",
            "## Recommended Fixes",
            "",
            "### Immediate (High Priority)",
            "1. **Force stream closure in all cases**",
            "2. **Add proper executor shutdown with timeout**", 
            "3. **Implement stream state verification**",
            "4. **Add resource monitoring in debug mode**",
            "",
            "### Medium Priority", 
            "1. **Improve streaming backend cleanup**",
            "2. **Add cleanup verification tests**",
            "3. **Implement resource leak detection**",
            "",
            "## Current Logging State Analysis",
            "",
            f"**Log Files Location**: `/tmp/semaphore_leak_diagnosis.log`",
            f"**Debug Logging**: {'Enabled' if logger.isEnabledFor(logging.DEBUG) else 'Disabled'}",
            f"**Log Handlers**: {len(logger.handlers)} active",
            "",
            "### Logging Gaps",
            "- No resource usage logging in production",
            "- Missing stream state logging",
            "- No executor shutdown logging",
            "- Limited error context in cleanup",
        ]
        
        return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description="Diagnose semaphore leaks in ZorOS")
    parser.add_argument('--monitor', action='store_true', 
                       help='Run continuous monitoring')
    parser.add_argument('--stress-test', action='store_true',
                       help='Run comprehensive stress test')
    parser.add_argument('--duration', type=int, default=60,
                       help='Monitoring duration in seconds')
    
    args = parser.parse_args()
    
    diagnostic = SemaphoreLeakDiagnostic()
    
    if args.monitor:
        diagnostic.monitor_continuous(args.duration)
    elif args.stress_test:
        diagnostic.run_stress_test()
    else:
        # Generate and display report
        report = diagnostic.generate_report()
        print(report)
        
        # Save report
        report_file = Path('semaphore_leak_report.md')
        with open(report_file, 'w') as f:
            f.write(report)
        print(f"\nFull report saved to: {report_file}")


if __name__ == "__main__":
    main()