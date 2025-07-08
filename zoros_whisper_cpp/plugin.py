from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from zoros_core.plugins import ZorosPlugin
from scripts.zoros_cli import app


class WhisperCPPPlugin(ZorosPlugin):
    """Plugin wrapping a local whisper.cpp binary."""

    name = "whisper-cpp"
    version = "0.1.0"

    def register_with_core(self, core_api) -> None:
        core_api.register_transcriber("whisper-cpp", self.transcribe)

        @app.command(name="whisper-cpp-transcribe")
        def transcribe_cmd(path: str) -> None:
            """Transcribe an audio file using whisper.cpp."""
            data = Path(path).read_bytes()
            print(self.transcribe(data))

        core_api.register_plugin(self)

    def transcribe(self, audio_bytes: bytes) -> str:
        """Invoke the local whisper.cpp binary and return transcript."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp.flush()
            cmd = ["whisper.cpp", "-f", tmp.name]
            proc = subprocess.run(cmd, capture_output=True, text=True)
        return proc.stdout.strip()
