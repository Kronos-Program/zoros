# See architecture: docs/zoros_architecture.md#component-overview
import os
import sys
from types import SimpleNamespace

import numpy as np
import pytest

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

# Make the parent directory importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from transcription import transcribe_whisper_cpp, transcribe_api
from utils import ConfigManager


class DummyConfig:
    def __init__(self):
        self.sections = {
            'recording_options': {'sample_rate': 16000},
            'model_options': {
                'local': {'model': 'ggml-base.bin'},
                'api': {'model': 'whisper-1', 'base_url': 'https://api.openai.com/v1'},
                'common': {'language': 'en', 'initial_prompt': '', 'temperature': 0}
            }
        }

    def get_section(self, name):
        return self.sections[name]


def _patch_basic_config(monkeypatch, config):
    monkeypatch.setattr(ConfigManager, 'get_config_section', staticmethod(config.get_section))
    monkeypatch.setattr(ConfigManager, 'console_print', lambda *a, **k: None)


def test_transcribe_whisper_cpp(monkeypatch):
    config = DummyConfig()
    _patch_basic_config(monkeypatch, config)

    def fake_run(cmd, capture_output, text, check):
        return SimpleNamespace(stdout='info\nexpected result')

    monkeypatch.setattr('subprocess.run', fake_run)

    audio = np.zeros(16000, dtype=np.int16)
    text = transcribe_whisper_cpp(audio)
    assert text == 'expected result'


def test_transcribe_api(monkeypatch):
    config = DummyConfig()
    _patch_basic_config(monkeypatch, config)

    class DummyClient:
        class audio:
            class transcriptions:
                @staticmethod
                def create(model, file, language, prompt, temperature):
                    return SimpleNamespace(text='api result')

    monkeypatch.setattr('transcription.OpenAI', lambda api_key=None, base_url=None: DummyClient())
    audio = np.zeros(16000, dtype=np.int16)
    text = transcribe_api(audio)
    assert text == 'api result'
class TranscriptionTests(unittest.TestCase):
    def setUp(self):
        self.config = DummyConfig()
        self.patcher_config = patch.object(
            ConfigManager,
            'get_config_section',
            side_effect=self.config.get_section
        )
        self.patcher_console = patch.object(ConfigManager, 'console_print', lambda *a, **k: None)
        self.patcher_config.start()
        self.patcher_console.start()

    def tearDown(self):
        patch.stopall()

    def test_transcribe_whisper_cpp(self):
        with patch('subprocess.run') as fake_run:
            fake_run.return_value = SimpleNamespace(stdout='info\nexpected result')
            audio = np.zeros(16000, dtype=np.int16)
            text = transcribe_whisper_cpp(audio)
            self.assertEqual(text, 'expected result')

    def test_transcribe_api(self):
        class DummyClient:
            class audio:
                class transcriptions:
                    @staticmethod
                    def create(model, file, language, prompt, temperature):
                        return SimpleNamespace(text='api result')

        with patch('transcription.OpenAI', return_value=DummyClient()):
            audio = np.zeros(16000, dtype=np.int16)
            text = transcribe_api(audio)
            self.assertEqual(text, 'api result')


if __name__ == '__main__':
    unittest.main()
