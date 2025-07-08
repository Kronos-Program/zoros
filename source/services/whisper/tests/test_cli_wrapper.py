from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from source.services.whisper.cli_wrapper import WhisperCLICaller


class DummyCompleted(subprocess.CompletedProcess[str]):
    def __init__(self, cmd: list[str], stdout: str, returncode: int = 0) -> None:
        super().__init__(cmd, returncode, stdout=stdout, stderr="")


def test_transcribe_returns_dict(monkeypatch, tmp_path: Path) -> None:
    output = {"text": "hi", "segments": [{"start": 0, "end": 1, "text": "hi", "tokens": [1]}]}

    def fake_run(cmd, capture_output=True, text=True, check=False):
        return DummyCompleted(cmd, json.dumps(output))

    monkeypatch.setattr(subprocess, "run", fake_run)

    audio = tmp_path / "a.wav"
    audio.write_text("data")

    binary = tmp_path / "whisper"
    binary.write_text("")
    model = tmp_path / "model.bin"
    model.write_text("m")

    caller = WhisperCLICaller(binary_path=str(binary), model_path=str(model))
    result = caller.transcribe_file(str(audio), beam_size=2, language="en", token_timestamps=True)
    assert result["text"] == "hi"
    assert result["segments"]


def test_prompt_flag_included(monkeypatch, tmp_path: Path) -> None:
    called = {}

    def fake_run(cmd, capture_output=True, text=True, check=False):
        called["cmd"] = cmd
        return DummyCompleted(cmd, "{}")

    monkeypatch.setattr(subprocess, "run", fake_run)

    audio = tmp_path / "a.wav"
    audio.write_text("data")

    binary = tmp_path / "whisper"
    binary.write_text("")
    model = tmp_path / "model.bin"
    model.write_text("m")
    caller = WhisperCLICaller(binary_path=str(binary), model_path=str(model))
    caller.transcribe_file(str(audio), initial_prompt="hello")
    assert "--prompt" in called["cmd"]
