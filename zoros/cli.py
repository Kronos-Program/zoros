"""
Dictation-focused CLI for the export bundle.

Commands:
- intake: launch the PySide6 intake UI (service-first).
- backend-status: report available dictation backends.
- diagnose: quick import check for service components.
"""
from __future__ import annotations

import importlib
import sys
from typing import List

import typer

app = typer.Typer(help="Dictation-only CLI")


def _cprint(text: str, color: str = "") -> None:
    colors = {"red": "31", "green": "32", "yellow": "33", "blue": "34"}
    code = colors.get(color)
    print(f"\033[{code}m{text}\033[0m" if code else text)


@app.command()
def intake(
    legacy: bool = typer.Option(False, help="Launch legacy intake (compat)"),
    headless: bool = typer.Option(False, help="Force headless Qt"),
) -> None:
    """Launch the PySide intake UI."""
    module = "backend.intake.main_legacy" if legacy else "backend.intake.main"
    _cprint(f"Launching intake ({'legacy' if legacy else 'service-first'})...", "blue")
    original_argv = sys.argv[:]
    try:
        intake_main = importlib.import_module(module)
        sys.argv = [original_argv[0]]
        if headless:
            sys.argv.append("--headless")
        intake_main.main()
    except Exception as exc:  # pragma: no cover - UI/runtime
        _cprint(f"Failed to launch intake: {exc}", "red")
        raise typer.Exit(1)
    finally:
        sys.argv = original_argv


@app.command("backend-status")
def backend_status(verbose: bool = typer.Option(False, help="Show backend details")) -> None:
    """List available dictation backends."""
    try:
        from backend.services.dictation.registry import get_backend_registry

        registry = get_backend_registry()
        available = registry.list_available_backends()
        failed = registry.get_failed_backends()
        _cprint("Available backends:", "green")
        if not available:
            _cprint("  (none)", "yellow")
        for name in available:
            info = registry.get_backend_info(name)
            line = f"  - {name}"
            if verbose and info:
                deps = ", ".join(info.dependencies) if info.dependencies else "none"
                line += f" (deps: {deps})"
            _cprint(line, "blue")
        if failed:
            _cprint("Failed backends:", "red")
            for name, reason in failed.items():
                _cprint(f"  - {name}: {reason}", "red")
    except Exception as exc:
        _cprint(f"Backend status failed: {exc}", "red")
        raise typer.Exit(1)


@app.command()
def diagnose() -> None:
    """Quick import check for dictation service components."""
    modules: List[str] = [
        "backend.intake.main",
        "backend.interfaces.intake.controller",
        "backend.interfaces.intake.service_client",
        "backend.interfaces.intake.persistence",
        "backend.services.dictation_service.service",
        "backend.services.dictation.registry",
    ]
    ok = True
    for mod in modules:
        try:
            importlib.import_module(mod)
            _cprint(f"✓ {mod}", "green")
        except Exception as exc:  # pragma: no cover - diagnostics only
            ok = False
            _cprint(f"✗ {mod}: {exc}", "red")
    if not ok:
        raise typer.Exit(1)


def run() -> None:
    app()


if __name__ == "__main__":
    run()
