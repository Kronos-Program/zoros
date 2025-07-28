"""
🚀 Live MLX Whisper Backend
Dedicated backend for live transcription with optimized performance.

This backend is specifically designed for real-time processing during recording,
separate from the stable MLXWhisper backend used for final transcription.
"""

from .mlx_whisper_backend import MLXWhisperBackend
from .live_chunk_processor import LiveChunkProcessor
from typing import Optional, Callable
import logging

logger = logging.getLogger(__name__)


class LiveMLXWhisperBackend(MLXWhisperBackend):
    """Live MLX Whisper backend optimized for real-time processing."""
    
    def __init__(self, model_name: str):
        super().__init__(model_name)
        self.live_processor = None
        self.is_live_mode = False
        
    def start_live_processing(self, 
                             chunk_duration: float = 2.0,
                             overlap_duration: float = 0.3,
                             update_callback: Optional[Callable[[str], None]] = None) -> None:
        """Start live processing mode for real-time transcription."""
        if self.is_live_mode:
            return
            
        logger.info("🎬 Starting live MLX processing...")
        
        try:
            self.live_processor = LiveChunkProcessor(
                backend_instance=self,
                chunk_duration=chunk_duration,
                overlap_duration=overlap_duration,
                max_buffer_chunks=3,  # Smaller buffer for live processing
                confidence_threshold=0.6  # Lower threshold for live updates
            )
            
            self.live_processor.start_processing(update_callback=update_callback)
            self.is_live_mode = True
            
            logger.info("✅ Live MLX processing started")
            
        except Exception as e:
            logger.error(f"❌ Failed to start live processing: {e}")
            self.live_processor = None
    
    def add_live_audio(self, audio_data) -> None:
        """Add audio data for live processing."""
        if self.live_processor and self.is_live_mode:
            try:
                self.live_processor.add_audio_chunk(audio_data)
            except Exception as e:
                logger.debug(f"Live audio feed error: {e}")
    
    def stop_live_processing(self) -> str:
        """Stop live processing and return final transcript."""
        if not self.is_live_mode or not self.live_processor:
            return ""
            
        logger.info("🛑 Stopping live MLX processing...")
        
        try:
            final_transcript = self.live_processor.stop_processing()
            self.live_processor.cleanup()
            self.live_processor = None
            self.is_live_mode = False
            
            logger.info("✅ Live MLX processing stopped")
            return final_transcript
            
        except Exception as e:
            logger.error(f"❌ Error stopping live processing: {e}")
            return ""
    
    def get_live_transcript(self) -> str:
        """Get current live transcript."""
        if self.live_processor:
            return self.live_processor.get_live_transcript()
        return ""
    
    def get_live_stats(self) -> dict:
        """Get live processing performance stats."""
        if self.live_processor:
            return self.live_processor.get_performance_stats()
        return {}
    
    def cleanup(self) -> None:
        """Clean up live processing resources."""
        if self.is_live_mode:
            self.stop_live_processing()