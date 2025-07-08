"""
ZorOS Window Manager

This module provides window management functionality for ZorOS applications,
allowing users to switch between different ZorOS windows and bring them
to focus. It maintains a registry of active ZorOS windows and provides
a unified interface for window management.

Spec: docs/requirements/dictation_requirements.md#window-management
Tests: tests/test_window_manager.py
Integration: source/interfaces/intake/main.py

Features:
- Window registry and tracking
- Focus management
- Window switching
- Process isolation for memory management
"""

import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QMainWindow, QMenu, QSystemTrayIcon

logger = logging.getLogger(__name__)


class ZorosWindowManager(QObject):
    """Manages ZorOS application windows and provides switching functionality.
    
    This class maintains a registry of active ZorOS windows and provides
    methods to switch between them, bring them to focus, and manage
    window states.
    
    Spec: docs/requirements/dictation_requirements.md#window-management
    Tests: tests/test_window_manager.py
    Integration: source/interfaces/intake/main.py
    
    Features:
    - Window registry and tracking
    - Focus management
    - Window switching
    - Process isolation
    """
    
    # Signals
    window_registered = Signal(str, str)  # window_id, window_type
    window_unregistered = Signal(str)     # window_id
    window_focused = Signal(str)          # window_id
    
    def __init__(self):
        super().__init__()
        self.windows: Dict[str, Dict] = {}
        self.system_tray: Optional[QSystemTrayIcon] = None
        self._setup_system_tray()
    
    def _setup_system_tray(self) -> None:
        """Setup system tray icon for window management."""
        try:
            # Check if system tray is supported
            if not QSystemTrayIcon.isSystemTrayAvailable():
                logger.info("System tray not available, skipping tray setup")
                return
                
            self.system_tray = QSystemTrayIcon()
            self.system_tray.setToolTip("ZorOS Window Manager")
            
            # Create context menu
            menu = QMenu()
            self.window_menu = menu.addMenu("ZorOS Windows")
            menu.addSeparator()
            
            # Add actions
            show_all_action = menu.addAction("Show All Windows")
            show_all_action.triggered.connect(self.show_all_windows)
            
            hide_all_action = menu.addAction("Hide All Windows")
            hide_all_action.triggered.connect(self.hide_all_windows)
            
            menu.addSeparator()
            quit_action = menu.addAction("Quit")
            quit_action.triggered.connect(self.quit_all)
            
            self.system_tray.setContextMenu(menu)
            self.system_tray.show()
            
        except Exception as e:
            logger.warning(f"Could not setup system tray: {e}")
            self.system_tray = None
    
    def register_window(self, window: QMainWindow, window_type: str, 
                       window_id: Optional[str] = None) -> str:
        """Register a ZorOS window with the manager.
        
        Args:
            window: The QMainWindow to register
            window_type: Type of window (e.g., 'intake', 'library', 'test')
            window_id: Optional custom ID, generates one if not provided
            
        Returns:
            The window ID
            
        Spec: docs/requirements/dictation_requirements.md#window-registration
        Tests: tests/test_window_manager.py#test_window_registration
        """
        if window_id is None:
            window_id = f"{window_type}_{id(window)}"
        
        self.windows[window_id] = {
            'window': window,
            'type': window_type,
            'title': window.windowTitle(),
            'visible': window.isVisible()
        }
        
        # Connect window signals
        window.destroyed.connect(lambda: self.unregister_window(window_id))
        window.windowTitleChanged.connect(lambda title: self._update_window_title(window_id, title))
        
        # Update system tray menu
        self._update_system_tray_menu()
        
        logger.info(f"Registered window: {window_id} ({window_type})")
        self.window_registered.emit(window_id, window_type)
        
        return window_id
    
    def unregister_window(self, window_id: str) -> None:
        """Unregister a window from the manager.
        
        Args:
            window_id: ID of the window to unregister
            
        Spec: docs/requirements/dictation_requirements.md#window-unregistration
        Tests: tests/test_window_manager.py#test_window_unregistration
        """
        if window_id in self.windows:
            del self.windows[window_id]
            self._update_system_tray_menu()
            logger.info(f"Unregistered window: {window_id}")
            self.window_unregistered.emit(window_id)
    
    def focus_window(self, window_id: str) -> bool:
        """Bring a window to focus.
        
        Args:
            window_id: ID of the window to focus
            
        Returns:
            True if window was focused successfully
            
        Spec: docs/requirements/dictation_requirements.md#window-focus
        Tests: tests/test_window_manager.py#test_window_focus
        """
        if window_id not in self.windows:
            logger.warning(f"Window not found: {window_id}")
            return False
        
        window_info = self.windows[window_id]
        window = window_info['window']
        
        try:
            # Show window if hidden
            if not window.isVisible():
                window.show()
            
            # Bring to front
            window.raise_()
            window.activateWindow()
            
            # Update state
            window_info['visible'] = True
            
            logger.info(f"Focused window: {window_id}")
            self.window_focused.emit(window_id)
            return True
            
        except Exception as e:
            logger.error(f"Error focusing window {window_id}: {e}")
            return False
    
    def show_all_windows(self) -> None:
        """Show all registered ZorOS windows."""
        for window_id in self.windows:
            window_info = self.windows[window_id]
            window = window_info['window']
            if not window.isVisible():
                window.show()
                window_info['visible'] = True
        
        logger.info("Showed all ZorOS windows")
    
    def hide_all_windows(self) -> None:
        """Hide all registered ZorOS windows."""
        for window_id in self.windows:
            window_info = self.windows[window_id]
            window = window_info['window']
            if window.isVisible():
                window.hide()
                window_info['visible'] = False
        
        logger.info("Hidden all ZorOS windows")
    
    def quit_all(self) -> None:
        """Quit all ZorOS applications."""
        logger.info("Quitting all ZorOS applications")
        QApplication.quit()
    
    def get_window_list(self) -> List[Tuple[str, str, str]]:
        """Get list of registered windows.
        
        Returns:
            List of (window_id, window_type, title) tuples
        """
        return [(wid, info['type'], info['title']) 
                for wid, info in self.windows.items()]
    
    def launch_window(self, window_type: str, backend: Optional[str] = None) -> Optional[str]:
        """Launch a new ZorOS window in a separate process.
        
        Args:
            window_type: Type of window to launch ('intake', 'library', 'test')
            backend: Optional backend to use for transcription
            
        Returns:
            Process ID if launched successfully, None otherwise
            
        Spec: docs/requirements/dictation_requirements.md#process-isolation
        Tests: tests/test_window_manager.py#test_window_launch
        """
        try:
            # Build command
            cmd = [sys.executable, "-m", f"source.interfaces.{window_type}.main"]
            
            if backend:
                cmd.extend(["--backend", backend])
            
            # Launch in separate process
            process = subprocess.Popen(cmd, 
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
            
            logger.info(f"Launched {window_type} window (PID: {process.pid})")
            return str(process.pid)
            
        except Exception as e:
            logger.error(f"Error launching {window_type} window: {e}")
            return None
    
    def _update_system_tray_menu(self) -> None:
        """Update the system tray window menu."""
        if not self.system_tray or not hasattr(self, 'window_menu'):
            return
        
        try:
            # Clear existing window menu
            self.window_menu.clear()
            
            # Add window actions
            for window_id, window_info in self.windows.items():
                action = self.window_menu.addAction(window_info['title'])
                action.triggered.connect(lambda checked, wid=window_id: self.focus_window(wid))
                
                # Add checkmark if window is visible
                if window_info['visible']:
                    action.setCheckable(True)
                    action.setChecked(True)
        except Exception as e:
            logger.warning(f"Error updating system tray menu: {e}")
    
    def _update_window_title(self, window_id: str, title: str) -> None:
        """Update window title in registry."""
        if window_id in self.windows:
            self.windows[window_id]['title'] = title
            self._update_system_tray_menu()


# Global window manager instance
_window_manager: Optional[ZorosWindowManager] = None


def get_window_manager() -> ZorosWindowManager:
    """Get the global window manager instance."""
    global _window_manager
    if _window_manager is None:
        _window_manager = ZorosWindowManager()
    return _window_manager


def register_window(window: QMainWindow, window_type: str, 
                   window_id: Optional[str] = None) -> str:
    """Register a window with the global window manager."""
    return get_window_manager().register_window(window, window_type, window_id)


def focus_window(window_id: str) -> bool:
    """Focus a window using the global window manager."""
    return get_window_manager().focus_window(window_id)


def launch_window(window_type: str, backend: Optional[str] = None) -> Optional[str]:
    """Launch a new window using the global window manager."""
    return get_window_manager().launch_window(window_type, backend) 