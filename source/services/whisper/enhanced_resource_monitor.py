"""
Enhanced Resource Monitor for Threading Improvements

This module provides comprehensive resource monitoring and automatic cleanup
for the improved threading architecture. It tracks memory usage, thread counts,
file handles, and provides automatic recovery mechanisms.

Based on: docs/threading_vs_subprocess_analysis.md#threading-improvements
"""

import gc
import logging
import os
import platform
import psutil
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from pathlib import Path

from PySide6.QtCore import QObject, Signal, QTimer

logger = logging.getLogger(__name__)


@dataclass
class ResourceSnapshot:
    """Snapshot of system resources at a point in time."""
    timestamp: float
    memory_usage_mb: float
    memory_percent: float
    thread_count: int
    file_handles: int
    cpu_percent: float
    disk_usage_mb: float
    python_objects: int
    active_timers: int = 0
    qt_objects: int = 0
    
    def __str__(self) -> str:
        return (f"ResourceSnapshot(mem={self.memory_usage_mb:.1f}MB/{self.memory_percent:.1f}%, "
               f"threads={self.thread_count}, files={self.file_handles}, "
               f"cpu={self.cpu_percent:.1f}%, objects={self.python_objects})")


@dataclass
class ResourceThresholds:
    """Configurable thresholds for resource monitoring."""
    max_memory_mb: float = 2048  # 2GB
    max_memory_percent: float = 80.0  # 80% of available memory
    max_thread_count: int = 50
    max_file_handles: int = 1000
    max_cpu_percent: float = 90.0
    max_python_objects: int = 100000
    
    # Growth rate thresholds (per minute)
    max_memory_growth_mb_per_min: float = 100  # 100MB/min
    max_thread_growth_per_min: int = 10
    max_object_growth_per_min: int = 10000


