# See architecture: docs/zoros_architecture.md#component-overview
import os
import sys
import argparse
from PySide6.QtWidgets import QApplication

from main import WhisperWriterApp
from utils import ConfigManager

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='WhisperWriter speech-to-text application')
    parser.add_argument('--headless', action='store_true', help='Run without main UI (only status window and keyboard listener)')
    parser.add_argument('--ui', action='store_true', help='Run with full UI (overrides headless)')
    parser.add_argument('--settings', action='store_true', help='Open settings window directly')
    parser.add_argument('--device', type=str, help='Specify audio input device')
    parser.add_argument('--save-to-file', action='store_true', help='Save transcriptions to file')
    parser.add_argument('--no-hotkey', action='store_true', help='Disable hotkeys and control recording via UI')
    args = parser.parse_args()
    
    # If both --ui and --headless are provided, --ui takes precedence
    if args.ui:
        args.headless = False
    
    # Update config with command line arguments before initializing the app
    if args.device:
        print(f"Setting audio device to: {args.device}")
        ConfigManager.initialize()
        ConfigManager.set_config_value(args.device, "recording_options", "sound_device")
        ConfigManager.save_config()
    
    if args.save_to_file:
        print("Enabling transcription save to file")
        ConfigManager.initialize()
        ConfigManager.set_config_value(True, "post_processing", "save_to_file")
        ConfigManager.save_config()
    
    # Initialize and run the application
    app = WhisperWriterApp(no_hotkey=args.no_hotkey)
    return app.run()

if __name__ == '__main__':
    sys.exit(main())
