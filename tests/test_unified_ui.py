import unittest
import sys
import types
import pytest
from unittest.mock import patch, Mock

import pytest

pytest.importorskip("PySide6.QtWidgets", reason="PySide6 not available")
pytest.importorskip("sounddevice", reason="sounddevice not available")
# Skip if PySide6 is unavailable (e.g. headless CI)
pytest.importorskip("PySide6.QtWebEngineWidgets", reason="PySide6 not available")

# Provide stub modules for optional audio deps so import succeeds
sys.modules.setdefault("sounddevice", types.ModuleType("sounddevice"))
sys.modules.setdefault("soundfile", types.ModuleType("soundfile"))
numpy_mock = types.ModuleType("numpy")
numpy_mock.ndarray = type('ndarray', (), {})
sys.modules.setdefault("numpy", numpy_mock)
pytest.importorskip("PySide6.QtWidgets", reason="PySide6 not available")

from backend.interfaces.intake.main import IntakeWindow

class TestUnifiedUI(unittest.TestCase):
    @patch('PySide6.QtWebEngineWidgets.QWebEngineView')
    @patch('backend.interfaces.intake.main.requests.get')
    def test_unified_ui_initializes(self, mock_get, mock_view):
        mock_get.return_value.status_code = 200
        window = IntakeWindow(unified=True)
        self.assertTrue(hasattr(window, 'webview'))
        mock_view.assert_called()
        mock_get.assert_called_once()

if __name__ == '__main__':
    unittest.main()
