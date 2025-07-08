from __future__ import annotations

import json
import logging
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional


class WhisperCLICaller:
    """Wrapper around the ``whisper.cpp`` command line interface."""

    def __init__(self, binary_path: str, model_path: str) -> None:
        self.binary_path = Path(os.path.expanduser(binary_path))
        self.model_path = Path(os.path.expanduser(model_path))
        if not self.binary_path.exists():
            raise FileNotFoundError(f"whisper.cpp binary not found: {self.binary_path}")
        if not self.model_path.exists():
            raise FileNotFoundError(f"model file not found: {self.model_path}")

    def _run(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        """Execute whisper.cpp with the provided arguments."""
        cmd = [str(self.binary_path)] + args
        logging.debug("Running command: %s", shlex.join(cmd))
        return subprocess.run(cmd, capture_output=True, text=True, check=False)

    def transcribe_file(
        self,
        audio_path: str,
        *,
        beam_size: Optional[int] = None,
        language: Optional[str] = None,
        token_timestamps: bool = False,
        backend: Optional[str] = None,
        initial_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Transcribe ``audio_path`` using whisper.cpp.

        Parameters
        ----------
        audio_path:
            Path to the audio file.
        beam_size:
            Beam search width. If ``None`` uses whisper.cpp default.
        language:
            Language hint such as ``en``.
        token_timestamps:
            Include token timestamps in segments.
        backend:
            Hardware backend, e.g. ``metal`` or ``cpu``.
        initial_prompt:
            Optional lexicon or priming prompt.
        """

        args: list[str] = ["-m", str(self.model_path), "-f", audio_path, "--output-format", "json"]
        if beam_size is not None:
            args += ["--beam_size", str(beam_size)]
        if language:
            args += ["--language", language]
        if token_timestamps:
            args.append("--token-timestamps")
        if backend:
            args += ["--backend", backend]
        if initial_prompt:
            args += ["--prompt", initial_prompt]

        proc = self._run(args)
        if proc.returncode != 0:
            logging.warning("whisper.cpp failed with code %s", proc.returncode)
            if backend:
                # retry without backend flag
                filtered = []
                skip_next = False
                for a in args:
                    if skip_next:
                        skip_next = False
                        continue
                    if a == "--backend":
                        skip_next = True
                        continue
                    filtered.append(a)
                proc = self._run(filtered)
                if proc.returncode != 0:
                    raise RuntimeError(proc.stderr)
            else:
                raise RuntimeError(proc.stderr)

        output = proc.stdout.strip()
        data: Dict[str, Any]
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            out_file = Path(audio_path).with_suffix(".json")
            if out_file.exists():
                data = json.loads(out_file.read_text())
                out_file.unlink(missing_ok=True)
            else:
                raise RuntimeError("Failed to parse whisper.cpp output")

        if not token_timestamps:
            for seg in data.get("segments", []):
                seg.pop("tokens", None)

        return {"text": data.get("text", ""), "segments": data.get("segments", [])}
