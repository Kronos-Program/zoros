from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import pydantic  # noqa: F401
except ImportError:  # pragma: no cover - fallback for offline venv
    venv_site = ROOT / "coder-env" / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    if venv_site.exists():
        sys.path.insert(0, str(venv_site))
        import pydantic  # noqa: F401

try:
    import sounddevice  # type: ignore
except Exception:  # pragma: no cover - create dummy stub for headless CI
    import types

    sys.modules['sounddevice'] = types.SimpleNamespace()

try:
    import PySide6  # type: ignore
except Exception:  # pragma: no cover - stub PySide6 for headless tests
    import types

    pkg = types.ModuleType('PySide6')
    sys.modules['PySide6'] = pkg
    for sub in ['QtWidgets', 'QtWebEngineWidgets', 'QtGui', 'QtCore']:
        mod = types.ModuleType(f'PySide6.{sub}')
        sys.modules[f'PySide6.{sub}'] = mod
        setattr(pkg, sub, mod)


def pytest_ignore_collect(path, config):
    """Skip integration-style whisper tests that require audio hardware."""
    p = str(path)
    if "src/core/modules/whisper/src/test" in p:
        return True
    if p.endswith("test_unified_ui.py"):
        return True
    return False
