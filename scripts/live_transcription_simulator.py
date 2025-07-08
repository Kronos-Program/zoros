#!/usr/bin/env python3
"""
🎬 LIVE TRANSCRIPTION SIMULATOR 🎬
Simulate the ultimate dictation experience: transcribe while "recording"

This script simulates feeding audio data to the live transcription backend
in real-time, as if it was coming from a microphone during recording.

Target: Complete transcription within 5-10 seconds of "stop recording"
"""

import time
import logging
import numpy as np
import soundfile as sf
from pathlib import Path
from typing import Dict, Any
import sys
import os

# Add current directory to path for imports
sys.path.insert(0, os.getcwd())

from source.dictation_backends.live_transcription_backend import LiveTranscriptionBackend

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LiveTranscriptionSimulator:
    """Simulator for live transcription during recording."""
    
    def __init__(self, audio_file: str):
        self.audio_file = Path(audio_file)
        self.audio_data = None
        self.audio_duration = 0
        self.sample_rate = 16000
        
        # Load audio file
        self._load_audio()
        
        # Live updates callback
        self.live_updates = []
        
        logger.info(f"🎬 Live Transcription Simulator")
        logger.info(f"🎵 Audio: {self.audio_file.name}")
        logger.info(f"⏱️  Duration: {self.audio_duration:.2f}s")
    
    def _load_audio(self):
        """Load audio file data."""
        with sf.SoundFile(self.audio_file) as f:
            self.audio_data = f.read()
            self.sample_rate = f.samplerate
            self.audio_duration = len(self.audio_data) / self.sample_rate
    
    def _live_transcript_callback(self, transcript: str, metadata: Dict):
        """Callback for live transcript updates."""
        self.live_updates.append({
            'timestamp': time.time(),
            'transcript': transcript,
            'metadata': metadata
        })
        
        logger.info(f"📝 Live update {metadata['chunk_id']}: {len(transcript)} chars")
        logger.debug(f"   Preview: {transcript[:100]}...")
    
    def simulate_recording_speed(self, speed_factor: float = 1.0) -> Dict[str, Any]:
        """Simulate recording at different speeds (1.0 = real-time, 2.0 = 2x speed, etc.)"""
        logger.info(f"🎬 SIMULATING RECORDING AT {speed_factor}x SPEED")
        
        # Create live transcription backend
        backend = LiveTranscriptionBackend(
            chunk_duration=3.0,
            overlap_duration=0.5,
            max_workers=3,
            buffer_size=15
        )
        
        # Start streaming
        recording_start = time.time()
        backend.start_streaming(callback=self._live_transcript_callback)
        
        # Simulate feeding audio data in real-time chunks
        chunk_size = int(0.1 * self.sample_rate)  # 100ms chunks
        real_time_delay = 0.1 / speed_factor  # Adjust delay based on speed factor
        
        total_chunks = len(self.audio_data) // chunk_size
        logger.info(f"📦 Feeding {total_chunks} audio chunks at {speed_factor}x speed...")
        
        for i in range(0, len(self.audio_data), chunk_size):
            chunk = self.audio_data[i:i+chunk_size]
            backend.add_audio_data(chunk)
            
            # Simulate real-time delay
            if speed_factor < 10:  # Don't delay for very fast simulations
                time.sleep(real_time_delay)
            
            # Log progress
            if i % (chunk_size * 50) == 0:  # Every 5 seconds of audio
                progress = (i / len(self.audio_data)) * 100
                logger.info(f"🎵 Recording progress: {progress:.1f}%")
        
        recording_end = time.time()
        recording_time = recording_end - recording_start
        
        logger.info(f"🛑 STOP RECORDING (after {recording_time:.2f}s)")
        
        # Stop streaming and get final result
        stop_start = time.time()
        final_transcript = backend.stop_streaming()
        stop_end = time.time()
        
        stop_processing_time = stop_end - stop_start
        total_time = stop_end - recording_start
        
        # Get performance stats
        stats = backend.get_performance_stats()
        
        # Clean up
        backend.cleanup()
        
        # Calculate results
        result = {
            'speed_factor': speed_factor,
            'audio_duration': self.audio_duration,
            'recording_time': recording_time,
            'stop_processing_time': stop_processing_time,
            'total_time': total_time,
            'final_transcript': final_transcript,
            'transcript_length': len(final_transcript),
            'live_updates_count': len(self.live_updates),
            'performance_stats': stats,
            'success': len(final_transcript) > 0
        }
        
        return result
    
    def run_speed_tests(self) -> Dict[str, Any]:
        """Run tests at different recording speeds."""
        logger.info("🚀 RUNNING LIVE TRANSCRIPTION SPEED TESTS")
        
        # Test different recording speeds
        speed_factors = [1.0, 2.0, 5.0, 10.0]  # Real-time to 10x speed
        results = {}
        
        for speed in speed_factors:
            logger.info(f"\n{'='*60}")
            logger.info(f"TESTING SPEED FACTOR: {speed}x")
            logger.info(f"{'='*60}")
            
            # Reset live updates for each test
            self.live_updates = []
            
            try:
                result = self.simulate_recording_speed(speed)
                results[f"speed_{speed}x"] = result
                
                logger.info(f"✅ Speed {speed}x Results:")
                logger.info(f"   Recording time: {result['recording_time']:.2f}s")
                logger.info(f"   Stop processing: {result['stop_processing_time']:.2f}s")
                logger.info(f"   Total time: {result['total_time']:.2f}s")
                logger.info(f"   Transcript length: {result['transcript_length']} chars")
                
                # Check if we hit the target
                if result['stop_processing_time'] <= 10:
                    logger.info(f"🎯 TARGET ACHIEVED! Stop processing: {result['stop_processing_time']:.2f}s ≤ 10s")
                else:
                    logger.info(f"⏰ Target missed by {result['stop_processing_time'] - 10:.2f}s")
                
            except Exception as e:
                logger.error(f"❌ Speed {speed}x failed: {e}")
                results[f"speed_{speed}x"] = {'success': False, 'error': str(e)}
        
        return results
    
    def find_optimal_configuration(self) -> Dict[str, Any]:
        """Find the optimal configuration for minimum stop processing time."""
        logger.info("🎯 FINDING OPTIMAL CONFIGURATION")
        
        configurations = [
            {'chunk_duration': 2.0, 'overlap': 0.3, 'workers': 4, 'buffer': 20},
            {'chunk_duration': 1.5, 'overlap': 0.2, 'workers': 6, 'buffer': 25},
            {'chunk_duration': 1.0, 'overlap': 0.1, 'workers': 8, 'buffer': 30},
            {'chunk_duration': 0.5, 'overlap': 0.05, 'workers': 10, 'buffer': 40},
        ]
        
        best_result = None
        best_stop_time = float('inf')
        
        for i, config in enumerate(configurations):
            logger.info(f"\n📊 Testing configuration {i+1}/{len(configurations)}")
            logger.info(f"   Chunk: {config['chunk_duration']}s, Workers: {config['workers']}")
            
            try:
                # Create backend with this configuration
                backend = LiveTranscriptionBackend(
                    chunk_duration=config['chunk_duration'],
                    overlap_duration=config['overlap'],
                    max_workers=config['workers'],
                    buffer_size=config['buffer']
                )
                
                # Test at 5x speed for faster iteration
                result = self._test_configuration(backend, speed_factor=5.0)
                result['configuration'] = config
                
                logger.info(f"   Stop processing time: {result['stop_processing_time']:.2f}s")
                
                if result['stop_processing_time'] < best_stop_time:
                    best_stop_time = result['stop_processing_time']
                    best_result = result
                    logger.info(f"   🏆 New best configuration!")
                
                backend.cleanup()
                
            except Exception as e:
                logger.error(f"   ❌ Configuration failed: {e}")
        
        if best_result:
            logger.info(f"\n🏆 OPTIMAL CONFIGURATION FOUND:")
            logger.info(f"   Stop processing time: {best_result['stop_processing_time']:.2f}s")
            logger.info(f"   Configuration: {best_result['configuration']}")
        
        return best_result or {}
    
    def _test_configuration(self, backend: LiveTranscriptionBackend, speed_factor: float = 1.0) -> Dict[str, Any]:
        """Test a specific backend configuration."""
        # Reset live updates
        self.live_updates = []
        
        recording_start = time.time()
        backend.start_streaming(callback=self._live_transcript_callback)
        
        # Feed audio data
        chunk_size = int(0.1 * self.sample_rate)
        real_time_delay = 0.1 / speed_factor
        
        for i in range(0, len(self.audio_data), chunk_size):
            chunk = self.audio_data[i:i+chunk_size]
            backend.add_audio_data(chunk)
            
            if speed_factor < 10:
                time.sleep(real_time_delay)
        
        recording_end = time.time()
        recording_time = recording_end - recording_start
        
        # Stop and measure
        stop_start = time.time()
        final_transcript = backend.stop_streaming()
        stop_end = time.time()
        
        stop_processing_time = stop_end - stop_start
        
        return {
            'recording_time': recording_time,
            'stop_processing_time': stop_processing_time,
            'transcript_length': len(final_transcript),
            'success': len(final_transcript) > 0
        }