class EnhancedResourceMonitor(QObject):
    """
    Enhanced resource monitor with automatic cleanup and alerting.
    
    Features:
    - Comprehensive resource tracking (memory, threads, files, CPU)
    - Growth rate monitoring to detect leaks
    - Automatic cleanup triggers
    - Qt timer integration for UI responsiveness
    - Historical data for trend analysis
    """
    
    # Signals for resource events
    resource_warning = Signal(str, str)  # resource_type, message
    resource_critical = Signal(str, str)  # resource_type, message
    cleanup_triggered = Signal(str)  # cleanup_type
    resource_recovered = Signal(str)  # resource_type
    
    def __init__(self, 
                 monitor_interval_ms: int = 5000,  # 5 seconds
                 thresholds: Optional[ResourceThresholds] = None):
        super().__init__()
        
        self.monitor_interval_ms = monitor_interval_ms
        self.thresholds = thresholds or ResourceThresholds()
        
        # Resource tracking
        self.snapshots: List[ResourceSnapshot] = []
        self.max_snapshots = 100  # Keep last 100 snapshots (8+ minutes at 5s intervals)
        self.baseline_snapshot: Optional[ResourceSnapshot] = None
        
        # Process handle for psutil
        self.process = psutil.Process()
        
        # Alert state tracking
        self.active_warnings: Dict[str, float] = {}  # resource_type -> first_warning_time
        self.active_criticals: Dict[str, float] = {}
        
        # Cleanup callbacks
        self.cleanup_callbacks: Dict[str, Callable[[], None]] = {}
        
        # Monitoring timer
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._monitor_resources)
        
        # Cleanup timer for aggressive resource management
        self.cleanup_timer = QTimer()
        self.cleanup_timer.timeout.connect(self._perform_automatic_cleanup)
        
        # Track Qt objects if possible
        self.qt_object_tracker = None
        try:
            from PySide6.QtCore import QObjectCleanupHandler
            self.qt_object_tracker = QObjectCleanupHandler()
        except ImportError:
            pass
        
        logger.info(f"Enhanced resource monitor initialized with {monitor_interval_ms}ms interval")
    
    def start_monitoring(self) -> None:
        """Start resource monitoring."""
        # Take baseline snapshot
        self.baseline_snapshot = self._take_snapshot()
        logger.info(f"Baseline resources: {self.baseline_snapshot}")
        
        # Start monitoring
        self.monitor_timer.start(self.monitor_interval_ms)
        
        # Start cleanup timer (less frequent)
        self.cleanup_timer.start(self.monitor_interval_ms * 6)  # Every 30 seconds
        
        logger.info("Resource monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop resource monitoring."""
        self.monitor_timer.stop()
        self.cleanup_timer.stop()
        logger.info("Resource monitoring stopped")
    
    def register_cleanup_callback(self, resource_type: str, callback: Callable[[], None]) -> None:
        """Register a cleanup callback for a specific resource type."""
        self.cleanup_callbacks[resource_type] = callback
        logger.info(f"Registered cleanup callback for {resource_type}")
    
    def force_cleanup(self, resource_type: Optional[str] = None) -> None:
        """Force cleanup for specific resource type or all resources."""
        if resource_type:
            callback = self.cleanup_callbacks.get(resource_type)
            if callback:
                try:
                    callback()
                    self.cleanup_triggered.emit(resource_type)
                    logger.info(f"Forced cleanup for {resource_type}")
                except Exception as e:
                    logger.error(f"Cleanup callback failed for {resource_type}: {e}")
        else:
            # Clean up all registered resources
            for res_type, callback in self.cleanup_callbacks.items():
                try:
                    callback()
                    self.cleanup_triggered.emit(res_type)
                except Exception as e:
                    logger.error(f"Cleanup callback failed for {res_type}: {e}")
            
            # Perform built-in cleanup
            self._perform_gc_cleanup()
    
    def get_current_snapshot(self) -> ResourceSnapshot:
        """Get current resource snapshot."""
        return self._take_snapshot()
    
    def get_resource_trends(self, minutes: int = 5) -> Dict[str, float]:
        """Get resource growth trends over the specified time period."""
        if len(self.snapshots) < 2:
            return {}
        
        cutoff_time = time.time() - (minutes * 60)
        recent_snapshots = [s for s in self.snapshots if s.timestamp >= cutoff_time]
        
        if len(recent_snapshots) < 2:
            return {}
        
        start_snapshot = recent_snapshots[0]
        end_snapshot = recent_snapshots[-1]
        time_diff_minutes = (end_snapshot.timestamp - start_snapshot.timestamp) / 60
        
        if time_diff_minutes <= 0:
            return {}
        
        return {
            "memory_growth_mb_per_min": (end_snapshot.memory_usage_mb - start_snapshot.memory_usage_mb) / time_diff_minutes,
            "thread_growth_per_min": (end_snapshot.thread_count - start_snapshot.thread_count) / time_diff_minutes,
            "object_growth_per_min": (end_snapshot.python_objects - start_snapshot.python_objects) / time_diff_minutes,
            "file_handle_growth_per_min": (end_snapshot.file_handles - start_snapshot.file_handles) / time_diff_minutes
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive monitoring statistics."""
        if not self.snapshots:
            return {"error": "No snapshots available"}
        
        current = self.snapshots[-1]
        trends = self.get_resource_trends()
        
        stats = {
            "current": {
                "memory_mb": current.memory_usage_mb,
                "memory_percent": current.memory_percent,
                "threads": current.thread_count,
                "file_handles": current.file_handles,
                "cpu_percent": current.cpu_percent,
                "python_objects": current.python_objects
            },
            "trends_5min": trends,
            "thresholds": {
                "memory_mb": self.thresholds.max_memory_mb,
                "memory_percent": self.thresholds.max_memory_percent,
                "threads": self.thresholds.max_thread_count,
                "file_handles": self.thresholds.max_file_handles
            },
            "active_warnings": list(self.active_warnings.keys()),
            "active_criticals": list(self.active_criticals.keys()),
            "snapshots_count": len(self.snapshots),
            "monitoring_since": self.baseline_snapshot.timestamp if self.baseline_snapshot else None
        }
        
        if self.baseline_snapshot:
            stats["growth_since_baseline"] = {
                "memory_mb": current.memory_usage_mb - self.baseline_snapshot.memory_usage_mb,
                "threads": current.thread_count - self.baseline_snapshot.thread_count,
                "objects": current.python_objects - self.baseline_snapshot.python_objects
            }
        
        return stats
    
    def _take_snapshot(self) -> ResourceSnapshot:
        """Take a snapshot of current resource usage."""
        try:
            # Memory info
            memory_info = self.process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)  # Convert bytes to MB
            
            # System memory percentage
            sys_memory = psutil.virtual_memory()
            memory_percent = sys_memory.percent
            
            # Thread count
            thread_count = threading.active_count()
            
            # File handles
            try:
                file_handles = len(self.process.open_files())
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                file_handles = 0
            
            # CPU usage
            cpu_percent = self.process.cpu_percent()
            
            # Disk usage for temp files
            temp_dir = Path.cwd() / "audio" / "intake"
            disk_usage_mb = 0
            if temp_dir.exists():
                try:
                    total_size = sum(f.stat().st_size for f in temp_dir.rglob("*") if f.is_file())
                    disk_usage_mb = total_size / (1024 * 1024)
                except OSError:
                    pass
            
            # Python object count
            python_objects = len(gc.get_objects())
            
            # Qt objects count (if available)
            qt_objects = 0
            if self.qt_object_tracker:
                try:
                    # This is a rough estimate - Qt doesn't provide easy object counting
                    qt_objects = len([obj for obj in gc.get_objects() 
                                    if hasattr(obj, '__class__') 
                                    and 'PySide6' in str(type(obj))])
                except Exception:
                    pass
            
            return ResourceSnapshot(
                timestamp=time.time(),
                memory_usage_mb=memory_mb,
                memory_percent=memory_percent,
                thread_count=thread_count,
                file_handles=file_handles,
                cpu_percent=cpu_percent,
                disk_usage_mb=disk_usage_mb,
                python_objects=python_objects,
                qt_objects=qt_objects
            )
            
        except Exception as e:
            logger.error(f"Error taking resource snapshot: {e}")
            # Return a minimal snapshot
            return ResourceSnapshot(
                timestamp=time.time(),
                memory_usage_mb=0,
                memory_percent=0,
                thread_count=threading.active_count(),
                file_handles=0,
                cpu_percent=0,
                disk_usage_mb=0,
                python_objects=len(gc.get_objects())
            )
    
    def _monitor_resources(self) -> None:
        """Monitor resources and check thresholds."""
        snapshot = self._take_snapshot()
        
        # Store snapshot
        self.snapshots.append(snapshot)
        if len(self.snapshots) > self.max_snapshots:
            self.snapshots.pop(0)
        
        # Check thresholds
        self._check_thresholds(snapshot)
        
        # Check growth rates
        self._check_growth_rates()
        
        logger.debug(f"Resource snapshot: {snapshot}")
    
    def _check_thresholds(self, snapshot: ResourceSnapshot) -> None:
        """Check if current resources exceed thresholds."""
        current_time = time.time()
        
        # Memory checks
        if snapshot.memory_usage_mb > self.thresholds.max_memory_mb:
            self._handle_threshold_exceeded("memory_mb", 
                f"Memory usage {snapshot.memory_usage_mb:.1f}MB exceeds limit {self.thresholds.max_memory_mb}MB",
                current_time, is_critical=True)
        elif snapshot.memory_percent > self.thresholds.max_memory_percent:
            self._handle_threshold_exceeded("memory_percent",
                f"Memory usage {snapshot.memory_percent:.1f}% exceeds limit {self.thresholds.max_memory_percent}%",
                current_time, is_critical=False)
        else:
            self._clear_alert("memory_mb")
            self._clear_alert("memory_percent")
        
        # Thread checks
        if snapshot.thread_count > self.thresholds.max_thread_count:
            self._handle_threshold_exceeded("threads",
                f"Thread count {snapshot.thread_count} exceeds limit {self.thresholds.max_thread_count}",
                current_time, is_critical=True)
        else:
            self._clear_alert("threads")
        
        # File handle checks
        if snapshot.file_handles > self.thresholds.max_file_handles:
            self._handle_threshold_exceeded("file_handles",
                f"File handles {snapshot.file_handles} exceeds limit {self.thresholds.max_file_handles}",
                current_time, is_critical=False)
        else:
            self._clear_alert("file_handles")
        
        # CPU checks
        if snapshot.cpu_percent > self.thresholds.max_cpu_percent:
            self._handle_threshold_exceeded("cpu",
                f"CPU usage {snapshot.cpu_percent:.1f}% exceeds limit {self.thresholds.max_cpu_percent}%",
                current_time, is_critical=False)
        else:
            self._clear_alert("cpu")
    
    def _check_growth_rates(self) -> None:
        """Check resource growth rates for potential leaks."""
        trends = self.get_resource_trends(minutes=2)  # Check 2-minute trends for faster detection
        
        if not trends:
            return
        
        current_time = time.time()
        
        # Memory growth rate
        memory_growth = trends.get("memory_growth_mb_per_min", 0)
        if memory_growth > self.thresholds.max_memory_growth_mb_per_min:
            self._handle_threshold_exceeded("memory_growth",
                f"Memory growing at {memory_growth:.1f}MB/min (limit: {self.thresholds.max_memory_growth_mb_per_min}MB/min)",
                current_time, is_critical=False)
        else:
            self._clear_alert("memory_growth")
        
        # Thread growth rate
        thread_growth = trends.get("thread_growth_per_min", 0)
        if thread_growth > self.thresholds.max_thread_growth_per_min:
            self._handle_threshold_exceeded("thread_growth",
                f"Threads growing at {thread_growth:.1f}/min (limit: {self.thresholds.max_thread_growth_per_min}/min)",
                current_time, is_critical=True)
        else:
            self._clear_alert("thread_growth")
        
        # Object growth rate
        object_growth = trends.get("object_growth_per_min", 0)
        if object_growth > self.thresholds.max_object_growth_per_min:
            self._handle_threshold_exceeded("object_growth",
                f"Objects growing at {object_growth:.0f}/min (limit: {self.thresholds.max_object_growth_per_min}/min)",
                current_time, is_critical=False)
        else:
            self._clear_alert("object_growth")
    
    def _handle_threshold_exceeded(self, resource_type: str, message: str, 
                                 current_time: float, is_critical: bool) -> None:
        """Handle threshold exceeded event."""
        if is_critical:
            if resource_type not in self.active_criticals:
                self.active_criticals[resource_type] = current_time
                self.resource_critical.emit(resource_type, message)
                logger.error(f"CRITICAL: {message}")
                
                # Trigger automatic cleanup for critical issues
                self._trigger_emergency_cleanup(resource_type)
            
        else:
            if resource_type not in self.active_warnings:
                self.active_warnings[resource_type] = current_time
                self.resource_warning.emit(resource_type, message)
                logger.warning(f"WARNING: {message}")
    
    def _clear_alert(self, resource_type: str) -> None:
        """Clear active alerts for a resource type."""
        if resource_type in self.active_warnings:
            del self.active_warnings[resource_type]
            self.resource_recovered.emit(resource_type)
            logger.info(f"Resource {resource_type} recovered")
        
        if resource_type in self.active_criticals:
            del self.active_criticals[resource_type]
            self.resource_recovered.emit(resource_type)
            logger.info(f"CRITICAL resource {resource_type} recovered")
    
    def _trigger_emergency_cleanup(self, resource_type: str) -> None:
        """Trigger emergency cleanup for critical resource issues."""
        logger.warning(f"Triggering emergency cleanup for {resource_type}")
        
        # Try specific cleanup first
        if resource_type in self.cleanup_callbacks:
            try:
                self.cleanup_callbacks[resource_type]()
                self.cleanup_triggered.emit(resource_type)
            except Exception as e:
                logger.error(f"Emergency cleanup failed for {resource_type}: {e}")
        
        # Perform general cleanup
        self._perform_gc_cleanup()
        
        # For memory issues, try more aggressive cleanup
        if "memory" in resource_type:
            self._aggressive_memory_cleanup()
    
    def _perform_automatic_cleanup(self) -> None:
        """Perform routine automatic cleanup."""
        # Only perform cleanup if we have some resource pressure
        if self.active_warnings or self.active_criticals:
            logger.debug("Performing automatic cleanup due to resource pressure")
            self._perform_gc_cleanup()
    
    def _perform_gc_cleanup(self) -> None:
        """Perform garbage collection cleanup."""
        try:
            collected = gc.collect()
            logger.debug(f"Garbage collection freed {collected} objects")
        except Exception as e:
            logger.error(f"Garbage collection failed: {e}")
    
    def _aggressive_memory_cleanup(self) -> None:
        """Perform aggressive memory cleanup."""
        try:
            # Force garbage collection
            for _ in range(3):
                gc.collect()
            
            # Clear any caches we can find
            if hasattr(gc, 'clear'):
                gc.clear()
            
            logger.info("Performed aggressive memory cleanup")
            
        except Exception as e:
            logger.error(f"Aggressive memory cleanup failed: {e}")


# Global monitor instance
_resource_monitor: Optional[EnhancedResourceMonitor] = None


def get_resource_monitor() -> EnhancedResourceMonitor:
    """Get the global enhanced resource monitor instance."""
    global _resource_monitor
    if _resource_monitor is None:
        _resource_monitor = EnhancedResourceMonitor()
    return _resource_monitor


def shutdown_resource_monitor() -> None:
    """Shutdown the global resource monitor."""
    global _resource_monitor
    if _resource_monitor:
        _resource_monitor.stop_monitoring()
        _resource_monitor = None