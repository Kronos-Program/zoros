# See architecture: docs/zoros_architecture.md#component-overview
import yaml
import os
import traceback
import json
import uuid
import datetime
import numpy as np
import soundfile as sf
from pathlib import Path
from pathlib import Path

# Add import for sounddevice
try:
    import sounddevice as sd
except ImportError:
    sd = None

class DictationManager:
    """
    Manages dictation objects including creation, storage, and retrieval.
    Implements the enhanced dictation model specified in the ZorOS requirements.
    """
    
    # Base path for storing dictations
    _dictation_base_path = Path("D:/Programming_D/zoros/data/dictations")
    
    @classmethod
    def initialize(cls):
        """Initialize the dictation storage system"""
        # Create base directory if it doesn't exist
        os.makedirs(cls._dictation_base_path, exist_ok=True)
    
    @classmethod
    def create_dictation(cls, audio_data=None, quick_transcript=None):
        """
        Create a new dictation object with the specified data
        
        Args:
            audio_data: The raw audio data as numpy array
            quick_transcript: Initial quick transcription if available
            
        Returns:
            dict: The created dictation object
        """
        dictation_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now().isoformat()
        
        # Create folder for this dictation
        dictation_folder = os.path.join(cls._dictation_base_path, dictation_id)
        os.makedirs(dictation_folder, exist_ok=True)
        
        # Save audio if provided
        audio_path = None
        if audio_data is not None:
            audio_path = os.path.join(dictation_folder, "audio.wav")
            ConfigManager.console_print(f"Saving audio to: {audio_path}")
            cls.save_audio(audio_data, audio_path)
        
        # Create dictation object
        dictation = {
            "dictation_id": dictation_id,
            "created_at": timestamp,
            "source_type": "voice",
            "audio_path": audio_path,
            "quick_transcript": quick_transcript or "",
            "full_transcript": "",
            "corrected_transcript": "",
            "accuracy": {
                "quick_to_full_wer": 0.0,
                "full_to_corrected_wer": 0.0
            },
            "status": "Draft",
            "metadata": {}
        }
        
        # Save dictation object
        cls.save_dictation(dictation)
        
        return dictation
    
    @classmethod
    def save_dictation(cls, dictation):
        """
        Save a dictation object to disk
        
        Args:
            dictation: The dictation object to save
        """
        dictation_id = dictation["dictation_id"]
        dictation_folder = os.path.join(cls._dictation_base_path, dictation_id)
        os.makedirs(dictation_folder, exist_ok=True)
        
        # Save dictation JSON
        json_path = os.path.join(dictation_folder, "dictation.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(dictation, f, indent=2, ensure_ascii=False)
            
        # Also save the quick transcript as a separate text file for convenience
        if dictation.get("quick_transcript"):
            text_path = os.path.join(dictation_folder, "transcript_quick.txt")
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(dictation["quick_transcript"])
    
    @classmethod
    def save_audio(cls, audio_data, file_path):
        """
        Save audio data to a WAV file
        
        Args:
            audio_data: Numpy array of audio data
            file_path: Path to save the WAV file
        """
        sample_rate = ConfigManager.get_config_section('recording_options').get('sample_rate') or 16000
        sf.write(file_path, audio_data, sample_rate)
    
    @classmethod
    def list_dictations(cls):
        """
        List all dictations in the storage
        
        Returns:
            list: List of dictation objects
        """
        dictations = []
        
        if not os.path.exists(cls._dictation_base_path):
            return dictations
            
        for item in os.listdir(cls._dictation_base_path):
            dictation_folder = os.path.join(cls._dictation_base_path, item)
            if os.path.isdir(dictation_folder):
                json_path = os.path.join(dictation_folder, "dictation.json")
                if os.path.exists(json_path):
                    try:
                        with open(json_path, 'r', encoding='utf-8') as f:
                            dictation = json.load(f)
                            dictations.append(dictation)
                    except Exception as e:
                        ConfigManager.console_print(f"Error loading dictation {item}: {str(e)}")
        
        # Sort by creation date (newest first)
        dictations.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return dictations
        
    @classmethod
    def get_dictation(cls, dictation_id):
        """
        Get a specific dictation by ID
        
        Args:
            dictation_id: ID of the dictation to retrieve
            
        Returns:
            dict: The dictation object or None if not found
        """
        json_path = os.path.join(cls._dictation_base_path, dictation_id, "dictation.json")
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                ConfigManager.console_print(f"Error loading dictation {dictation_id}: {str(e)}")
        return None
        
    @classmethod
    def update_dictation(cls, dictation_id, **updates):
        """
        Update fields in a dictation
        
        Args:
            dictation_id: ID of the dictation to update
            **updates: Field updates as keyword arguments
            
        Returns:
            dict: The updated dictation or None if not found
        """
        dictation = cls.get_dictation(dictation_id)
        if dictation:
            # Update the specified fields
            for key, value in updates.items():
                if key == "metadata" and isinstance(value, dict):
                    # Merge metadata rather than replace
                    dictation["metadata"].update(value)
                else:
                    dictation[key] = value
            
            # Save the updated dictation
            cls.save_dictation(dictation)
            return dictation
        return None
    
    @classmethod
    def delete_dictation(cls, dictation_id):
        """
        Delete a dictation by ID, removing all associated files and folders
        
        Args:
            dictation_id: ID of the dictation to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        dictation_folder = os.path.join(cls._dictation_base_path, dictation_id)
        if not os.path.exists(dictation_folder):
            ConfigManager.console_print(f"Dictation folder not found: {dictation_folder}")
            return False
            
        try:
            # Track any errors for files we couldn't delete
            failed_files = []
            
            # Delete all files in the dictation folder
            for item in os.listdir(dictation_folder):
                item_path = os.path.join(dictation_folder, item)
                try:
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                    elif os.path.isdir(item_path):
                        import shutil
                        shutil.rmtree(item_path)
                except Exception as e:
                    # Log the error but continue with other files
                    ConfigManager.console_print(f"Error deleting {item_path}: {str(e)}")
                    failed_files.append(item_path)
            
            # Only remove the folder if all files were deleted
            if not failed_files:
                try:
                    os.rmdir(dictation_folder)
                    ConfigManager.console_print(f"Deleted dictation: {dictation_id}")
                    return True
                except Exception as e:
                    ConfigManager.console_print(f"Error removing folder {dictation_folder}: {str(e)}")
                    return False
            else:
                ConfigManager.console_print(f"Partial deletion of dictation {dictation_id}: Some files could not be deleted")
                return False
                
        except Exception as e:
            ConfigManager.console_print(f"Error deleting dictation {dictation_id}: {str(e)}")
            traceback.print_exc()
            return False

class ConfigManager:
    _instance = None

    def __init__(self):
        """Initialize the ConfigManager instance."""
        self.config = None
        self.schema = None

    @classmethod
    def initialize(cls, schema_path=None):
        """Initialize the ConfigManager with the given schema path."""
        if cls._instance is None:
            cls._instance = cls()
            cls._instance.schema = cls._instance.load_config_schema(schema_path)
            cls._instance.config = cls._instance.load_default_config()
            cls._instance.load_user_config()
            
            # Log available audio devices on startup
            cls.log_audio_devices()

    @classmethod
    def find_device_by_name_pattern(cls, pattern, hostapi=None):
        """Find an audio device by a name pattern and optionally hostapi.
        
        Args:
            pattern (str): A substring to match in device names
            hostapi (int, optional): The hostapi index to match, if provided
            
        Returns:
            int or None: The device index if found, None otherwise
        """
        if sd is None:
            cls.console_print("sounddevice library not available")
            return None
            
        try:
            devices = sd.query_devices()
            # Case-insensitive matching
            pattern = pattern.lower()
            
            # First try to parse pattern for device:hostapi format
            device_hostapi = None
            if isinstance(pattern, str) and ':' in pattern:
                parts = pattern.split(':', 1)
                if len(parts) == 2 and parts[1].strip().isdigit():
                    pattern = parts[0].strip()
                    device_hostapi = int(parts[1].strip())
                    cls.console_print(f"Detected device:hostapi format. Looking for pattern '{pattern}' with hostapi {device_hostapi}")
            
            # Use provided hostapi if device_hostapi wasn't in the pattern
            if device_hostapi is None:
                device_hostapi = hostapi
            
            # First pass: look for exact matches with hostapi if specified
            for i, device in enumerate(devices):
                device_name = device.get('name', '').lower()
                device_api = device.get('hostapi', None)
                
                # Check for exact match considering hostapi if specified
                if pattern == device_name:
                    # If hostapi is specified, it must match
                    if device_hostapi is not None and device_api != device_hostapi:
                        continue
                    
                    cls.console_print(f"Found exact device match: {device.get('name', '')} (index {i}, hostapi {device_api})")
                    return i
            
            # Second pass: look for partial matches with hostapi if specified
            for i, device in enumerate(devices):
                device_name = device.get('name', '').lower()
                device_api = device.get('hostapi', None)
                
                if pattern in device_name:
                    # If hostapi is specified, it must match
                    if device_hostapi is not None and device_api != device_hostapi:
                        continue
                    
                    cls.console_print(f"Found partial device match: {device.get('name', '')} (index {i}, hostapi {device_api})")
                    return i
            
            cls.console_print(f"No audio device matching '{pattern}'{' with hostapi ' + str(device_hostapi) if device_hostapi is not None else ''} found")
            return None
            
        except Exception as e:
            cls.console_print(f"Error finding audio device: {str(e)}")
            return None

    @classmethod
    def log_audio_devices(cls):
        """Log all available audio devices for debugging purposes."""        
        if sd is None:
            cls.console_print("sounddevice library not available")
            return
            
        try:
            cls.console_print("=== Available Audio Devices ===")
            devices = sd.query_devices()
            for i, device in enumerate(devices):
                # Extract device name and relevant info
                device_name = device.get('name', 'Unknown')
                device_api = device.get('hostapi', -1)
                inputs = device.get('max_input_channels', 0)
                outputs = device.get('max_output_channels', 0)
                cls.console_print(f"Device #{i}: {device_name} (Inputs: {inputs}, Outputs: {outputs}, HostAPI: {device_api})")
            cls.console_print("===============================")
            
            # Get current configured device
            recording_options = cls.get_config_section('recording_options')
            sound_device = recording_options.get('sound_device')
            cls.console_print(f"Currently configured sound_device: {sound_device} (type: {type(sound_device).__name__})")
        except Exception as e:
            cls.console_print(f"Error listing audio devices: {str(e)}")
            traceback.print_exc()

    @classmethod
    def get_schema(cls):
        """Get the configuration schema."""
        if cls._instance is None:
            raise RuntimeError("ConfigManager not initialized")
        return cls._instance.schema

    @classmethod
    def get_config_section(cls, *keys):
        """Get a specific section of the configuration."""
        if cls._instance is None:
            raise RuntimeError("ConfigManager not initialized")

        section = cls._instance.config
        for key in keys:
            if isinstance(section, dict) and key in section:
                section = section[key]
            else:
                return {}
        return section

    @classmethod
    def get_config_value(cls, *keys):
        """Get a specific configuration value using nested keys."""
        if cls._instance is None:
            raise RuntimeError("ConfigManager not initialized")

        value = cls._instance.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        return value

    @classmethod
    def set_config_value(cls, value, *keys):
        """Set a specific configuration value using nested keys."""        
        if cls._instance is None:
            raise RuntimeError("ConfigManager not initialized")

        config = cls._instance.config
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            elif not isinstance(config[key], dict):
                config[key] = {}
            config = config[key]
        config[keys[-1]] = value

    @staticmethod
    def load_config_schema(schema_path=None):
        """Load the configuration schema from a YAML file."""
        if schema_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            schema_path = os.path.join(base_dir, 'config_schema.yaml')

        with open(schema_path, 'r') as file:
            schema = yaml.safe_load(file)
        return schema

    def load_default_config(self):
        """Load default configuration values from the schema."""
        def extract_value(item):
            if isinstance(item, dict):
                if 'value' in item:
                    return item['value']
                else:
                    return {k: extract_value(v) for k, v in item.items()}
            return item

        config = {}
        for category, settings in self.schema.items():
            config[category] = extract_value(settings)
        return config

    def load_user_config(self, config_path=None):
        """Load user configuration and merge with default config."""
        def deep_update(source, overrides):
            for key, value in overrides.items():
                if isinstance(value, dict) and key in source:
                    deep_update(source[key], value)
                else:
                    source[key] = value

        # Better config path handling - try multiple locations
        paths_to_try = []
        
        # Use provided path if specified
        if config_path:
            paths_to_try.append(config_path)
            
        # Add standard locations
        base_dir = os.path.dirname(os.path.abspath(__file__))
        paths_to_try.extend([
            os.path.join(base_dir, 'config.yaml'),  # Same dir as this file
            os.path.join('source', 'modules', 'whisper', 'src', 'config.yaml'),
            os.path.join(os.getcwd(), 'source', 'modules', 'whisper', 'src', 'config.yaml')
        ])
        
        # Debug config file search
        for path in paths_to_try:
            if os.path.isfile(path):
                print(f"Found config file at: {path}")
                try:
                    with open(path, 'r') as file:
                        print(f"Opening config file: {path}")
                        user_config = yaml.safe_load(file)
                        if user_config:
                            print(f"Loaded config with keys: {list(user_config.keys())}")
                            if 'recording_options' in user_config:
                                print(f"recording_options: {user_config['recording_options']}")
                            deep_update(self.config, user_config)
                            return  # Successfully loaded config
                        else:
                            print(f"Config file at {path} is empty or invalid")
                except yaml.YAMLError as e:
                    print(f"Error parsing config file {path}: {str(e)}")
                except Exception as e:
                    print(f"Error loading config file {path}: {str(e)}")
        
        print("Warning: No valid config file found in any location. Using default configuration.")

    @classmethod
    def save_config(cls, config_path=os.path.join('source', 'modules', 'whisper', 'src', 'config.yaml')):
        """Save the current configuration to a YAML file."""
        if cls._instance is None:
            raise RuntimeError("ConfigManager not initialized")
        with open(config_path, 'w') as file:
            yaml.dump(cls._instance.config, file, default_flow_style=False)

    @classmethod
    def reload_config(cls):
        """
        Reload the configuration from the file.
        """
        if cls._instance is None:
            raise RuntimeError("ConfigManager not initialized")
        cls._instance.config = cls._instance.load_default_config()
        cls._instance.load_user_config()

    @classmethod
    def config_file_exists(cls):
        """Check if a valid config file exists."""
        config_path = os.path.join('source', 'modules', 'whisper', 'src', 'config.yaml')
        return os.path.isfile(config_path)

    @classmethod
    def console_print(cls, message):
        """Print a message to the console if enabled in the configuration."""
        if cls._instance and cls._instance.config['misc'].get('print_to_terminal', True):
            print(message)

    @classmethod
    def is_debug_enabled(cls):
        """Return True if debug logging is enabled in the configuration."""
        return bool(cls._instance and cls._instance.config['misc'].get('debug_logging', False))

    @classmethod
    def debug_print(cls, message):
        """Print a debug message when debug logging is enabled."""
        if cls.is_debug_enabled():
            print(message)
