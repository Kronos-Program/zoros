import pytest

pytest.importorskip("PySide6.QtWidgets", reason="PySide6 not available")
from PySide6.QtWidgets import QApplication, QMessageBox

from source.interfaces.intake.main import SettingsDialog


def test_run_test(monkeypatch):
    app = QApplication.instance() or QApplication([])
    called = {}
    monkeypatch.setattr(
        "source.dictation_backends.check_backend",
        lambda name: called.setdefault("name", name) or True,
    )
    monkeypatch.setattr(QMessageBox, "exec", lambda self: called.setdefault("msg", True))
    dlg = SettingsDialog({}, ["StandardOpenAIWhisper"], None)
    dlg._run_test()
    assert called["name"] == "StandardOpenAIWhisper"
    assert called.get("msg")
    app.quit()
