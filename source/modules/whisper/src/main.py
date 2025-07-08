# See architecture: docs/zoros_architecture.md#component-overview
import os
import sys
import time
import datetime
import argparse
import pyperclip  # For clipboard functionality
from audioplayer import AudioPlayer
from pynput.keyboard import Controller
from PySide6.QtCore import QObject, QProcess, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox

from key_listener import KeyListener
from result_thread import ResultThread
from ui.main_window import MainWindow
from ui.settings_window import SettingsWindow
from ui.status_window import StatusWindow
from transcription import create_local_model
from input_simulation import InputSimulator
from utils import ConfigManager, DictationManager

# Import for audio stream preloading
import sounddevice as sd
import numpy as np
from threading import Event


class WhisperWriterApp(QObject):
    # Static variables for persistent audio stream
    persistent_audio_stream = None
    audio_callback_data = None
    
    def __init__(self, no_hotkey: bool = False):
        """
        Initialize the application, with options to skip main UI but still show status window.
        """
        super().__init__()
        
        # Parse command-line arguments
        parser = argparse.ArgumentParser(description='Whisper Writer speech-to-text application')
        parser.add_argument('--settings', action='store_true', help='Open settings window directly')
        parser.add_argument('--headless', action='store_true', help='Run without main UI (only status window and keyboard listener)')
        args, _ = parser.parse_known_args()
        
        self.use_hotkey = not no_hotkey
        self.app = QApplication(sys.argv)
        self.app.setWindowIcon(QIcon(os.path.join('assets', 'ww-logo.png')))
        
        # Track headless mode
        self.headless_mode = args.headless
        if self.headless_mode:
            print('Starting in headless mode (only status window, no main window)')

        ConfigManager.initialize()
        
        # Initialize dictation storage system
        DictationManager.initialize()

        # Create default config if it doesn't exist
        if not ConfigManager.config_file_exists():
            print('No configuration file found. Creating default configuration...')
            ConfigManager.save_config()
        
        # Create settings window if not in headless mode
        if not self.headless_mode:
            self.settings_window = SettingsWindow()
            self.settings_window.settings_closed.connect(self.on_settings_closed)
            self.settings_window.settings_saved.connect(self.restart_app)
        
        # Initialize core components
        self.initialize_core_components()
        
        # Initialize status window in all modes, unless specifically hidden
        hide_status = ConfigManager.get_config_value('misc', 'hide_status_window')
        if not hide_status:
            self.status_window = StatusWindow()
        else:
            self.status_window = None
            
        # Initialize main window only if not in headless mode
        if not self.headless_mode:
            self.initialize_main_window()
            
            # Show settings if requested
            if args.settings:
                print('Opening settings window from command line...')
                self.settings_window.show()
        else:
            if self.use_hotkey and self.key_listener:
                print('Starting key listener in headless mode...')
                self.key_listener.start()
            else:
                print('Headless mode without hotkeys is not fully supported.')

    def initialize_core_components(self):
        """
        Initialize the core functionality components that work in both UI and headless modes.
        """
        self.input_simulator = InputSimulator()

        if self.use_hotkey:
            self.key_listener = KeyListener()
            self.key_listener.add_callback("on_activate", self.on_activation)
            self.key_listener.add_callback("on_deactivate", self.on_deactivation)
        else:
            self.key_listener = None

        # Ensure sound_device is properly set
        recording_options = ConfigManager.get_config_section('recording_options')
        print(f"Recording options after initialization: {recording_options}")
        
        if 'sound_device' not in recording_options or recording_options['sound_device'] is None:
            print("Setting sound_device to '1' since it's not in the config")
            ConfigManager.set_config_value("1", "recording_options", "sound_device")
            ConfigManager.save_config()
            print(f"Updated recording options: {ConfigManager.get_config_section('recording_options')}")
        
        # Initialize model
        model_options = ConfigManager.get_config_section('model_options')
        backend = model_options.get('backend', 'faster-whisper')
        if backend == 'faster-whisper' and not model_options.get('use_api'):
            self.local_model = create_local_model()
        else:
            self.local_model = None
        self.result_thread = None
        
        # Initialize audio stream with a slight delay
        QTimer.singleShot(1000, self.initialize_persistent_audio)

    def initialize_main_window(self):
        """
        Initialize main UI window - only called in non-headless mode.
        """
        self.main_window = MainWindow()
        self.main_window.openSettings.connect(self.settings_window.show)
        if self.use_hotkey:
            self.main_window.startRecording.connect(self.key_listener.start)
        else:
            self.main_window.startRecording.connect(self.start_result_thread)
            self.main_window.stopRecording.connect(self.stop_result_thread)
        self.main_window.closeApp.connect(self.exit_app)
        
        # Show the main window
        self.main_window.show()
        
    def initialize_persistent_audio(self):
        """
        Initialize a persistent audio stream that remains open during the entire app lifecycle.
        This dramatically reduces the recording startup time by eliminating audio device 
        initialization delay when the hotkey is pressed.
        """
        try:
            if WhisperWriterApp.persistent_audio_stream is not None:
                return  # Already initialized
                
            print("Initializing persistent audio stream...")
            recording_options = ConfigManager.get_config_section('recording_options')
            sample_rate = recording_options.get('sample_rate') or 16000
            
            # Configure sound device with enhanced name-based selection
            sound_device = None
            configured_device = recording_options.get('sound_device')
            
            if configured_device is not None:
                # Check if it's a list/array of device patterns
                if isinstance(configured_device, list):
                    print(f"Multiple sound devices configured, trying each in order")
                    # Try each device pattern in order until one is found
                    for device_pattern in configured_device:
                        if isinstance(device_pattern, str):
                            if device_pattern.strip() == "":
                                continue  # Skip empty strings
                            elif device_pattern.isdigit():
                                # Try numeric index
                                device_index = int(device_pattern)
                                try:
                                    # Verify the device exists
                                    devices = sd.query_devices()
                                    if 0 <= device_index < len(devices):
                                        sound_device = device_index
                                        print(f"Using device #{sound_device} from numeric index in list")
                                        break
                                except Exception:
                                    pass  # Continue to next pattern if this fails
                            else:
                                # Try to find a device by pattern matching
                                matched_device = ConfigManager.find_device_by_name_pattern(device_pattern)
                                if matched_device is not None:
                                    sound_device = matched_device
                                    print(f"Using device #{sound_device} matched by name pattern '{device_pattern}'")
                                    break
                        elif isinstance(device_pattern, int):
                            # Direct integer index
                            try:
                                # Verify the device exists
                                devices = sd.query_devices()
                                if 0 <= device_pattern < len(devices):
                                    sound_device = device_pattern
                                    print(f"Using device #{sound_device} from integer index in list")
                                    break
                            except Exception:
                                pass  # Continue to next pattern if this fails

                    if sound_device is None:
                        print(f"No matching device found for any pattern in configured devices")
                        # Fall back to first pattern as direct name/index
                        sound_device = configured_device[0]
                else:
                    # Handle single device specification (existing logic)
                    if isinstance(configured_device, str):
                        if configured_device.strip() == "":
                            sound_device = None  # Empty string means default device
                        elif configured_device.isdigit():
                            sound_device = int(configured_device)  # Convert numeric string to int
                        else:
                            # Try to find a device by pattern matching
                            matched_device = ConfigManager.find_device_by_name_pattern(configured_device)
                            if matched_device is not None:
                                sound_device = matched_device  # Use the matched device index
                                print(f"Using device #{sound_device} matched by name pattern '{configured_device}'")
                            else:
                                # Fall back to using the string directly as a device name
                                sound_device = configured_device
                                print(f"No matching device found for '{configured_device}', using as direct name")
                    else:
                        # Direct integer or other value
                        sound_device = configured_device
                    
            # Prepare callback data structure
            WhisperWriterApp.audio_callback_data = {
                'buffer': [],
                'is_recording': False,
                'event': Event()
            }
            
            # Define minimal callback that only collects data when recording is active
            def persistent_audio_callback(indata, frames, time, status):
                if WhisperWriterApp.audio_callback_data['is_recording']:
                    WhisperWriterApp.audio_callback_data['buffer'].extend(indata[:, 0])
                    WhisperWriterApp.audio_callback_data['event'].set()
                    
            # Create minimal blocksize for more frequent callbacks and less latency
            blocksize = int(sample_rate * 0.01)  # 10ms blocks instead of 30ms
                  
            # Open the persistent stream
            WhisperWriterApp.persistent_audio_stream = sd.InputStream(
                samplerate=sample_rate,
                channels=1,
                dtype='int16',
                blocksize=blocksize,
                device=sound_device,
                callback=persistent_audio_callback
            )
            
            # Start the stream
            WhisperWriterApp.persistent_audio_stream.start()
            print("Persistent audio stream successfully initialized!")
            
            # Let the ResultThread know we have a persistent stream
            ResultThread.persistent_audio_stream = WhisperWriterApp.persistent_audio_stream
            ResultThread.audio_callback_data = WhisperWriterApp.audio_callback_data
            
        except Exception as e:
            print(f"Error initializing persistent audio stream: {str(e)}")
            # Not having a persistent stream is ok - we'll fall back to on-demand streaming

    def cleanup(self):
        if self.key_listener:
            self.key_listener.stop()
        if self.input_simulator:
            self.input_simulator.cleanup()

    def exit_app(self):
        """
        Exit the application.
        """
        self.cleanup()
        QApplication.quit()

    def restart_app(self):
        """Restart the application to apply the new settings."""


        self.cleanup()
        QApplication.quit()
        QProcess.startDetached(sys.executable, sys.argv)

    def on_settings_closed(self):
        """
        If settings is closed without saving on first run, initialize the components with default values.
        """
        if not os.path.exists(os.path.join('src', 'config.yaml')):
            QMessageBox.information(
                self.settings_window,
                'Using Default Values',
                'Settings closed without saving. Default values are being used.'
            )
            # Initialize core components and main window
            self.initialize_core_components()
            self.initialize_main_window()

    def on_activation(self):
        """
        Called when the activation key combination is pressed.
        """
        if self.result_thread and self.result_thread.isRunning():
            recording_mode = ConfigManager.get_config_value('recording_options', 'recording_mode')
            if recording_mode == 'press_to_toggle':
                self.result_thread.stop_recording()
            elif recording_mode == 'continuous':
                self.stop_result_thread()
            return

        self.start_result_thread()

    def on_deactivation(self):
        """
        Called when the activation key combination is released.
        """
        if ConfigManager.get_config_value('recording_options', 'recording_mode') == 'hold_to_record':
            if self.result_thread and self.result_thread.isRunning():
                self.result_thread.stop_recording()

    def start_result_thread(self):
        """
        Start the result thread to record audio and transcribe it.
        """
        if self.result_thread and self.result_thread.isRunning():
            return

        self.result_thread = ResultThread(self.local_model)
        
        # Connect to status window if it exists and if it's not hidden in config
        if hasattr(self, 'status_window') and self.status_window:
            self.result_thread.statusSignal.connect(self.status_window.updateStatus)
            self.status_window.closeSignal.connect(self.stop_result_thread)
            
        self.result_thread.resultSignal.connect(self.on_transcription_complete)
        self.result_thread.dictationSignal.connect(self.on_dictation_complete)
        self.result_thread.start()

    def stop_result_thread(self):
        """
        Stop the result thread.
        """
        if self.result_thread and self.result_thread.isRunning():
            self.result_thread.stop()

    def on_dictation_complete(self, dictation):
        """
        Handle a completed dictation object.
        This is called when the ResultThread completes a dictation and emits it.
        
        Args:
            dictation (dict): The completed dictation object
        """
        ConfigManager.console_print(f"Dictation complete: ID {dictation['dictation_id']}")
        
        # The transcription will be handled separately by on_transcription_complete

    def save_transcription_to_file(self, text):
        """
        Save the transcription to a file with an optional timestamp.
        
        Args:
            text (str): The transcription text to save
        """
        post_processing = ConfigManager.get_config_section('post_processing')
        
        # Check for dictations directory setting
        use_dictations_dir = post_processing.get('use_dictations_directory', False)
        
        if use_dictations_dir:
            # This is handled by DictationManager, so we don't need to do anything here
            ConfigManager.console_print("Transcription saved to dictation object")
            return
        
        # Legacy file saving logic
        file_path = post_processing.get('transcription_file_path')
        
        # Ensure the file path is absolute
        if not os.path.isabs(file_path):
            file_path = os.path.join(os.getcwd(), file_path)
            
        # Get current timestamp
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Prepare the content to write
        if post_processing.get('prepend_timestamp'):
            content = f"[{timestamp}] {text}\n\n"
        else:
            content = f"{text}\n\n"
            
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path) or '.', exist_ok=True)
        
        # Append to file - write at the beginning of the file
        try:
            # If file exists, read its content first
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
            else:
                existing_content = ""
                
            # Write new content at the beginning of the file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content + existing_content)
                
            ConfigManager.console_print(f"Transcription saved to {file_path}")
        except Exception as e:
            ConfigManager.console_print(f"Error saving transcription to file: {str(e)}")

    def on_transcription_complete(self, result):
        """
        When the transcription is complete, handle the result based on configuration settings.
        Either type the result at cursor position, save to file, or both.
        Also can copy to clipboard.
        """
        post_processing = ConfigManager.get_config_section('post_processing')
        save_to_file = post_processing.get('save_to_file')
        copy_to_clipboard = post_processing.get('copy_to_clipboard')
        use_dictations_dir = post_processing.get('use_dictations_directory', False)
        
        # Apply any post-processing to the result text
        if post_processing.get('remove_trailing_period') and result.endswith('.'):
            result = result[:-1]
            
        if post_processing.get('add_trailing_space'):
            result += ' '
            
        if post_processing.get('remove_capitalization'):
            result = result.lower()
        
        # Save to file if enabled
        if save_to_file:
            self.save_transcription_to_file(result)
        
        # Copy to clipboard if enabled
        if copy_to_clipboard:
            try:
                pyperclip.copy(result)
                ConfigManager.console_print("Transcription copied to clipboard")
            except Exception as e:
                ConfigManager.console_print(f"Error copying to clipboard: {str(e)}")
        
        # Type at cursor position if file saving is not enabled or if typing is forced
        if not save_to_file or post_processing.get('always_type_at_cursor', False):
            self.input_simulator.typewrite(result)

        # Play completion sound if enabled
        if ConfigManager.get_config_value('misc', 'noise_on_completion'):
            AudioPlayer(os.path.join('assets', 'beep.wav')).play(block=True)

        # Continue recording or start listening based on recording mode
        if ConfigManager.get_config_value('recording_options', 'recording_mode') == 'continuous':
            self.start_result_thread()
        else:
            if self.use_hotkey and self.key_listener:
                self.key_listener.start()
            elif not self.use_hotkey and hasattr(self, 'main_window'):
                self.main_window.update_recording_state(False)

    def run(self):
        """
        Start the application.
        """
        sys.exit(self.app.exec())


if __name__ == '__main__':
    app = WhisperWriterApp()
    app.run()
