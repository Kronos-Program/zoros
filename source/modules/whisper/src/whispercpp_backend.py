# See architecture: docs/zoros_architecture.md#component-overview
import subprocess
import json
from pathlib import Path
from typing import Optional, Union, Dict, Any, List

class WhisperCppWrapper:
    """
    A Python wrapper for the whisper.cpp CLI, exposing key parameters for transcription.
    """

    def __init__(
        self,
        binary_path: Union[str, Path] = "./main",
        model_path: Union[str, Path] = "models/ggml-small.bin"
    ):
        self.binary = Path(binary_path)
        self.model = Path(model_path)
        if not self.binary.exists():
            raise FileNotFoundError(f"Whisper.cpp binary not found at {self.binary}")
        if not self.model.exists():
            raise FileNotFoundError(f"Model file not found at {self.model}")

    def transcribe(
        self,
        audio_source: Union[str, Path],
        beam_size: int = 5,
        language: Optional[str] = None,
        token_timestamps: bool = True,
        output_format: str = "json",
        extra_args: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Transcribe an audio file using whisper.cpp CLI.

        Parameters:
            audio_source: Path to audio file or "mic" (if CLI built with mic support)
            beam_size: Beam search width (higher = more accurate, slower)
            language: Force transcription in given ISO code, e.g. "en", "es"
            token_timestamps: Include token-level timestamps in the results
            output_format: CLI output format: "json", "srt", "txt", etc.
            extra_args: Any additional CLI flags (e.g., ["--threads", "4"]) 

        Returns:
            A dictionary parsed from JSON output when output_format="json";
            otherwise returns {'raw': output_text}.
        """
        audio = Path(audio_source)
        if not audio.exists() and audio_source != "mic":
            raise FileNotFoundError(f"Audio source not found: {audio_source}")

        cmd = [str(self.binary), "-m", str(self.model)]
        if audio_source == "mic":
            cmd += ["-r"]  # record mode; requires SDL2 build
        else:
            cmd += ["-f", str(audio)]

        cmd += ["--beam_size", str(beam_size)]
        cmd += ["--output-format", output_format]

        if language:
            cmd += ["--language", language]
        if extra_args:
            cmd += extra_args

        # whisper.cpp always prints JSON with timestamps and tokens if format=json
        result = subprocess.run(
            cmd,
            capture_output=True,
            check=True
        )

        text = result.stdout.decode('utf-8')
        if output_format == "json":
            data = json.loads(text)
            if not token_timestamps:
                # drop token-level info
                for seg in data.get('segments', []):
                    seg.pop('tokens', None)
            return data
        else:
            return {"raw": text}


if __name__ == "__main__":
    # Example usage:
    wrapper = WhisperCppWrapper(
        binary_path="./main",
        model_path="models/ggml-small.bin"
    )

    # Transcribe a file with custom settings
    result = wrapper.transcribe(
        audio_source="test_audio.wav",
        beam_size=8,
        language="en",
        token_timestamps=False,
        output_format="json"
    )
    print(json.dumps(result, indent=2))
