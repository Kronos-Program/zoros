from __future__ import annotations

import subprocess
import sys
import types

from pathlib import Path
import importlib
import importlib.metadata
from importlib.metadata import EntryPoint

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ensure local site-packages are available for FastAPI

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover - fallback for offline env
    venv_site = ROOT / "coder-env" / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    if venv_site.exists():
        sys.path.insert(0, str(venv_site))
    from fastapi.testclient import TestClient

# patch entry points before importing the core
orig_eps = importlib.metadata.entry_points

def _fake_entry_points(*args, **kwargs):
    group = kwargs.get("group") if kwargs else args[0] if args else None
    if group == "zoros.plugins":
        return [
            EntryPoint("whisper_cpp", "zoros_whisper_cpp:WhisperCPPPlugin", "zoros.plugins"),
            EntryPoint("lang_service", "zoros_lang_service:LangServicePlugin", "zoros.plugins"),
        ]
    return orig_eps(*args, **kwargs)

importlib.metadata.entry_points = _fake_entry_points

# Ensure a clean import of the core module with patched entry points
for mod in list(sys.modules):
    if mod.startswith("zoros_core"):
        del sys.modules[mod]

sys.modules.setdefault("sounddevice", types.ModuleType("sounddevice"))
sys.modules.setdefault("soundfile", types.ModuleType("soundfile"))
sys.modules.setdefault("numpy", types.ModuleType("numpy"))

from backend.app import app
from zoros_core import core_api

client = TestClient(app)


def test_plugins_loaded(monkeypatch):
    # stub whisper.cpp call
    def fake_run(cmd, capture_output=True, text=True):
        return subprocess.CompletedProcess(cmd, 0, stdout="hi", stderr="")

    monkeypatch.setattr("zoros_whisper_cpp.plugin.subprocess.run", fake_run)
    monkeypatch.setattr(
        "source.language_service.LanguageService.complete_chat",
        lambda self, msgs, **kw: "pong",
    )

    names = core_api.list_plugins()
    assert "whisper-cpp" in names
    assert "lang-service" in names

    out = core_api.transcribe_with("whisper-cpp", b"audio")
    assert out

    proc = subprocess.run(
        [sys.executable, "scripts/zoros_cli.py", "lang-service-test"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0


def test_api_plugins():
    resp = client.get("/api/plugins")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "whisper-cpp" in names
    assert "lang-service" in names
