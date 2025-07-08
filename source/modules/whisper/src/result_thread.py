# See architecture: docs/zoros_architecture.md#component-overview
import time
import traceback
import numpy as np
import sounddevice as sd
import tempfile
import wave
import webrtcvad
from PySide6.QtCore import QThread, QMutex, Signal
from collections import deque
from threading import Event
import os

from transcription import transcribe
from utils import ConfigManager, DictationManager


class ResultThread(QThread):
    """
    A thread class for handling audio recording, transcription, and result processing.

    This class manages the entire process of:
    1. Recording audio from the microphone
    2. Detecting speech and silence
    3. Saving the recorded audio as numpy array
    4. Transcribing the audio
    5. Creating and saving dictation objects
    

    Signals:
        statusSignal: Emits the current status of the thread (e.g., 'recording', 'transcribing', 'idle')
        resultSignal: Emits the transcription result
        dictationSignal: Emits the created dictation object
    """

    statusSignal = Signal(str)
    resultSignal = Signal(str)
    dictationSignal = Signal(dict)
    
    # Static variable to hold pre-initialized audio parameters
    audio_stream = None
    audio_device = None
    sample_rate = None

    def __init__(self, local_model=None):
        """
        Initialize the ResultThread.

        :param local_model: Local transcription model (if applicable)
        """
        super().__init__()
        self.local_model = local_model
        self.is_recording = False
        self.is_running = True
        self.mutex = QMutex()
        self.recorded_audio = None  # Store the recorded audio data
        self.dictation = None  # Store the current dictation object
        
        # Pre-initialize audio parameters if not already done
        if ResultThread.audio_device is None:
            try:
                self._initialize_audio_params()
            except Exception as e:
                ConfigManager.console_print(f"Warning: Could not pre-initialize audio: {str(e)}")
                
        # Initialize dictation storage
        DictationManager.initialize()

    def _initialize_audio_params(self):
        """Pre-initializes audio parameters to speed up recording startup"""
        recording_options = ConfigManager.get_config_section('recording_options')
        ResultThread.sample_rate = recording_options.get('sample_rate') or 16000

        # Process sound_device value with enhanced handling
        sound_device = None
        try:
            # Get the raw value from config
            configured_device = recording_options.get('sound_device')

            # Handle different types properly
            if configured_device is not None:
                # Check if it's a list/array of device patterns
                if isinstance(configured_device, list):
                    ConfigManager.console_print(f"Multiple sound devices configured, trying each in order")
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
                                        ConfigManager.console_print(f"Using device #{sound_device} from numeric index in list")
                                        break
                                except Exception:
                                    pass  # Continue to next pattern if this fails
                            else:
                                # Try to find a device by pattern matching
                                matched_device = ConfigManager.find_device_by_name_pattern(device_pattern)
                                if matched_device is not None:
                                    sound_device = matched_device
                                    ConfigManager.console_print(f"Using device #{sound_device} matched by name pattern '{device_pattern}'")
                                    break
                        elif isinstance(device_pattern, int):
                            # Direct integer index
                            try:
                                # Verify the device exists
                                devices = sd.query_devices()
                                if 0 <= device_pattern < len(devices):
                                    sound_device = device_pattern
                                    ConfigManager.console_print(f"Using device #{sound_device} from integer index in list")
                                    break
                            except Exception:
                                pass  # Continue to next pattern if this fails

                    if sound_device is None:
                        ConfigManager.console_print(f"No matching device found for any pattern in configured devices")
                        # Fall back to first pattern as direct name/index
                        sound_device = configured_device[0]
                else:
                    # Original single-device logic
                    if isinstance(configured_device, str):
                        # Handle string configurations
                        if configured_device.strip() == "":
                            sound_device = None  # Empty string means default device
                        elif configured_device.isdigit():
                            sound_device = int(configured_device)  # Convert numeric string to int
                        else:
                            # Try to find a device by pattern matching
                            matched_device = ConfigManager.find_device_by_name_pattern(configured_device)
                            if matched_device is not None:
                                sound_device = matched_device  # Use the matched device index
                            else:
                                # Fall back to using the string directly as a device name
                                sound_device = configured_device
                    else:
                        # Direct integer or other value
                        sound_device = configured_device
        except Exception as e:
            ConfigManager.console_print(f"Error initializing audio device: {str(e)}")
            sound_device = None  # Fall back to default device
            
        ResultThread.audio_device = sound_device

    def stop_recording(self):
        """Stop the current recording session."""
        self.mutex.lock()
        self.is_recording = False
        self.mutex.unlock()

    def stop(self):
        """Stop the entire thread execution."""
        self.mutex.lock()
        self.is_running = False
        self.mutex.unlock()
        self.statusSignal.emit('idle')
        self.wait()

    def run(self):
        """Main execution method for the thread."""
        try:
            if not self.is_running:
                return

            self.mutex.lock()
            self.is_recording = True
            self.mutex.unlock()

            self.statusSignal.emit('preparing')
            ConfigManager.console_print('Starting recording...')
            audio_data = self._record_audio()
            
            # Save the recorded audio for later use
            self.recorded_audio = audio_data

            if not self.is_running:
                return

            if audio_data is None:
                self.statusSignal.emit('idle')
                return

            self.statusSignal.emit('transcribing')
            ConfigManager.console_print('Transcribing...')

            # Time the transcription process
            start_time = time.time()
            result = transcribe(audio_data, self.local_model)
            end_time = time.time()

            transcription_time = end_time - start_time
            ConfigManager.console_print(f'Transcription completed in {transcription_time:.2f} seconds. Post-processed line: {result}')

            # Create a dictation object with audio and transcription
            self.dictation = DictationManager.create_dictation(
                audio_data=audio_data,
                quick_transcript=result
            )
            
            ConfigManager.console_print(f'Dictation saved with ID: {self.dictation["dictation_id"]}')
            
            if not self.is_running:
                return

            # Emit both the transcription and dictation object
            self.statusSignal.emit('idle')
            self.resultSignal.emit(result)
            self.dictationSignal.emit(self.dictation)

        except Exception as e:
            traceback.print_exc()
            self.statusSignal.emit('error')
            self.resultSignal.emit('')
        finally:
            self.stop_recording()

    def _record_audio(self):
        """
        Record audio from the microphone and save it to a temporary file.

        :return: numpy array of audio data, or None if the recording is too short
        """
        recording_options = ConfigManager.get_config_section('recording_options')
        self.sample_rate = recording_options.get('sample_rate') or 16000
        frame_duration_ms = 30  # 30ms frame duration for WebRTC VAD
        frame_size = int(self.sample_rate * (frame_duration_ms / 1000.0))
        silence_duration_ms = recording_options.get('silence_duration') or 900
        silence_frames = int(silence_duration_ms / frame_duration_ms)

        # Only skip 1 frame (30ms) to avoid key press noise
        initial_frames_to_skip = 1
        
        # Create VAD only for recording modes that use it
        recording_mode = recording_options.get('recording_mode') or 'continuous'
        vad = None
        if recording_mode in ('voice_activity_detection', 'continuous'):
            vad = webrtcvad.Vad(2)  # VAD aggressiveness: 0 to 3, 3 being the most aggressive
            speech_detected = False
            silent_frame_count = 0

        # Use for collecting frames processed from the audio buffer
        recording = []

        # Signal to notify when recording is actually ready
        self.recording_ready = Event()

        # Fast-startup approach using persistent audio stream
        try:
            # Signal preparing status 
            self.statusSignal.emit('preparing')
            start_time_ms = int(time.time() * 1000)
            
            # Check if we have a persistent audio stream available
            if hasattr(ResultThread, 'persistent_audio_stream') and ResultThread.persistent_audio_stream is not None:
                # FAST PATH: Use the pre-initialized persistent audio stream
                ConfigManager.console_print("Using persistent audio stream for ultra-fast startup")
                
                # Reset the buffer
                ResultThread.audio_callback_data['buffer'] = []
                
                # Set recording flag to start capturing audio
                ResultThread.audio_callback_data['is_recording'] = True
                
                # Clear any previous events
                ResultThread.audio_callback_data['event'].clear()
                
                # We're immediately ready - signal ready state
                current_time_ms = int(time.time() * 1000)
                startup_time_ms = current_time_ms - start_time_ms
                ConfigManager.console_print(f"Recording ready in {startup_time_ms}ms")
                self.statusSignal.emit('ready')
                
                # Play a brief beep to indicate recording is ready
                try:
                    if os.path.exists(os.path.join('assets', 'beep.wav')):
                        from audioplayer import AudioPlayer
                        AudioPlayer(os.path.join('assets', 'beep.wav')).play(block=False)
                except Exception:
                    pass  # Ignore beep errors
                
                # ------------ MAIN RECORDING LOOP (FAST PATH) ------------
                min_record_time_seconds = 1.0
                start_time = time.time()
                frames_collected = 0
                
                while self.is_running and self.is_recording:
                    # Force minimum recording time
                    current_time = time.time()
                    elapsed_time = (current_time * 1000 - start_time_ms) / 1000.0
                    
                    # Check for new audio data (100ms timeout)
                    if ResultThread.audio_callback_data['event'].wait(timeout=0.1):
                        ResultThread.audio_callback_data['event'].clear()
                        
                        # Get a snapshot of the current buffer
                        buffer_snapshot = ResultThread.audio_callback_data['buffer'].copy()
                        ResultThread.audio_callback_data['buffer'] = []
                        
                        if buffer_snapshot:
                            # Process all audio data we got
                            while len(buffer_snapshot) >= frame_size:
                                # Extract a frame
                                frame = np.array(buffer_snapshot[:frame_size], dtype=np.int16)
                                buffer_snapshot = buffer_snapshot[frame_size:]
                                
                                # Skip initial frame if needed
                                if initial_frames_to_skip > 0:
                                    initial_frames_to_skip -= 1
                                    continue
                                
                                # Add frame to recording
                                recording.extend(frame)
                                frames_collected += 1
                                
                                # Process VAD
                                if vad and elapsed_time >= min_record_time_seconds:
                                    try:
                                        is_speech = vad.is_speech(frame.tobytes(), self.sample_rate)
                                        if is_speech:
                                            silent_frame_count = 0
                                            if not speech_detected:
                                                speech_detected = True
                                                self.statusSignal.emit('recording')
                                        else:
                                            silent_frame_count += 1

                                        if speech_detected and silent_frame_count > silence_frames:
                                            self.is_recording = False
                                            break
                                    except Exception as e:
                                        ConfigManager.console_print(f"VAD error: {str(e)}")
                            
                            # Add any remaining data to recording
                            if buffer_snapshot:
                                recording.extend(buffer_snapshot)
                    
                    # For very short hold_to_record mode
                    if elapsed_time >= min_record_time_seconds and recording_mode == 'hold_to_record' and not self.is_recording:
                        break
                
                # Stop collecting audio data
                ResultThread.audio_callback_data['is_recording'] = False
                
            else:
                # SLOW PATH: Fall back to creating a new stream if persistent stream isn't available
                ConfigManager.console_print("Persistent stream not available, falling back to on-demand stream")

                # ... existing on-demand stream code ...
                # Changed from deque to list to prevent data loss
                audio_buffer = []
                data_ready = Event()

                def audio_callback(indata, frames, time, status):
                    if status and status != sd.CallbackFlags.input_underflow:  # Ignore common underflow warnings
                        ConfigManager.console_print(f"Audio callback status: {status}")
                    
                    # Extend buffer with all samples from this callback - no debug here for speed
                    audio_buffer.extend(indata[:, 0])
                    data_ready.set()

                # Process sound_device value with enhanced handling
                sound_device = None
                try:
                    # Get the raw value from config
                    configured_device = recording_options.get('sound_device')

                    # Handle different types properly
                    if configured_device is not None:
                        if isinstance(configured_device, str):
                            # Handle string configurations
                            if configured_device.strip() == "":
                                sound_device = None  # Empty string means default device
                            elif configured_device.isdigit():
                                sound_device = int(configured_device)  # Convert numeric string to int
                            else:
                                sound_device = configured_device  # Use as device name
                        else:
                            # Direct integer or other value
                            sound_device = configured_device
                except Exception:
                    sound_device = None  # Fall back to default device
                
                with sd.InputStream(samplerate=self.sample_rate, channels=1, dtype='int16',
                                  blocksize=frame_size, device=sound_device,
                                  callback=audio_callback):
                                      
                    # Wait for first callback data with a short timeout
                    if data_ready.wait(timeout=0.2):
                        # We received first data - we're ready to record
                        data_ready.clear()
                        current_time_ms = int(time.time() * 1000)
                        startup_time_ms = current_time_ms - start_time_ms
                        ConfigManager.console_print(f"Recording ready in {startup_time_ms}ms")
                        self.statusSignal.emit('ready')
                        
                        # Play a brief beep to indicate recording is ready
                        try:
                            if os.path.exists(os.path.join('assets', 'beep.wav')):
                                from audioplayer import AudioPlayer
                                AudioPlayer(os.path.join('assets', 'beep.wav')).play(block=False)
                        except Exception:
                            pass  # Ignore beep errors
                    
                    # Force a minimum recording time to ensure we get some samples
                    min_record_time_seconds = 1.0
                    have_data = False
                    
                    # Main recording loop
                    while self.is_running and self.is_recording:
                        # Force minimum recording time
                        current_time = time.time()
                        elapsed_time = (current_time * 1000 - start_time_ms) / 1000.0
                        
                        if not data_ready.wait(timeout=0.1):  # Shorter timeout for faster response
                            continue
                            
                        data_ready.clear()
                        have_data = True

                        # Process a frame of data if we have enough
                        while len(audio_buffer) >= frame_size:
                            # Extract a frame and add to recording
                            frame = np.array(audio_buffer[:frame_size], dtype=np.int16)
                            recording.extend(frame)
                            
                            # Remove the processed frame from buffer
                            audio_buffer = audio_buffer[frame_size:]

                            # Avoid trying to detect voice in initial frames
                            if initial_frames_to_skip > 0:
                                initial_frames_to_skip -= 1
                                continue

                            if vad and elapsed_time >= min_record_time_seconds:
                                try:
                                    is_speech = vad.is_speech(frame.tobytes(), self.sample_rate)
                                    if is_speech:
                                        silent_frame_count = 0
                                        if not speech_detected:
                                            speech_detected = True
                                            # Update status when speech is detected
                                            self.statusSignal.emit('recording')
                                    else:
                                        silent_frame_count += 1

                                    if speech_detected and silent_frame_count > silence_frames:
                                        self.is_recording = False
                                        break
                                except Exception as e:
                                    ConfigManager.console_print(f"VAD error: {str(e)}")
                        
                        # If we've reached minimum time and mode is hold_to_record, check if key is still pressed
                        if elapsed_time >= min_record_time_seconds and recording_mode == 'hold_to_record' and not self.is_recording:
                            break
                    
                    # Don't forget any remaining samples in the buffer
                    if audio_buffer:
                        recording.extend(audio_buffer)
                    
        except Exception as e:
            ConfigManager.console_print(f"Error in audio recording: {str(e)}")
        finally:
            # Make sure we turn off recording in persistent stream 
            if hasattr(ResultThread, 'audio_callback_data') and ResultThread.audio_callback_data is not None:
                ResultThread.audio_callback_data['is_recording'] = False
                
            # Always signal transcribing when done
            self.statusSignal.emit('transcribing')

        audio_data = np.array(recording, dtype=np.int16)
        duration = len(audio_data) / self.sample_rate

        ConfigManager.console_print(f'Recording finished. Size: {audio_data.size} samples, Duration: {duration:.2f} seconds')

        min_duration_ms = recording_options.get('min_duration') or 100

        if (duration * 1000) < min_duration_ms:
            ConfigManager.console_print(f'Discarded due to being too short (less than {min_duration_ms}ms).')
            return None

        return audio_data
