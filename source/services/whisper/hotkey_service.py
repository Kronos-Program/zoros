"""
Global Hotkey Service for Zoros Dictation

This module provides cross-platform global hotkey functionality for controlling
dictation recording. It supports both push-to-hold and push-to-toggle modes
with configurable key combinations.

Dependencies:
- pynput: Cross-platform keyboard monitoring and global hotkeys
- PySide6: Qt signals for UI integration

Permissions Required:
- macOS: "Enable access for assistive devices" in System Preferences
- Windows: May require admin privileges for global hooks
- Linux: X11 session (Wayland support may be limited)
"""

import logging
from enum import Enum
from typing import Callable, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path
import json

from PySide6.QtCore import QObject, Signal
from pynput import keyboard
from pynput.keyboard import GlobalHotKeys, Key

logger = logging.getLogger(__name__)


class HotkeyMode(Enum):
    """Hotkey operation modes."""
    PUSH_TO_HOLD = "push_to_hold"  # Hold key to record, release to stop
    PUSH_TO_TOGGLE = "push_to_toggle"  # Press once to start, press again to stop


@dataclass
class HotkeyConfig:
    """Configuration for global hotkeys."""
    enabled: bool = True
    mode: HotkeyMode = HotkeyMode.PUSH_TO_TOGGLE
    key_combination: str = "<ctrl>+<alt>+r"  # Default: Ctrl+Alt+R
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "enabled": self.enabled,
            "mode": self.mode.value,
            "key_combination": self.key_combination
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HotkeyConfig':
        """Create from dictionary."""
        return cls(
            enabled=data.get("enabled", True),
            mode=HotkeyMode(data.get("mode", HotkeyMode.PUSH_TO_TOGGLE.value)),
            key_combination=data.get("key_combination", "<ctrl>+<alt>+r")
        )


