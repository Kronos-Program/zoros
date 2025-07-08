#!/usr/bin/env python3
"""
Audio File Management Script

This script provides utilities for managing audio files for testing:
- Copy latest recorded audio to test assets
- List available test audio files
- Generate test audio files of various lengths
- Clean up old test files
- List dictations from database
- List temp files

Spec: docs/streaming_backend_plan.md#test-data
Tests: tests/test_transcription_performance.py
Integration: source/interfaces/intake/main.py

Usage:
    python scripts/audio_file_manager.py --copy-latest
    python scripts/audio_file_manager.py --list
    python scripts/audio_file_manager.py --list-db
    python scripts/audio_file_manager.py --list-temp
    python scripts/audio_file_manager.py --generate 60
    python scripts/audio_file_manager.py --cleanup
"""

import argparse
import shutil
import time
import sqlite3
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any
import numpy as np
import soundfile as sf


class AudioFileManager:
    """Manage audio files for testing and benchmarking."""
    
    def __init__(self):
        self.test_assets_dir = Path("tests/assets")
        self.audio_dir = Path("audio/intake")
        self.db_path = Path("zoros_intake.db")
        self.test_assets_dir.mkdir(parents=True, exist_ok=True)
    
    def get_latest_audio_file(self) -> Optional[Path]:
        """Get the most recently created audio file from the intake directory."""
        if not self.audio_dir.exists():
            print(f"Audio directory not found: {self.audio_dir}")
            return None
        
        # Find all .wav files in the intake directory
        audio_files = list(self.audio_dir.glob("*.wav"))
        
        if not audio_files:
            print(f"No audio files found in {self.audio_dir}")
            return None
        
        # Sort by modification time (newest first)
        latest_file = max(audio_files, key=lambda f: f.stat().st_mtime)
        
        print(f"Latest audio file: {latest_file}")
        print(f"Modified: {time.ctime(latest_file.stat().st_mtime)}")
        print(f"Size: {latest_file.stat().st_size / 1024:.1f} KB")
        
        return latest_file
    
    def list_dictations_from_db(self) -> List[Dict[str, Any]]:
        """List all dictations from the database with audio files."""
        dictations = []
        
        if not self.db_path.exists():
            print(f"Database not found: {self.db_path}")
            return dictations
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT id, timestamp, content, audio_path, fiber_type 
                    FROM intake 
                    WHERE audio_path IS NOT NULL AND audio_path != ''
                    ORDER BY timestamp DESC
                """)
                
                for row in cursor.fetchall():
                    dictation = {
                        'id': row[0],
                        'timestamp': row[1],
                        'content': row[2],
                        'audio_path': row[3],
                        'fiber_type': row[4],
                        'duration': 0.0,
                        'file_exists': False,
                        'file_size': 0
                    }
                    
                    # Check if audio file exists and get info
                    if dictation['audio_path']:
                        audio_path = Path(dictation['audio_path'])
                        if audio_path.exists():
                            dictation['file_exists'] = True
                            dictation['file_size'] = audio_path.stat().st_size / 1024  # KB
                            dictation['duration'] = self.get_audio_duration(audio_path)
                    
                    dictations.append(dictation)
                    
        except Exception as e:
            print(f"Error reading database: {e}")
        
        return dictations
    
    def list_temp_files(self) -> List[Path]:
        """List temporary audio files in the system temp directory."""
        temp_files = []
        temp_dir = Path(tempfile.gettempdir())
        
        # Look for common temp file patterns
        patterns = ["tmp_*.wav", "chunk_*.wav", "*_temp.wav"]
        
        for pattern in patterns:
            temp_files.extend(temp_dir.glob(pattern))
        
        # Sort by modification time (newest first)
        temp_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        
        return temp_files
    
    def copy_dictation_to_test_assets(self, dictation_id: str, filename: Optional[str] = None) -> Optional[Path]:
        """Copy a dictation's audio file to test assets directory."""
        if not self.db_path.exists():
            print(f"Database not found: {self.db_path}")
            return None
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT audio_path FROM intake WHERE id = ?",
                    (dictation_id,)
                )
                row = cursor.fetchone()
                
                if not row or not row[0]:
                    print(f"No audio file found for dictation {dictation_id}")
                    return None
                
                source_path = Path(row[0])
                if not source_path.exists():
                    print(f"Audio file not found: {source_path}")
                    return None
                
                # Generate filename if not provided
                if not filename:
                    duration = self.get_audio_duration(source_path)
                    timestamp = int(time.time())
                    filename = f"dictation-{dictation_id}-{duration:.0f}s-{timestamp}.wav"
                
                dest_path = self.test_assets_dir / filename
                
                # Copy file
                shutil.copy2(source_path, dest_path)
                print(f"✅ Copied dictation {dictation_id} to {dest_path}")
                
                # Verify the copy
                if dest_path.exists():
                    print(f"✅ Verification: {dest_path} exists")
                    print(f"   Size: {dest_path.stat().st_size / 1024:.1f} KB")
                    print(f"   Duration: {self.get_audio_duration(dest_path):.2f}s")
                    return dest_path
                else:
                    print(f"❌ Copy failed: {dest_path} does not exist")
                    return None
                    
        except Exception as e:
            print(f"❌ Error copying dictation: {e}")
            return None
    
    def copy_latest_to_test_assets(self, filename: Optional[str] = None) -> Optional[Path]:
        """Copy the latest audio file to test assets directory."""
        latest_file = self.get_latest_audio_file()
        
        if not latest_file:
            return None
        
        # Generate filename if not provided
        if not filename:
            timestamp = int(time.time())
            duration = self.get_audio_duration(latest_file)
            filename = f"test-{duration:.0f}s-{timestamp}.wav"
        
        dest_path = self.test_assets_dir / filename
        
        try:
            shutil.copy2(latest_file, dest_path)
            print(f"✅ Copied {latest_file} to {dest_path}")
            
            # Verify the copy
            if dest_path.exists():
                print(f"✅ Verification: {dest_path} exists")
                print(f"   Size: {dest_path.stat().st_size / 1024:.1f} KB")
                print(f"   Duration: {self.get_audio_duration(dest_path):.2f}s")
                return dest_path
            else:
                print(f"❌ Copy failed: {dest_path} does not exist")
                return None
                
        except Exception as e:
            print(f"❌ Error copying file: {e}")
            return None
    
    def get_audio_duration(self, audio_path: Path) -> float:
        """Get the duration of an audio file in seconds."""
        try:
            info = sf.info(audio_path)
            return info.duration
        except Exception as e:
            print(f"Error getting audio duration: {e}")
            return 0.0
    
    def list_test_audio_files(self) -> List[Path]:
        """List all test audio files with their details."""
        audio_files = list(self.test_assets_dir.glob("*.wav"))
        
        if not audio_files:
            print("No test audio files found.")
            return []
        
        print(f"\nTest Audio Files in {self.test_assets_dir}:")
        print("-" * 80)
        print(f"{'Filename':<30} {'Duration':<10} {'Size (KB)':<12} {'Modified':<20}")
        print("-" * 80)
        
        for audio_file in sorted(audio_files):
            try:
                duration = self.get_audio_duration(audio_file)
                size_kb = audio_file.stat().st_size / 1024
                modified = time.ctime(audio_file.stat().st_mtime)
                
                print(f"{audio_file.name:<30} {duration:<10.2f}s {size_kb:<12.1f} {modified:<20}")
            except Exception as e:
                print(f"{audio_file.name:<30} {'ERROR':<10} {'ERROR':<12} {'ERROR':<20}")
        
        return audio_files
    
    def list_dictations_table(self) -> None:
        """Display dictations from database in a table format."""
        dictations = self.list_dictations_from_db()
        
        if not dictations:
            print("No dictations with audio files found in database.")
            return
        
        print(f"\nDictations with Audio Files in Database:")
        print("-" * 100)
        print(f"{'ID':<36} {'Duration':<10} {'Size (KB)':<12} {'Type':<10} {'Exists':<6} {'Timestamp':<20}")
        print("-" * 100)
        
        for dictation in dictations:
            id_short = dictation['id'][:8] + "..." if len(dictation['id']) > 8 else dictation['id']
            duration = f"{dictation['duration']:.1f}s"
            size_kb = f"{dictation['file_size']:.1f}" if dictation['file_exists'] else "N/A"
            fiber_type = dictation['fiber_type'] or "unknown"
            exists = "✓" if dictation['file_exists'] else "✗"
            timestamp = dictation['timestamp'][:19] if dictation['timestamp'] else "N/A"
            
            print(f"{id_short:<36} {duration:<10} {size_kb:<12} {fiber_type:<10} {exists:<6} {timestamp:<20}")
    
    def list_temp_files_table(self) -> None:
        """Display temp files in a table format."""
        temp_files = self.list_temp_files()
        
        if not temp_files:
            print("No temporary audio files found.")
            return
        
        print(f"\nTemporary Audio Files in {tempfile.gettempdir()}:")
        print("-" * 80)
        print(f"{'Filename':<30} {'Duration':<10} {'Size (KB)':<12} {'Modified':<20}")
        print("-" * 80)
        
        for temp_file in temp_files:
            try:
                duration = self.get_audio_duration(temp_file)
                size_kb = temp_file.stat().st_size / 1024
                modified = time.ctime(temp_file.stat().st_mtime)
                
                print(f"{temp_file.name:<30} {duration:<10.2f}s {size_kb:<12.1f} {modified:<20}")
            except Exception as e:
                print(f"{temp_file.name:<30} {'ERROR':<10} {'ERROR':<12} {'ERROR':<20}")
    
    def generate_test_audio(self, duration_seconds: float, filename: Optional[str] = None) -> Optional[Path]:
        """Generate a test audio file with specified duration."""
        if not filename:
            timestamp = int(time.time())
            filename = f"test-generated-{duration_seconds:.0f}s-{timestamp}.wav"
        
        dest_path = self.test_assets_dir / filename
        
        try:
            # Generate a simple sine wave with some variation
            sample_rate = 16000
            samples = int(duration_seconds * sample_rate)
            
            # Create a time array
            t = np.linspace(0, duration_seconds, samples, False)
            
            # Generate a sine wave with frequency modulation
            base_freq = 440  # A4 note
            freq_mod = 0.1 * np.sin(2 * np.pi * 0.5 * t)  # Slow frequency modulation
            frequency = base_freq + freq_mod * base_freq
            
            # Generate the audio signal
            audio_data = 0.3 * np.sin(2 * np.pi * frequency * t)
            
            # Add some noise to make it more realistic
            noise = 0.01 * np.random.randn(samples)
            audio_data += noise
            
            # Ensure the audio is in the correct range
            audio_data = np.clip(audio_data, -1.0, 1.0)
            
            # Save the audio file
            sf.write(dest_path, audio_data, sample_rate)
            
            print(f"✅ Generated test audio: {dest_path}")
            print(f"   Duration: {duration_seconds:.2f}s")
            print(f"   Sample rate: {sample_rate} Hz")
            print(f"   Size: {dest_path.stat().st_size / 1024:.1f} KB")
            
            return dest_path
            
        except Exception as e:
            print(f"❌ Error generating test audio: {e}")
            return None
    
    def cleanup_old_test_files(self, days_old: int = 7) -> int:
        """Clean up test audio files older than specified days."""
        cutoff_time = time.time() - (days_old * 24 * 60 * 60)
        
        old_files = []
        for audio_file in self.test_assets_dir.glob("*.wav"):
            if audio_file.stat().st_mtime < cutoff_time:
                old_files.append(audio_file)
        
        if not old_files:
            print(f"No test files older than {days_old} days found.")
            return 0
        
        print(f"Found {len(old_files)} test files older than {days_old} days:")
        for old_file in old_files:
            print(f"  {old_file.name} ({time.ctime(old_file.stat().st_mtime)})")
        
        # Ask for confirmation
        response = input(f"\nDelete {len(old_files)} files? (y/N): ")
        if response.lower() != 'y':
            print("Cleanup cancelled.")
            return 0
        
        deleted_count = 0
        for old_file in old_files:
            try:
                old_file.unlink()
                print(f"✅ Deleted: {old_file.name}")
                deleted_count += 1
            except Exception as e:
                print(f"❌ Error deleting {old_file.name}: {e}")
        
        print(f"✅ Cleanup complete: {deleted_count} files deleted.")
        return deleted_count
    
    def suggest_test_files(self) -> None:
        """Suggest test files for different scenarios."""
        print("\nSuggested Test Files for Different Scenarios:")
        print("-" * 50)
        
        scenarios = [
            ("Short dictation", "10-30s", "Quick transcription test"),
            ("Medium dictation", "1-2min", "Standard workflow test"),
            ("Long dictation", "5-10min", "Performance and memory test"),
            ("Very long dictation", "15-30min", "Stress test for chunking"),
        ]
        
        for scenario, duration, description in scenarios:
            print(f"• {scenario}: {duration} - {description}")
        
        print("\nTo generate test files:")
        print("  python scripts/audio_file_manager.py --generate 30   # 30 seconds")
        print("  python scripts/audio_file_manager.py --generate 120  # 2 minutes")
        print("  python scripts/audio_file_manager.py --generate 600  # 10 minutes")


