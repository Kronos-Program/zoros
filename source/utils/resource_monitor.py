"""
Resource Monitoring Utilities for ZorOS

This module provides comprehensive resource monitoring and leak detection
for the ZorOS dictation system, particularly focused on semaphore leaks
and ThreadPoolExecutor resource management.

Usage:
    from source.utils.resource_monitor import ResourceMonitor
    
    monitor = ResourceMonitor()
    monitor.start_monitoring()
    # ... perform operations ...
    monitor.stop_monitoring()
    monitor.generate_report()

Author: ZorOS Claude Code
Date: 2025-07-05
"""

import os
import sys
import time
import threading
import subprocess
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class ResourceMonitor:
    """Comprehensive resource monitoring for leak detection."""
    
    def __init__(self, log_file: Optional[Path] = None):
        self.monitoring = False
        self.start_time = None
        self.measurements = []
        self.baseline = None
        self.log_file = log_file or Path("resource_monitor.log")
        
        # Configure detailed logging
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup comprehensive logging for resource monitoring."""
        handler = logging.FileHandler(self.log_file)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
    
    def get_system_resources(self) -> Dict[str, Any]:
        """Get comprehensive system resource information."""
        try:
            pid = os.getpid()
            
            # Thread information
            active_threads = threading.active_count()
            thread_names = [t.name for t in threading.enumerate()]
            
            # Process information
            process_info = {}
            try:
                # macOS specific commands
                if sys.platform == 'darwin':
                    # Get semaphore usage
                    result = subprocess.run(['sysctl', 'kern.sysv.semmns'], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        process_info['system_semaphores'] = result.stdout.strip().split()[-1]
                    
                    # Get process threads
                    result = subprocess.run(['ps', '-M', str(pid)], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        process_info['process_threads'] = len(result.stdout.strip().split('\n')) - 1
                    
                    # Get open files
                    result = subprocess.run(['lsof', '-p', str(pid)], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        process_info['open_files'] = len(result.stdout.strip().split('\n')) - 1
                        
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                logger.warning(f"Could not get process info: {e}")
            
            return {
                'timestamp': datetime.now().isoformat(),
                'pid': pid,
                'active_threads': active_threads,
                'thread_names': thread_names,
                'process_info': process_info
            }
            
        except Exception as e:
            logger.error(f"Error getting system resources: {e}")
            return {'error': str(e), 'timestamp': datetime.now().isoformat()}
    
    def start_monitoring(self, interval: float = 1.0):
        """Start continuous resource monitoring."""
        if self.monitoring:
            logger.warning("Monitoring already active")
            return
        
        self.monitoring = True
        self.start_time = time.time()
        self.baseline = self.get_system_resources()
        self.measurements = [self.baseline]
        
        logger.info("Started resource monitoring")
        logger.info(f"Baseline: {self.baseline}")
        
        def monitor_loop():
            while self.monitoring:
                try:
                    measurement = self.get_system_resources()
                    self.measurements.append(measurement)
                    
                    # Log significant changes
                    if len(self.measurements) > 1:
                        prev = self.measurements[-2]
                        current = measurement
                        
                        thread_diff = current.get('active_threads', 0) - prev.get('active_threads', 0)
                        if abs(thread_diff) > 0:
                            logger.info(f"Thread count change: {thread_diff} (now {current.get('active_threads')})")
                    
                    time.sleep(interval)
                    
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")
        
        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop resource monitoring and capture final state."""
        if not self.monitoring:
            logger.warning("Monitoring not active")
            return
        
        self.monitoring = False
        
        # Wait for monitor thread to finish
        if hasattr(self, 'monitor_thread'):
            self.monitor_thread.join(timeout=2.0)
        
        # Capture final measurement
        final_measurement = self.get_system_resources()
        self.measurements.append(final_measurement)
        
        logger.info("Stopped resource monitoring")
        logger.info(f"Final state: {final_measurement}")
    
    def detect_leaks(self) -> Dict[str, Any]:
        """Analyze measurements for resource leaks."""
        if len(self.measurements) < 2:
            return {'error': 'Insufficient measurements for leak detection'}
        
        baseline = self.measurements[0]
        final = self.measurements[-1]
        
        leaks = {
            'baseline': baseline,
            'final': final,
            'duration': time.time() - (self.start_time or 0),
            'leaks_detected': False,
            'issues': []
        }
        
        # Check thread count increase
        baseline_threads = baseline.get('active_threads', 0)
        final_threads = final.get('active_threads', 0)
        thread_increase = final_threads - baseline_threads
        
        if thread_increase > 2:  # Allow some variance
            leaks['leaks_detected'] = True
            leaks['issues'].append({
                'type': 'thread_leak',
                'increase': thread_increase,
                'baseline': baseline_threads,
                'final': final_threads
            })
        
        # Check for thread name patterns that suggest leaks
        baseline_names = set(baseline.get('thread_names', []))
        final_names = set(final.get('thread_names', []))
        new_threads = final_names - baseline_names
        
        suspicious_patterns = ['ThreadPoolExecutor', 'concurrent.futures', 'queue']
        suspicious_threads = [t for t in new_threads 
                            if any(pattern in t for pattern in suspicious_patterns)]
        
        if suspicious_threads:
            leaks['leaks_detected'] = True
            leaks['issues'].append({
                'type': 'suspicious_threads',
                'threads': suspicious_threads
            })
        
        # Check process-level metrics if available
        if (baseline.get('process_info') and final.get('process_info')):
            baseline_proc = baseline['process_info']
            final_proc = final['process_info']
            
            # Check file descriptor increase
            baseline_files = baseline_proc.get('open_files', 0)
            final_files = final_proc.get('open_files', 0)
            if isinstance(baseline_files, int) and isinstance(final_files, int):
                file_increase = final_files - baseline_files
                if file_increase > 10:  # Significant increase
                    leaks['issues'].append({
                        'type': 'file_descriptor_leak',
                        'increase': file_increase,
                        'baseline': baseline_files,
                        'final': final_files
                    })
        
        return leaks
    
    def generate_report(self) -> str:
        """Generate comprehensive monitoring report."""
        leak_analysis = self.detect_leaks()
        
        report_lines = [
            "# Resource Monitoring Report",
            f"Generated: {datetime.now().isoformat()}",
            f"Duration: {leak_analysis.get('duration', 0):.2f} seconds",
            f"Measurements: {len(self.measurements)}",
            "",
            "## Leak Detection Results",
            f"Leaks Detected: {'YES' if leak_analysis.get('leaks_detected') else 'NO'}",
            ""
        ]
        
        if leak_analysis.get('issues'):
            report_lines.append("### Issues Found:")
            for issue in leak_analysis['issues']:
                report_lines.append(f"- **{issue['type']}**: {issue}")
            report_lines.append("")
        
        # Baseline vs Final comparison
        baseline = leak_analysis.get('baseline', {})
        final = leak_analysis.get('final', {})
        
        report_lines.extend([
            "## Resource Comparison",
            "| Metric | Baseline | Final | Change |",
            "|--------|----------|-------|--------|"
        ])
        
        metrics = ['active_threads', 'pid']
        for metric in metrics:
            baseline_val = baseline.get(metric, 'N/A')
            final_val = final.get(metric, 'N/A')
            if isinstance(baseline_val, int) and isinstance(final_val, int):
                change = final_val - baseline_val
                change_str = f"+{change}" if change > 0 else str(change)
            else:
                change_str = 'N/A'
            
            report_lines.append(f"| {metric} | {baseline_val} | {final_val} | {change_str} |")
        
        # Thread details
        if baseline.get('thread_names') and final.get('thread_names'):
            baseline_threads = set(baseline['thread_names'])
            final_threads = set(final['thread_names'])
            new_threads = final_threads - baseline_threads
            removed_threads = baseline_threads - final_threads
            
            if new_threads or removed_threads:
                report_lines.extend([
                    "",
                    "## Thread Changes",
                    f"New threads: {list(new_threads)}",
                    f"Removed threads: {list(removed_threads)}"
                ])
        
        # Save detailed data
        report_lines.extend([
            "",
            "## Raw Data",
            f"Full measurement data saved to: {self.log_file.with_suffix('.json')}"
        ])
        
        # Save JSON data
        json_data = {
            'measurements': self.measurements,
            'leak_analysis': leak_analysis,
            'report_generated': datetime.now().isoformat()
        }
        
        with open(self.log_file.with_suffix('.json'), 'w') as f:
            json.dump(json_data, f, indent=2)
        
        return "\n".join(report_lines)
    
    @contextmanager
    def monitor_operation(self, operation_name: str):
        """Context manager for monitoring specific operations."""
        logger.info(f"Starting monitoring for operation: {operation_name}")
        
        pre_state = self.get_system_resources()
        start_time = time.time()
        
        try:
            yield self
        finally:
            end_time = time.time()
            post_state = self.get_system_resources()
            
            duration = end_time - start_time
            thread_change = post_state.get('active_threads', 0) - pre_state.get('active_threads', 0)
            
            logger.info(f"Operation '{operation_name}' completed in {duration:.3f}s")
            logger.info(f"Thread count change: {thread_change}")
            
            if abs(thread_change) > 1:
                logger.warning(f"Significant thread count change in '{operation_name}': {thread_change}")


# Global monitor instance for easy access
_global_monitor = None

def get_global_monitor() -> ResourceMonitor:
    """Get or create global resource monitor instance."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = ResourceMonitor()
    return _global_monitor

def monitor_operation(operation_name: str):
    """Decorator for monitoring operations."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            monitor = get_global_monitor()
            with monitor.monitor_operation(operation_name):
                return func(*args, **kwargs)
        return wrapper
    return decorator


if __name__ == "__main__":
    # Example usage
    monitor = ResourceMonitor()
    monitor.start_monitoring()
    
    # Simulate some work
    time.sleep(2)
    
    monitor.stop_monitoring()
    report = monitor.generate_report()
    print(report)