class GlobalHotkeyService(QObject):
    """
    Cross-platform global hotkey service for dictation control.
    
    Provides configurable hotkeys with support for both hold-to-record
    and toggle recording modes. Integrates with Qt's signal system
    for seamless UI communication.
    
    Signals:
        start_recording: Emitted when recording should start
        stop_recording: Emitted when recording should stop
        hotkey_error: Emitted when hotkey setup fails
    """
    
    # Qt Signals
    start_recording = Signal()
    stop_recording = Signal()
    hotkey_error = Signal(str)  # Error message
    
    def __init__(self):
        super().__init__()
        self.config = HotkeyConfig()
        self.hotkeys: Optional[GlobalHotKeys] = None
        self.is_recording = False
        self.is_key_held = False
        
        # Callbacks for different hotkey actions
        self._start_callback: Optional[Callable] = None
        self._stop_callback: Optional[Callable] = None
        
        # Load saved configuration
        self.load_config()
    
    def set_callbacks(self, start_callback: Callable, stop_callback: Callable):
        """Set callbacks for recording start/stop actions."""
        self._start_callback = start_callback
        self._stop_callback = stop_callback
    
    def load_config(self):
        """Load hotkey configuration from settings file."""
        try:
            config_path = Path.home() / ".zoros" / "hotkey_settings.json"
            if config_path.exists():
                with open(config_path, 'r') as f:
                    data = json.load(f)
                    self.config = HotkeyConfig.from_dict(data)
                logger.info(f"Loaded hotkey config: {self.config.key_combination} ({self.config.mode.value})")
            else:
                logger.info("No hotkey config found, using defaults")
        except Exception as e:
            logger.error(f"Error loading hotkey config: {e}")
            self.config = HotkeyConfig()  # Reset to defaults
    
    def save_config(self):
        """Save current hotkey configuration."""
        try:
            config_dir = Path.home() / ".zoros"
            config_dir.mkdir(exist_ok=True)
            
            config_path = config_dir / "hotkey_settings.json"
            with open(config_path, 'w') as f:
                json.dump(self.config.to_dict(), f, indent=2)
            logger.info(f"Saved hotkey config to {config_path}")
        except Exception as e:
            logger.error(f"Error saving hotkey config: {e}")
    
    def update_config(self, config: HotkeyConfig):
        """Update configuration and restart hotkeys."""
        self.config = config
        self.save_config()
        if self.hotkeys:
            self.stop_hotkeys()
            self.start_hotkeys()
    
    def start_hotkeys(self) -> bool:
        """
        Start global hotkey monitoring.
        
        Returns:
            bool: True if hotkeys started successfully, False otherwise
        """
        if not self.config.enabled:
            logger.info("Hotkeys disabled in configuration")
            return True
        
        if self.hotkeys:
            logger.warning("Hotkeys already running")
            return True
        
        try:
            # Validate key combination before attempting to start
            if not self.test_hotkey(self.config.key_combination):
                error_msg = f"Invalid key combination: {self.config.key_combination}"
                logger.error(error_msg)
                self.hotkey_error.emit(error_msg)
                return False
            
            if self.config.mode == HotkeyMode.PUSH_TO_TOGGLE:
                # Toggle mode: one hotkey for start/stop
                hotkey_map = {
                    self.config.key_combination: self._on_toggle_hotkey
                }
            else:
                # Hold mode: separate press/release handling  
                hotkey_map = {
                    self.config.key_combination: self._on_hold_press
                }
            
            # Create hotkeys with better error handling
            self.hotkeys = GlobalHotKeys(hotkey_map)
            
            # Start in a separate try block to catch startup errors
            try:
                self.hotkeys.start()
            except Exception as start_error:
                # Clean up the hotkeys object if start fails
                self.hotkeys = None
                raise start_error
            
            # For hold mode, we also need a regular keyboard listener for key releases
            if self.config.mode == HotkeyMode.PUSH_TO_HOLD:
                self._setup_hold_mode_listener()
            
            logger.info(f"Global hotkeys started: {self.config.key_combination} ({self.config.mode.value})")
            return True
            
        except Exception as e:
            error_msg = f"Failed to start global hotkeys: {e}"
            logger.error(error_msg)
            
            # Ensure cleanup on failure
            if hasattr(self, 'hotkeys') and self.hotkeys:
                try:
                    self.hotkeys.stop()
                except:
                    pass
                self.hotkeys = None
            
            self.hotkey_error.emit(error_msg)
            return False
    
    def stop_hotkeys(self):
        """Stop global hotkey monitoring."""
        if self.hotkeys:
            try:
                # Use join() to properly wait for hotkey thread to finish
                self.hotkeys.stop()
                # Give the thread time to clean up properly
                import time
                time.sleep(0.1)
                self.hotkeys = None
                logger.info("Global hotkeys stopped")
            except Exception as e:
                logger.error(f"Error stopping hotkeys: {e}")
                # Force cleanup even if stop() fails
                self.hotkeys = None
    
    def _on_toggle_hotkey(self):
        """Handle toggle mode hotkey press."""
        logger.debug(f"Toggle hotkey pressed, currently recording: {self.is_recording}")
        
        if self.is_recording:
            self._trigger_stop()
        else:
            self._trigger_start()
    
    def _on_hold_press(self):
        """Handle hold mode hotkey press."""
        logger.debug("Hold hotkey pressed")
        if not self.is_key_held:
            self.is_key_held = True
            self._trigger_start()
    
    def _setup_hold_mode_listener(self):
        """Set up keyboard listener for hold mode key releases."""
        def on_key_release(key):
            # Parse the configured key combination to detect releases
            if self.is_key_held and self._is_hotkey_release(key):
                logger.debug("Hold hotkey released")
                self.is_key_held = False
                self._trigger_stop()
        
        # Start a separate listener for key releases
        listener = keyboard.Listener(on_release=on_key_release)
        listener.start()
    
    def _is_hotkey_release(self, key) -> bool:
        """Check if the released key matches our hotkey combination."""
        # This is a simplified check - in a full implementation,
        # we'd need to parse the key combination string and track modifiers
        try:
            # For now, check if it's the main key (not a modifier)
            key_str = str(key).replace("'", "")
            return key_str.lower() == 'r'  # Assuming 'r' is the main key
        except:
            return False
    
    def _trigger_start(self):
        """Trigger recording start."""
        if not self.is_recording:
            self.is_recording = True
            logger.info("Hotkey triggered: START recording")
            self.start_recording.emit()
            if self._start_callback:
                self._start_callback()
    
    def _trigger_stop(self):
        """Trigger recording stop."""
        if self.is_recording:
            self.is_recording = False
            logger.info("Hotkey triggered: STOP recording")
            self.stop_recording.emit()
            if self._stop_callback:
                self._stop_callback()
    
    def set_recording_state(self, is_recording: bool):
        """Update internal recording state (called by main app)."""
        self.is_recording = is_recording
    
    def get_supported_keys(self) -> Dict[str, str]:
        """Get list of supported key combinations for UI configuration."""
        return {
            "Ctrl+Alt+R": "<ctrl>+<alt>+r",
            "Ctrl+Alt+D": "<ctrl>+<alt>+d", 
            "Ctrl+Shift+R": "<ctrl>+<shift>+r",
            "Ctrl+Shift+D": "<ctrl>+<shift>+d",
            "F12": "<f12>",
            "F11": "<f11>",
            "Ctrl+F12": "<ctrl>+<f12>",
            "Alt+Space": "<alt>+<space>",
            "Ctrl+`": "<ctrl>+`"
        }
    
    def test_hotkey(self, key_combination: str) -> bool:
        """Test if a hotkey combination is valid."""
        if not key_combination or not key_combination.strip():
            return False
            
        try:
            # Create a temporary hotkey to test validity with better cleanup
            test_hotkeys = None
            try:
                test_hotkeys = GlobalHotKeys({key_combination: lambda: None})
                test_hotkeys.start()
                
                # Give it a moment to initialize properly
                import time
                time.sleep(0.05)
                
                return True
            finally:
                # Ensure cleanup happens
                if test_hotkeys:
                    try:
                        test_hotkeys.stop()
                        time.sleep(0.05)  # Allow cleanup time
                    except:
                        pass  # Ignore cleanup errors
                        
        except Exception as e:
            logger.debug(f"Invalid hotkey combination '{key_combination}': {e}")
            return False
    
    def __del__(self):
        """Cleanup on destruction."""
        self.stop_hotkeys()


# Global instance for easy access
_hotkey_service: Optional[GlobalHotkeyService] = None

def get_hotkey_service() -> GlobalHotkeyService:
    """Get the global hotkey service instance."""
    global _hotkey_service
    if _hotkey_service is None:
        _hotkey_service = GlobalHotkeyService()
    return _hotkey_service