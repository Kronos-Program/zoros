import os
import sys
import webbrowser
from unittest import mock

import zoros.cli as cli


def test_no_display_falls_back_to_tui(monkeypatch, capsys):
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.setattr(cli, "start_engine", lambda cfg: None)
    opened = {"called": False}
    monkeypatch.setattr(webbrowser, "open", lambda url: opened.update(called=True))

    def fake_tui(engine):
        print("TUI")
        return 0

    monkeypatch.setattr(cli, "tui_loop", fake_tui)
    cli.main([])
    out = capsys.readouterr().out
    assert "TUI" in out
    assert not opened["called"]


def test_gui_launches_intake(monkeypatch):
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setattr(cli, "start_engine", lambda cfg: None)
    called = {"ui": False, "browser": False}

    fake_mod = type("M", (), {"main": lambda: called.__setitem__("ui", True)})
    monkeypatch.setitem(sys.modules, "source.interfaces.intake.main", fake_mod)

    monkeypatch.setattr(webbrowser, "open", lambda url: called.__setitem__("browser", True))
    monkeypatch.setattr(cli, "tui_loop", lambda engine: 0)

    cli.main([])
    assert called["ui"]
    assert not called["browser"]
