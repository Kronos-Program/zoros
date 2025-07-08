from zoros import cli


def test_menu_shows_options(monkeypatch, capsys):
    """Menu should list available layers."""
    monkeypatch.setattr('builtins.input', lambda prompt: '')
    cli.menu()
    out = capsys.readouterr().out
    assert "Intake (PySide)" in out

