#!/usr/bin/env python3
"""
🧪 Test Live Transcription Integration
Test the complete live transcription pipeline with model preloading.
"""

import time
import sys
import os
import logging
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, os.getcwd())

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_model_preloading():
    """Test model preloading functionality."""
    logger.info("🔥 Testing model preloading...")
    
    try:
        from source.dictation_backends.mlx_whisper_backend import MLXWhisperBackend
        
        # Test cold start
        logger.info("❄️ Testing cold start...")
        cold_start = time.time()
        backend1 = MLXWhisperBackend("large-v3-turbo")
        cold_time = time.time() - cold_start
        
        # Test warm start (should reuse)
        logger.info("🔥 Testing warm start...")
        warm_start = time.time()
        backend2 = MLXWhisperBackend("large-v3-turbo")
        warm_time = time.time() - warm_start
        
        logger.info(f"✅ Cold start: {cold_time:.2f}s")
        logger.info(f"✅ Warm start: {warm_time:.2f}s")
        logger.info(f"🚀 Speedup: {cold_time/warm_time:.1f}x faster")
        
        return backend1
        
    except Exception as e:
        logger.error(f"❌ Model preloading test failed: {e}")
        return None

def test_live_processor():
    """Test live chunk processor functionality."""
    logger.info("🎬 Testing live chunk processor...")
    
    try:
        from source.dictation_backends.live_chunk_processor import LiveChunkProcessor
        from source.dictation_backends.mlx_whisper_backend import MLXWhisperBackend
        import numpy as np
        
        # Create backend instance
        backend = MLXWhisperBackend("large-v3-turbo")
        logger.info("✅ Backend created")
        
        # Create live processor
        processor = LiveChunkProcessor(
            backend_instance=backend,
            chunk_duration=2.0,  # Short chunks for testing
            overlap_duration=0.3,
            max_buffer_chunks=3
        )
        logger.info("✅ Live processor created")
        
        # Test callback for updates
        update_count = 0
        def test_callback(transcript):
            nonlocal update_count
            update_count += 1
            logger.info(f"📝 Live update {update_count}: {len(transcript)} chars")
        
        # Start processing
        processor.start_processing(update_callback=test_callback)
        logger.info("✅ Processing started")
        
        # Simulate audio data
        sample_rate = 16000
        for i in range(5):  # 5 chunks of data
            # Generate dummy audio (1 second each)
            audio_data = np.random.normal(0, 0.1, sample_rate)
            processor.add_audio_chunk(audio_data)
            logger.info(f"📦 Added audio chunk {i+1}")
            time.sleep(0.1)  # Small delay
        
        # Let it process
        time.sleep(3.0)
        
        # Stop and get results
        final_transcript = processor.stop_processing()
        stats = processor.get_performance_stats()
        
        logger.info(f"✅ Final transcript: {len(final_transcript)} chars")
        logger.info(f"📊 Stats: {stats}")
        
        processor.cleanup()
        return True
        
    except Exception as e:
        logger.error(f"❌ Live processor test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_audio_file_processing():
    """Test live processing with actual audio file."""
    logger.info("🎵 Testing with actual audio file...")
    
    audio_file = "tests/assets/dictation-f151869f-d8d8-4b9a-91d3-1f9b04498f76-135s-1751631986.wav"
    
    if not Path(audio_file).exists():
        logger.warning(f"⚠️ Audio file not found: {audio_file}")
        return False
    
    try:
        from source.dictation_backends.live_chunk_processor import LiveChunkProcessor
        from source.dictation_backends.mlx_whisper_backend import MLXWhisperBackend
        import soundfile as sf
        import numpy as np
        
        # Create backend
        backend = MLXWhisperBackend("large-v3-turbo")
        
        # Create processor
        processor = LiveChunkProcessor(
            backend_instance=backend,
            chunk_duration=5.0,  # 5-second chunks
            overlap_duration=0.5,
            max_buffer_chunks=10
        )
        
        updates = []
        def track_updates(transcript):
            updates.append({
                'time': time.time(),
                'length': len(transcript),
                'preview': transcript[:50]
            })
            logger.info(f"📝 Live update: {len(transcript)} chars - '{transcript[:50]}...'")
        
        # Start processing
        start_time = time.time()
        processor.start_processing(update_callback=track_updates)
        
        # Load and feed audio data in chunks
        with sf.SoundFile(audio_file) as f:
            audio_data = f.read()
            sample_rate = f.samplerate
            
            logger.info(f"🎵 Audio: {len(audio_data)/sample_rate:.1f}s, {sample_rate}Hz")
            
            # Feed in 1-second chunks to simulate real-time
            chunk_size = sample_rate  # 1 second
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i+chunk_size]
                processor.add_audio_chunk(chunk)
                
                # Small delay to simulate real-time
                time.sleep(0.1)
                
                if i % (chunk_size * 10) == 0:  # Every 10 seconds
                    logger.info(f"🎵 Fed {i/sample_rate:.1f}s of audio")
        
        logger.info("🎵 Finished feeding audio, processing final chunks...")
        
        # Stop and get final result
        final_transcript = processor.stop_processing()
        end_time = time.time()
        
        total_time = end_time - start_time
        audio_duration = len(audio_data) / sample_rate
        
        logger.info(f"✅ LIVE PROCESSING COMPLETE:")
        logger.info(f"   Audio duration: {audio_duration:.1f}s")
        logger.info(f"   Processing time: {total_time:.2f}s")
        logger.info(f"   RTF: {total_time/audio_duration:.3f}x")
        logger.info(f"   Live updates: {len(updates)}")
        logger.info(f"   Final transcript: {len(final_transcript)} chars")
        logger.info(f"   Preview: '{final_transcript[:100]}...'")
        
        # Check if we achieved target
        if total_time <= 10:
            logger.info(f"🎯 TARGET ACHIEVED! {total_time:.2f}s ≤ 10s")
        else:
            logger.info(f"⏰ Target missed by {total_time - 10:.2f}s")
        
        processor.cleanup()
        return True
        
    except Exception as e:
        logger.error(f"❌ Audio file test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all live transcription tests."""
    logger.info("🧪 LIVE TRANSCRIPTION INTEGRATION TESTS")
    logger.info("="*60)
    
    results = {}
    
    # Test 1: Model preloading
    logger.info("\n1️⃣ Testing model preloading...")
    backend = test_model_preloading()
    results['model_preloading'] = backend is not None
    
    # Test 2: Live processor
    logger.info("\n2️⃣ Testing live processor...")
    results['live_processor'] = test_live_processor()
    
    # Test 3: Audio file processing
    logger.info("\n3️⃣ Testing with audio file...")
    results['audio_file'] = test_audio_file_processing()
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("🧪 TEST RESULTS SUMMARY")
    logger.info("="*60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"   {test_name}: {status}")
    
    all_passed = all(results.values())
    if all_passed:
        logger.info("🎉 ALL TESTS PASSED! Live transcription integration ready!")
    else:
        logger.info("⚠️ Some tests failed. Check logs for details.")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)