def main():
    """Main function for the audio file manager."""
    parser = argparse.ArgumentParser(description="Manage audio files for testing")
    parser.add_argument("--copy-latest", action="store_true", 
                       help="Copy latest recorded audio to test assets")
    parser.add_argument("--list", action="store_true",
                       help="List all test audio files")
    parser.add_argument("--list-db", action="store_true",
                       help="List dictations with audio files from database")
    parser.add_argument("--list-temp", action="store_true",
                       help="List temporary audio files")
    parser.add_argument("--generate", type=float, metavar="SECONDS",
                       help="Generate test audio file with specified duration")
    parser.add_argument("--cleanup", action="store_true",
                       help="Clean up old test files")
    parser.add_argument("--suggest", action="store_true",
                       help="Suggest test files for different scenarios")
    parser.add_argument("--copy-dictation", type=str, metavar="ID",
                       help="Copy dictation audio file to test assets by ID")
    parser.add_argument("--filename", type=str,
                       help="Custom filename for copy or generate operations")
    
    args = parser.parse_args()
    
    manager = AudioFileManager()
    
    if args.copy_latest:
        manager.copy_latest_to_test_assets(args.filename)
    
    elif args.list:
        manager.list_test_audio_files()
    
    elif args.list_db:
        manager.list_dictations_table()
    
    elif args.list_temp:
        manager.list_temp_files_table()
    
    elif args.generate is not None:
        manager.generate_test_audio(args.generate, args.filename)
    
    elif args.cleanup:
        manager.cleanup_old_test_files()
    
    elif args.suggest:
        manager.suggest_test_files()
    
    elif args.copy_dictation:
        manager.copy_dictation_to_test_assets(args.copy_dictation, args.filename)
    
    else:
        # Default: show help and current status
        print("Audio File Manager")
        print("=" * 50)
        print("Available commands:")
        print("  --list         : List test audio files")
        print("  --list-db      : List dictations from database")
        print("  --list-temp    : List temporary files")
        print("  --copy-latest  : Copy latest audio to test assets")
        print("  --copy-dictation ID : Copy dictation to test assets")
        print("  --generate SECONDS : Generate test audio")
        print("  --cleanup      : Clean up old test files")
        print("  --suggest      : Suggest test file scenarios")
        print("\nUse --help for detailed options.")


if __name__ == "__main__":
    main() 