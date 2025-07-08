from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from .standard_whisper_backend import WhisperBackend


class WhisperCPPBackend(WhisperBackend):
    """Invoke the native `whisper.cpp` binary."""

    def __init__(self, model_name: str) -> None:
        super().__init__(model_name)
        # Look for the whisper-cli binary in the whisper.cpp build directory
        whisper_cpp_dir = Path(__file__).resolve().parents[2] / "whisper.cpp"
        self.binary = whisper_cpp_dir / "build" / "bin" / "whisper-cli"
        
        if not self.binary.exists():
            # Fallback to system PATH
            self.binary = shutil.which("whisper-cli")
            
        if not self.binary:
            raise RuntimeError("whisper.cpp binary not found. Please build whisper.cpp first.")

    def transcribe(self, audio_path: str) -> str:
        print(f"DEBUG: WhisperCPP starting transcription of {audio_path}")
        outdir = Path(tempfile.mkdtemp())
        print(f"DEBUG: Using temp directory: {outdir}")
        
        # Handle model name mapping
        model_path = self._get_model_path()
        print(f"DEBUG: Using model: {model_path}")
        
        # Output file prefix (without extension)
        output_prefix = outdir / Path(audio_path).stem
        print(f"DEBUG: Output prefix: {output_prefix}")
        
        cmd = [
            str(self.binary),
            "-m", str(model_path),
            "-f", audio_path,
            "-of", str(output_prefix),
            "--output-json",
            "--print-confidence",
        ]
        
        print(f"DEBUG: Running command: {' '.join(cmd)}")
        try:
            logging.info(f"Running WhisperCPP CLI: {' '.join(cmd)}")
            print("DEBUG: Starting subprocess...")
            # Add timeout of 60 seconds to prevent hanging
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=60)
            print(f"DEBUG: Subprocess completed with return code: {result.returncode}")
            print(f"DEBUG: stdout length: {len(result.stdout)}")
            print(f"DEBUG: stderr length: {len(result.stderr)}")
            
            # Look for the output JSON file
            result_file = Path(f"{output_prefix}.json")
            print(f"DEBUG: Looking for JSON output file: {result_file}")
            if result_file.exists():
                print(f"DEBUG: Found JSON output file, size: {result_file.stat().st_size} bytes")
                with result_file.open() as fh:
                    data = json.load(fh)
                print(f"DEBUG: JSON data keys: {list(data.keys())}")
                print(f"DEBUG: Full JSON data: {json.dumps(data, indent=2)}")
                
                # Try different possible text fields
                text_result = ""
                if "transcription" in data:
                    text_result = data["transcription"].strip()
                    print(f"DEBUG: Found text in 'transcription' field: {text_result[:100]}...")
                elif "text" in data:
                    text_result = data["text"].strip()
                    print(f"DEBUG: Found text in 'text' field: {text_result[:100]}...")
                elif "result" in data and isinstance(data["result"], dict) and "text" in data["result"]:
                    text_result = data["result"]["text"].strip()
                    print(f"DEBUG: Found text in 'result.text' field: {text_result[:100]}...")
                
                # Print confidence values if present
                if "confidence" in data:
                    logging.info(f"Transcription confidence: {data['confidence']}")
                    print(f"DEBUG: Confidence: {data['confidence']}")
                
                return text_result
            else:
                print(f"DEBUG: JSON output file not found: {result_file}")
            
            # If no JSON file, try to parse the stdout output
            print(f"DEBUG: Trying to parse stdout output...")
            if result.stdout:
                print(f"DEBUG: stdout content: {result.stdout[:200]}...")
                # Extract text from stdout (fallback)
                lines = result.stdout.strip().split('\n')
                print(f"DEBUG: stdout has {len(lines)} lines")
                for line in lines:
                    if '-->' in line and ']' in line:
                        # Extract text after timestamp
                        text_part = line.split(']', 1)[1].strip()
                        if text_part:
                            print(f"DEBUG: Found timestamped text: {text_part}")
                            return text_part
                
                # If no timestamped lines, return the last non-empty line
                for line in reversed(lines):
                    if line.strip():
                        print(f"DEBUG: Using last non-empty line: {line.strip()}")
                        return line.strip()
            else:
                print("DEBUG: No stdout output")
            
            print("DEBUG: No transcription text found")
            return ""
            
        except subprocess.TimeoutExpired as err:
            logging.error("WhisperCPP CLI timed out after 60 seconds: %s", err)
            print(f"DEBUG: WhisperCPP CLI timed out: {err}")
            raise
        except subprocess.CalledProcessError as err:
            logging.error("WhisperCPP CLI failed: %s", err)
            logging.error("stdout: %s", err.stdout)
            logging.error("stderr: %s", err.stderr)
            print(f"DEBUG: WhisperCPP CLI failed with return code {err.returncode}")
            print(f"DEBUG: stdout: {err.stdout}")
            print(f"DEBUG: stderr: {err.stderr}")
            raise
        except Exception as err:
            logging.error("WhisperCPP failed: %s", err)
            print(f"DEBUG: WhisperCPP failed with exception: {err}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            try:
                for f in outdir.iterdir():
                    f.unlink(missing_ok=True)
                outdir.rmdir()
            except Exception:
                pass

    def _get_model_path(self) -> Path:
        """Get the path to the model file."""
        whisper_cpp_dir = Path(__file__).resolve().parents[2] / "whisper.cpp"
        
        # Map model names to file paths
        model_mapping = {
            "tiny": "models/ggml-tiny.bin",
            "tiny.en": "models/ggml-tiny.en.bin",
            "base": "models/ggml-base.bin",
            "base.en": "models/ggml-base.en.bin",
            "small": "models/ggml-small.bin",
            "small.en": "models/ggml-small.en.bin",
            "medium": "models/ggml-medium.bin",
            "medium.en": "models/ggml-medium.en.bin",
            "large": "models/ggml-large.bin",
            "large-v1": "models/ggml-large-v1.bin",
            "large-v2": "models/ggml-large-v2.bin",
            "large-v3": "models/ggml-large-v3.bin",
            "large-v3-turbo": "models/ggml-large-v3-turbo.bin",
        }
        
        if self.model_name in model_mapping:
            model_path = whisper_cpp_dir / model_mapping[self.model_name]
            if model_path.exists():
                return model_path
            else:
                logging.warning(f"Model file not found: {model_path}")
        
        # If not found in mapping or file doesn't exist, assume it's a direct path
        return Path(self.model_name)