def main():
    """Run the live transcription simulation."""
    audio_file = "tests/assets/dictation-f151869f-d8d8-4b9a-91d3-1f9b04498f76-135s-1751631986.wav"
    
    if not Path(audio_file).exists():
        logger.error(f"❌ Audio file not found: {audio_file}")
        return
    
    simulator = LiveTranscriptionSimulator(audio_file)
    
    # Run speed tests
    logger.info("🎬 Starting live transcription simulation...")
    speed_results = simulator.run_speed_tests()
    
    # Find optimal configuration
    optimal_config = simulator.find_optimal_configuration()
    
    # Generate final report
    logger.info("\n" + "="*80)
    logger.info("🎯 LIVE TRANSCRIPTION SIMULATION RESULTS")
    logger.info("="*80)
    
    for speed_test, result in speed_results.items():
        if result.get('success'):
            logger.info(f"{speed_test}: Stop processing = {result['stop_processing_time']:.2f}s")
    
    if optimal_config:
        logger.info(f"\n🏆 Best configuration: {optimal_config['stop_processing_time']:.2f}s stop processing")
    
    # Check if target achieved
    best_time = min([r['stop_processing_time'] for r in speed_results.values() if r.get('success')], default=float('inf'))
    
    if best_time <= 10:
        logger.info(f"🎉 TARGET ACHIEVED! Best stop processing time: {best_time:.2f}s")
    else:
        logger.info(f"🎯 Target missed. Best time: {best_time:.2f}s (need {best_time - 10:.2f}s improvement)")


if __name__ == "__main__":
    main()