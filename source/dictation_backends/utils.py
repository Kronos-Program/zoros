from __future__ import annotations

import importlib
import importlib.util
import shutil
import sys
from pathlib import Path
from typing import List


def is_macos() -> bool:
    """Return True if running on macOS."""
    return sys.platform == "darwin"


def _has_module(name: str) -> bool:
    spec = importlib.util.find_spec(name)
    return spec is not None


def get_available_backends() -> List[str]:
    """Detect available whisper backends for the current platform."""
    available: List[str] = []
    if is_macos():
        # Check for whisper.cpp CLI
        whisper_cpp_dir = Path(__file__).resolve().parents[2] / "whisper.cpp"
        whisper_cli = whisper_cpp_dir / "build" / "bin" / "whisper-cli"
        if whisper_cli.exists() or shutil.which("whisper-cli"):
            available.append("WhisperCPP")
        elif _has_module("whispercpp"):
            # Fallback to Python bindings if CLI not available
            available.append("WhisperCPP")
        if _has_module("mlx_whisper"):
            available.append("MLXWhisper")
            available.append("LiveMLXWhisper")  # Experimental live transcription
            # Add streaming backends if MLX Whisper is available
            available.append("ParallelMLXWhisper")
            available.append("QueueBasedStreamingMLXWhisper")
            available.append("RealtimeStreamingMLXWhisper")
        if _has_module("faster_whisper"):
            try:
                import torch  # noqa: WPS433

                if torch.backends.mps.is_available():
                    available.append("FasterWhisper")
            except Exception:
                pass
    if _has_module("whisper"):
        available.append("StandardOpenAIWhisper")
    if _has_module("openai"):
        import os

        if os.getenv("OPENAI_API_KEY"):
            available.append("OpenAIAPI")
    if os.getenv("ZOROS_MOCK_TRANSCRIPTION"):
        available.append("Mock")
    return available


def check_backend(name: str) -> bool:
    """Return True if the backend can be initialized."""
    try:
        if name == "WhisperCPP":
            # Check for whisper.cpp CLI first
            whisper_cpp_dir = Path(__file__).resolve().parents[2] / "whisper.cpp"
            whisper_cli = whisper_cpp_dir / "build" / "bin" / "whisper-cli"
            if whisper_cli.exists() or shutil.which("whisper-cli"):
                # Test CLI by running a simple command
                import subprocess
                try:
                    result = subprocess.run([str(whisper_cli), "--help"], 
                                          capture_output=True, text=True, timeout=5)
                    return result.returncode == 0
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                    pass
            
            # Fallback to Python bindings
            from whispercpp import Whisper  # type: ignore
            w = Whisper.from_pretrained("tiny")
            return True
        if name == "FasterWhisper":
            from faster_whisper import WhisperModel  # type: ignore

            WhisperModel("tiny", device="cpu")
            return True
        if name == "MLXWhisper":
            try:
                import mlx_whisper
                # Try a dry-run with a short dummy file path (should fail gracefully if installed)
                # We don't actually run a transcription, just check import
                return True
            except Exception:
                return False
        if name == "LiveMLXWhisper":
            try:
                import mlx_whisper
                # Check if MLX Whisper is available (LiveMLXWhisper depends on it)
                return True
            except Exception:
                return False
        if name == "ParallelMLXWhisper":
            try:
                import mlx_whisper
                # Check if MLX Whisper is available (parallel depends on it)
                return True
            except Exception:
                return False
        if name == "QueueBasedStreamingMLXWhisper":
            try:
                import mlx_whisper
                # Check if MLX Whisper is available (queue-based depends on it)
                return True
            except Exception:
                return False
        if name == "RealtimeStreamingMLXWhisper":
            try:
                import mlx_whisper
                # Check if MLX Whisper is available (streaming depends on it)
                return True
            except Exception:
                return False
        if name == "StandardOpenAIWhisper":
            import whisper  # type: ignore

            whisper.load_model("tiny")
            return True
        if name == "OpenAIAPI":
            import openai  # type: ignore
            import os

            return bool(os.getenv("OPENAI_API_KEY"))
        if name == "Mock":
            return True
    except Exception:
        return False
    return False
