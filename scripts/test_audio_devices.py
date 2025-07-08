#!/usr/bin/env python3
"""
Test script for audio device detection and basic recording

This script tests the audio device detection logic and basic recording
functionality to ensure the UI will work properly.

Specification: docs/requirements/dictation_requirements.md#audio-testing
Architecture: docs/zoros_architecture.md#audio-device-detection
Tests: tests/test_audio_devices.py
Integration: source/interfaces/intake/main.py#audio_device_detection

Related Modules:
- source/interfaces/intake/main.py - Audio device detection logic
- source/interfaces/intake/recorder.py - Recording functionality
- docs/audio_device_detection.md - Audio device documentation

Dependencies:
- External libraries: sounddevice, numpy, soundfile
- Internal modules: source.interfaces.intake.main
- Configuration: config/audio_settings.json
"""

import sounddevice as sd
import numpy as np
import soundfile as sf
from pathlib import Path
import tempfile


def test_audio_devices():
    """Test audio device detection and list available devices.
    
    Spec: docs/requirements/dictation_requirements.md#device-detection
    Tests: tests/test_audio_devices.py#test_device_detection
    """
    print("=== Audio Device Detection Test ===")
    
    try:
        devices = sd.query_devices()
        print(f"Total devices found: {len(devices)}")
        
        input_devices = [d for d in devices if d.get("max_input_channels", 0) > 0]
        print(f"Input devices found: {len(input_devices)}")
        
        for i, dev in enumerate(input_devices):
            print(f"  {i}: {dev['name']} (channels: {dev['max_input_channels']})")
        
        if not input_devices:
            print("ERROR: No input devices found!")
            return False
        
        print(f"✓ Audio device detection successful")
        return True
        
    except Exception as e:
        print(f"ERROR: Audio device detection failed: {e}")
        return False


def test_basic_recording(duration=3.0, device=None):
    """Test basic recording functionality.
    
    Args:
        duration: Recording duration in seconds
        device: Device index to use (None for default)
        
    Spec: docs/requirements/dictation_requirements.md#basic-recording
    Tests: tests/test_audio_devices.py#test_basic_recording
    """
    print(f"\n=== Basic Recording Test ({duration}s) ===")
    
    try:
        # Test device settings
        if device is not None:
            print(f"Testing device {device}")
            sd.check_input_settings(device=device)
        
        # Record audio
        print("Starting recording...")
        audio_data = sd.rec(int(duration * 16000), samplerate=16000, channels=1, device=device)
        sd.wait()
        
        # Check audio level
        level = float(np.abs(audio_data).mean())
        print(f"Audio level: {level:.6f}")
        
        if level > 0.00001:  # Lower threshold to match UI
            print("✓ Audio signal detected")
            
            # Save test file
            test_file = Path(tempfile.gettempdir()) / "test_recording.wav"
            sf.write(str(test_file), audio_data, 16000)
            print(f"✓ Test recording saved to: {test_file}")
            return True
        else:
            print("⚠ No audio signal detected (silence)")
            return False
            
    except Exception as e:
        print(f"ERROR: Recording test failed: {e}")
        return False


def main():
    """Main test function.
    
    Spec: docs/requirements/dictation_requirements.md#audio-testing
    Tests: tests/test_audio_devices.py#test_main
    """
    print("Audio Device and Recording Test")
    print("=" * 40)
    
    # Test device detection
    if not test_audio_devices():
        print("\n❌ Audio device detection failed")
        return
    
    # Test basic recording with default device
    if test_basic_recording(3.0):
        print("\n✓ Basic recording test passed")
    else:
        print("\n⚠ Basic recording test had issues")
    
    print("\n" + "=" * 40)
    print("Test completed!")


if __name__ == "__main__":
    main() 