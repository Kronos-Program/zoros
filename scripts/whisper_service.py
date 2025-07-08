#!/usr/bin/env python3
"""
Standalone Whisper transcription service for Docker deployment.
"""

import os
import sys
import tempfile
from typing import Optional
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ZorOS Whisper Service", version="1.0.0")

# Global Whisper model
whisper_model = None


def initialize_whisper():
    """Initialize Whisper model based on environment configuration."""
    global whisper_model
    
    model_size = os.getenv("MODEL_SIZE", "base")
    device = os.getenv("DEVICE", "cpu")
    
    try:
        # Try faster-whisper first
        from faster_whisper import WhisperModel
        
        logger.info(f"Initializing faster-whisper model: {model_size} on {device}")
        whisper_model = WhisperModel(
            model_size,
            device=device,
            compute_type="int8" if device == "cpu" else "float16",
            download_root=os.getenv("CACHE_DIR", "/app/models")
        )
        logger.info("Faster-whisper model initialized successfully")
        return "faster-whisper"
        
    except Exception as e:
        logger.warning(f"Failed to initialize faster-whisper: {e}")
        
        try:
            # Fallback to openai-whisper
            import whisper
            
            logger.info(f"Initializing openai-whisper model: {model_size}")
            whisper_model = whisper.load_model(
                model_size,
                download_root=os.getenv("CACHE_DIR", "/app/models")
            )
            logger.info("OpenAI Whisper model initialized successfully")
            return "openai-whisper"
            
        except Exception as e:
            logger.error(f"Failed to initialize any Whisper model: {e}")
            raise


@app.on_event("startup")
async def startup_event():
    """Initialize Whisper model on startup."""
    global whisper_backend_type
    whisper_backend_type = initialize_whisper()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    if whisper_model is None:
        raise HTTPException(status_code=503, detail="Whisper model not initialized")
    
    return {
        "status": "healthy",
        "backend": whisper_backend_type,
        "model_size": os.getenv("MODEL_SIZE", "base"),
        "device": os.getenv("DEVICE", "cpu")
    }


@app.post("/transcribe")
async def transcribe_audio(
    audio_file: UploadFile = File(...),
    language: Optional[str] = None,
    task: str = "transcribe"
):
    """Transcribe audio file."""
    if whisper_model is None:
        raise HTTPException(status_code=503, detail="Whisper model not initialized")
    
    try:
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
            content = await audio_file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        # Transcribe based on backend type
        if whisper_backend_type == "faster-whisper":
            segments, info = whisper_model.transcribe(
                temp_file_path,
                language=language,
                task=task
            )
            
            # Extract text from segments
            text = " ".join([segment.text for segment in segments])
            
            result = {
                "text": text.strip(),
                "language": info.language,
                "language_probability": info.language_probability,
                "backend": "faster-whisper"
            }
            
        else:  # openai-whisper
            result_data = whisper_model.transcribe(
                temp_file_path,
                language=language,
                task=task
            )
            
            result = {
                "text": result_data["text"].strip(),
                "language": result_data["language"],
                "backend": "openai-whisper"
            }
        
        # Clean up temporary file
        os.unlink(temp_file_path)
        
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        # Clean up temp file if it exists
        try:
            os.unlink(temp_file_path)
        except:
            pass
        
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


@app.get("/models")
async def list_models():
    """List available Whisper models."""
    available_models = ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]
    current_model = os.getenv("MODEL_SIZE", "base")
    
    return {
        "available_models": available_models,
        "current_model": current_model,
        "backend": whisper_backend_type
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8001))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )