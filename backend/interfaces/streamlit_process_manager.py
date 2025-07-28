"""
Streamlit Process Manager for ZorOS

This module manages Streamlit application processes to prevent port conflicts
and enable proper lifecycle management.

Key Features:
- Automatic port allocation and conflict resolution
- Process health monitoring and cleanup
- Integration with main UI for window management
- Graceful shutdown procedures

Author: ZorOS Claude Code
Date: 2025-07-05
"""

import subprocess
import signal
import time
import socket
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import threading
import psutil

try:
    from PySide6.QtCore import QObject, Signal, QTimer
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False
    class QObject:
        pass
    class Signal:
        def __init__(self, *args): pass
        def emit(self, *args): pass
        def connect(self, func): pass

logger = logging.getLogger(__name__)


@dataclass
class StreamlitProcess:
    """Information about a running Streamlit process."""
    name: str
    process: subprocess.Popen
    port: int
    script_path: str
    started_at: datetime
    pid: int
    url: str
    
    @property
    def is_alive(self) -> bool:
        """Check if the process is still running."""
        return self.process.poll() is None
    
    @property
    def uptime_seconds(self) -> float:
        """Get process uptime in seconds."""
        return (datetime.now() - self.started_at).total_seconds()


class StreamlitProcessManager(QObject if QT_AVAILABLE else object):
    """Manages Streamlit application processes."""
    
    # Signals for UI integration
    if QT_AVAILABLE:
        processStarted = Signal(str, int)  # name, port
        processStopped = Signal(str)       # name
        processError = Signal(str, str)    # name, error
        healthUpdated = Signal(dict)       # health status
    
    def __init__(self):
        if QT_AVAILABLE:
            super().__init__()
        
        # Process tracking
        self.processes: Dict[str, StreamlitProcess] = {}
        self.port_range = range(8501, 8520)  # Available port range
        self.reserved_ports = set()
        
        # Health monitoring
        if QT_AVAILABLE:
            self.health_timer = QTimer()
            self.health_timer.timeout.connect(self._check_health)
            self.health_timer.setInterval(10000)  # Check every 10 seconds
            self.health_timer.start()
        
        # Cleanup on exit
        import atexit
        atexit.register(self.cleanup_all)
        
        logger.info("Streamlit process manager initialized")
    
    def find_available_port(self) -> Optional[int]:
        """Find an available port in the configured range."""
        for port in self.port_range:
            if port in self.reserved_ports:
                continue
                
            if self._is_port_available(port):
                self.reserved_ports.add(port)
                return port
        
        logger.error("No available ports in range")
        return None
    
    def _is_port_available(self, port: int) -> bool:
        """Check if a port is available for use."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                result = sock.connect_ex(('127.0.0.1', port))
                return result != 0
        except Exception:
            return False
    
    def start_streamlit_app(
        self, 
        script_path: str, 
        app_name: str,
        args: Optional[List[str]] = None,
        port: Optional[int] = None
    ) -> bool:
        """Start a Streamlit application."""
        
        # Check if already running
        if app_name in self.processes:
            if self.processes[app_name].is_alive:
                logger.warning(f"App {app_name} is already running")
                return True
            else:
                # Clean up dead process
                self._cleanup_process(app_name)
        
        # Validate script path
        script = Path(script_path)
        if not script.exists():
            error_msg = f"Script not found: {script_path}"
            logger.error(error_msg)
            if QT_AVAILABLE:
                self.processError.emit(app_name, error_msg)
            return False
        
        # Find available port
        if port is None:
            port = self.find_available_port()
            if port is None:
                error_msg = "No available ports"
                logger.error(error_msg)
                if QT_AVAILABLE:
                    self.processError.emit(app_name, error_msg)
                return False
        
        # Prepare command
        cmd = [
            "python", "-m", "streamlit", "run",
            str(script.absolute()),
            "--server.port", str(port),
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
            "--client.showErrorDetails", "false"
        ]
        
        # Add additional arguments
        if args:
            cmd.extend(["--"] + args)
        
        try:
            # Start process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=script.parent,
                env={"STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false"}
            )
            
            # Wait briefly for startup
            time.sleep(2)
            
            # Check if process started successfully
            if process.poll() is not None:
                # Process died immediately
                stdout, stderr = process.communicate()
                error_msg = f"Process failed to start: {stderr.decode()}"
                logger.error(error_msg)
                if QT_AVAILABLE:
                    self.processError.emit(app_name, error_msg)
                return False
            
            # Create process info
            url = f"http://localhost:{port}"
            streamlit_process = StreamlitProcess(
                name=app_name,
                process=process,
                port=port,
                script_path=str(script),
                started_at=datetime.now(),
                pid=process.pid,
                url=url
            )
            
            # Store process
            self.processes[app_name] = streamlit_process
            
            logger.info(f"Started {app_name} on port {port} (PID: {process.pid})")
            
            if QT_AVAILABLE:
                self.processStarted.emit(app_name, port)
            
            return True
            
        except Exception as e:
            error_msg = f"Failed to start {app_name}: {e}"
            logger.error(error_msg)
            if QT_AVAILABLE:
                self.processError.emit(app_name, error_msg)
            return False
    
    def stop_app(self, app_name: str) -> bool:
        """Stop a Streamlit application."""
        if app_name not in self.processes:
            logger.warning(f"App {app_name} not found")
            return False
        
        process_info = self.processes[app_name]
        
        try:
            # Try graceful shutdown first
            process_info.process.terminate()
            
            # Wait for graceful shutdown
            try:
                process_info.process.wait(timeout=5)
                logger.info(f"Gracefully stopped {app_name}")
            except subprocess.TimeoutExpired:
                # Force kill if needed
                process_info.process.kill()
                process_info.process.wait()
                logger.warning(f"Force killed {app_name}")
            
            # Clean up
            self._cleanup_process(app_name)
            
            if QT_AVAILABLE:
                self.processStopped.emit(app_name)
            
            return True
            
        except Exception as e:
            logger.error(f"Error stopping {app_name}: {e}")
            return False
    
    def restart_app(self, app_name: str) -> bool:
        """Restart a Streamlit application."""
        if app_name not in self.processes:
            logger.warning(f"App {app_name} not found")
            return False
        
        process_info = self.processes[app_name]
        script_path = process_info.script_path
        
        # Stop the app
        if not self.stop_app(app_name):
            return False
        
        # Wait briefly
        time.sleep(1)
        
        # Start again
        return self.start_streamlit_app(script_path, app_name)
    
    def get_app_info(self, app_name: str) -> Optional[StreamlitProcess]:
        """Get information about a running app."""
        return self.processes.get(app_name)
    
    def list_running_apps(self) -> List[StreamlitProcess]:
        """List all running applications."""
        return [proc for proc in self.processes.values() if proc.is_alive]
    
    def is_app_running(self, app_name: str) -> bool:
        """Check if an app is currently running."""
        process = self.processes.get(app_name)
        return process is not None and process.is_alive
    
    def get_app_url(self, app_name: str) -> Optional[str]:
        """Get the URL for a running app."""
        process = self.processes.get(app_name)
        return process.url if process and process.is_alive else None
    
    def cleanup_all(self):
        """Stop all managed processes."""
        logger.info("Cleaning up all Streamlit processes")
        
        for app_name in list(self.processes.keys()):
            self.stop_app(app_name)
        
        # Clear reserved ports
        self.reserved_ports.clear()
    
    def _cleanup_process(self, app_name: str):
        """Clean up process resources."""
        if app_name in self.processes:
            process_info = self.processes[app_name]
            
            # Release port
            if process_info.port in self.reserved_ports:
                self.reserved_ports.remove(process_info.port)
            
            # Remove from tracking
            del self.processes[app_name]
    
    def _check_health(self):
        """Check health of all managed processes."""
        dead_processes = []
        health_status = {}
        
        for app_name, process_info in self.processes.items():
            if not process_info.is_alive:
                dead_processes.append(app_name)
                health_status[app_name] = "dead"
            else:
                # Check if process is responsive
                try:
                    # Try to get process info
                    process = psutil.Process(process_info.pid)
                    cpu_percent = process.cpu_percent()
                    memory_mb = process.memory_info().rss / 1024 / 1024
                    
                    health_status[app_name] = {
                        "status": "running",
                        "uptime": process_info.uptime_seconds,
                        "cpu_percent": cpu_percent,
                        "memory_mb": memory_mb,
                        "port": process_info.port,
                        "url": process_info.url
                    }
                    
                except psutil.NoSuchProcess:
                    dead_processes.append(app_name)
                    health_status[app_name] = "dead"
                except Exception as e:
                    health_status[app_name] = f"error: {e}"
        
        # Clean up dead processes
        for app_name in dead_processes:
            logger.warning(f"Process {app_name} died unexpectedly")
            self._cleanup_process(app_name)
            if QT_AVAILABLE:
                self.processStopped.emit(app_name)
        
        # Emit health update
        if QT_AVAILABLE:
            self.healthUpdated.emit(health_status)
    
    def get_health_status(self) -> Dict[str, any]:
        """Get current health status of all processes."""
        status = {}
        
        for app_name, process_info in self.processes.items():
            if process_info.is_alive:
                try:
                    process = psutil.Process(process_info.pid)
                    status[app_name] = {
                        "status": "running",
                        "pid": process_info.pid,
                        "port": process_info.port,
                        "uptime": process_info.uptime_seconds,
                        "memory_mb": process.memory_info().rss / 1024 / 1024,
                        "url": process_info.url
                    }
                except psutil.NoSuchProcess:
                    status[app_name] = {"status": "dead"}
            else:
                status[app_name] = {"status": "dead"}
        
        return status


# Global instance for easy access
_process_manager = None

def get_streamlit_manager() -> StreamlitProcessManager:
    """Get or create the global Streamlit process manager."""
    global _process_manager
    if _process_manager is None:
        _process_manager = StreamlitProcessManager()
    return _process_manager


# Convenience functions for common ZorOS Streamlit apps
def start_fiberizer_ui() -> bool:
    """Start the fiberizer review UI."""
    manager = get_streamlit_manager()
    script_path = "source/interfaces/streamlit/fiberizer_review.py"
    return manager.start_streamlit_app(script_path, "fiberizer")


def start_feature_tour() -> bool:
    """Start the feature tour UI."""
    manager = get_streamlit_manager()
    script_path = "source/interfaces/streamlit/feature_tour.py"
    return manager.start_streamlit_app(script_path, "feature_tour")


def start_recovery_ui() -> bool:
    """Start the dictation recovery UI."""
    manager = get_streamlit_manager()
    script_path = "source/interfaces/dictation_recovery.py"
    args = ["--streamlit"]
    return manager.start_streamlit_app(script_path, "recovery", args=args)


if __name__ == "__main__":
    # Test the process manager
    import sys
    
    manager = StreamlitProcessManager()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "start":
            app_name = sys.argv[2] if len(sys.argv) > 2 else "test"
            script_path = sys.argv[3] if len(sys.argv) > 3 else "source/interfaces/streamlit/feature_tour.py"
            
            if manager.start_streamlit_app(script_path, app_name):
                print(f"Started {app_name}")
                print(f"URL: {manager.get_app_url(app_name)}")
            else:
                print(f"Failed to start {app_name}")
        
        elif command == "stop":
            app_name = sys.argv[2] if len(sys.argv) > 2 else "test"
            if manager.stop_app(app_name):
                print(f"Stopped {app_name}")
            else:
                print(f"Failed to stop {app_name}")
        
        elif command == "list":
            apps = manager.list_running_apps()
            if apps:
                print("Running Streamlit apps:")
                for app in apps:
                    print(f"  {app.name}: {app.url} (PID: {app.pid})")
            else:
                print("No Streamlit apps running")
        
        elif command == "status":
            status = manager.get_health_status()
            print("Health status:")
            for app_name, health in status.items():
                print(f"  {app_name}: {health}")
    
    else:
        print("Usage: python streamlit_process_manager.py [start|stop|list|status] [app_name] [script_path]")