# See architecture: docs/zoros_architecture.md#component-overview
import os
import sys
import soundfile as sf
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from transcription import transcribe_whisper_cpp
from utils import ConfigManager

def main():
    # Path to the audio file - should be provided as command line argument or use a test file
    audio_path = "data/dictations/sample/audio.wav"  # Example path
    
    # Load and prepare the audio file
    print(f"Loading audio file from: {audio_path}")
    audio_data, sample_rate = sf.read(audio_path)
    
    # Convert to mono if stereo
    if len(audio_data.shape) > 1:
        audio_data = audio_data.mean(axis=1)
    
    # Convert to 16-bit integers
    audio_data = (audio_data * 32767).astype(np.int16)
    
    # Initialize config
    config = ConfigManager()
    config.initialize()
    
    print("Starting transcription with whisper.cpp...")
    try:
        transcribed_text = transcribe_whisper_cpp(audio_data)
        print("\nTranscription result:")
        print("-" * 50)
        print(transcribed_text)
        print("-" * 50)
    except Exception as e:
        print(f"Error during transcription: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 
