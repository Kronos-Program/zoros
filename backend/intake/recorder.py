"""
Lightweight audio recorder used by the service-first intake UI.
"""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Optional

import numpy as np

try:  # optional sounddevice
    import sounddevice as sd
except Exception:  # pragma: no cover - optional dependency
    sd = None  # type: ignore


class Recorder:
    """Simple microphone recorder accumulating frames."""

    def __init__(self, sample_rate: int = 16000) -> None:
        self.sample_rate = sample_rate
        self.stream: Optional[sd.InputStream] = None if sd else None  # type: ignore[attr-defined]
        self.frames: list[np.ndarray] = []
        self.level: float = 0.0
        self.device: Optional[int] = None
        self.recording_start_time: Optional[float] = None

    def _callback(self, indata, _frames, _time, _status) -> None:  # pragma: no cover - passthrough
        self.frames.append(indata.copy())
        self.level = float(np.abs(indata).mean())

    def start(self, device: Optional[int] = None) -> None:
        if sd is None:
            raise RuntimeError("sounddevice is not available")
        self.frames = []
        self.level = 0.0
        self.recording_start_time = perf_counter()
        self.device = device
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            callback=self._callback,
            device=self.device,
        )
        self.stream.start()

    def stop(self, path: Path, keep_stream: bool = False) -> None:
        if not self.stream:
            return
        self.stream.stop()
        self.stream.close()
        self.stream = None
        import soundfile as sf  # local import to avoid hard dependency at module import

        # Ensure we always write a file, even if no frames captured
        if self.frames:
            audio = np.concatenate(self.frames)
        else:
            audio = np.zeros(int(self.sample_rate * 0.25), dtype=np.float32)
        sf.write(str(path), audio, self.sample_rate)
        print(f"[recorder] wrote audio to {path} (frames={len(self.frames)})")
        if keep_stream and sd is not None:
            # restart stream if requested
            self.start(self.device)
