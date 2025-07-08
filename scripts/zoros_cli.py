# See architecture: docs/zoros_architecture.md#component-overview
"""Zoros CLI implemented with a tiny Typer wrapper."""

import os
import sys
import json
import platform
import shutil
import subprocess
from pathlib import Path

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import typer
from source.language_service import LanguageService

try:
    from ui import intake_review
except Exception:  # pragma: no cover - optional
    intake_review = None  # type: ignore

app = typer.Typer()

# Configuration file used by the main CLI
CONFIG_FILE = Path.home() / ".zoros" / "config.toml"


@app.command()
def speak() -> None:
    """Run demo chat and turn."""
    svc = LanguageService()
    try:
        resp = svc.complete_chat([{"role": "user", "content": "Say hello"}])
        print("Chat:", resp)
        turn = svc.complete_turn("example", {"prompt": "Demo"})
        print("Turn:", turn)
    except Exception as exc:  # pragma: no cover - network may fail
        print("Error:", exc)


@app.command(name="echo-test")
def echo_test(text: str = typer.Option(..., help="Text to echo")) -> None:
    """Simple echo command used in tests."""
    print(text)


@app.command(name="review-intake")
def review_intake() -> None:
    """Launch the PySide intake review UI."""
    if intake_review is None:
        typer.echo("Intake review UI not available")
        raise typer.Exit(1)
    intake_review.main()


@app.command()
def intake(
    unified: bool = typer.Option(False, "--unified-ui", help="Embed React UI inside PySide window"),
    light: bool = typer.Option(False, "--light-theme", help="Use light theme instead of dark")
) -> None:
    """Launch the ZorOS intake dictation interface."""
    try:
        # Import and launch the intake UI
        from source.interfaces.intake.main import main as intake_main
        import sys
        
        # Set up sys.argv for the intake main function
        original_argv = sys.argv[:]
        sys.argv = ["intake"]
        
        if unified:
            sys.argv.append("--unified-ui")
        if light:
            sys.argv.append("--light-theme")
        
        try:
            intake_main()
        finally:
            # Restore original argv
            sys.argv = original_argv
            
    except Exception as e:
        typer.echo(f"Error launching intake UI: {e}")
        raise typer.Exit(1)


@app.command(name="lint-fiber")
def lint_fiber_cmd(
    path: str,
    fix: bool = typer.Option(False, help="Auto repair missing fields"),
) -> None:
    """Lint a fiber and optionally apply fixes."""
    from zoros.utils.lint_fiber import lint_fiber

    fiber_path = Path(path)
    if not fiber_path.exists():
        typer.echo("File not found")
        raise typer.Exit(1)

    ok, messages = lint_fiber(fiber_path, fix=fix)
    for msg in messages:
        typer.echo(msg)
    if not ok:
        raise typer.Exit(1)


def _suggest_install(tool: str) -> None:
    """Print an install suggestion for the given tool."""
    os_name = platform.system()
    if os_name == "Darwin":
        cmd = f"brew install {tool}"
    elif os_name == "Windows":
        cmd = f"choco install {tool}"
    else:
        cmd = f"sudo apt-get install {tool}"
    typer.echo(f"Run '{cmd}' to install {tool}")


def _check_tool(names: list[str], desc: str) -> str | None:
    """Return path for the first found tool or prompt the user."""
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    typer.echo(f"{desc} not found.")
    _suggest_install(names[0])
    path = input(f"Enter path to {desc} or press Enter to skip: ").strip()
    if path and Path(path).exists():
        return path
    return None


@app.command()
def wizard() -> None:
    """Run the interactive setup wizard."""
    print("=== Zoros Setup Wizard ===")

    conda = shutil.which("conda")
    if conda:
        ans = input(f"Found Miniconda at {conda}. Use this? [Y/n] ").strip().lower()
        if ans.startswith("n"):
            conda = None
    while not conda:
        path = input("Enter path to Miniconda (or 'cancel'): ").strip()
        if not path or path.lower().startswith("cancel"):
            print("Setup cancelled.")
            raise typer.Exit(1)
        if shutil.which(path) or Path(path).exists():
            conda = path
        else:
            print("Invalid path. Try again.")

    os_name = platform.system()
    machine = platform.machine()
    gpu = "yes" if shutil.which("nvidia-smi") else "no"
    print(f"Detected OS: {os_name}, Hardware: {machine}, GPU Available: {gpu}")

    env_name = "zoros"
    try:
        proc = subprocess.run([conda, "env", "list", "--json"], capture_output=True, text=True, check=True)
        envs = {Path(p).name for p in json.loads(proc.stdout).get("envs", [])}
    except Exception:
        envs = set()

    if env_name not in envs:
        ans = input("No 'zoros' environment found. Create it? [Y/n] ").strip().lower()
        if ans.startswith("y") or ans == "":
            try:
                subprocess.run([conda, "create", "-y", "-n", env_name, "python=3.11"], check=True)
            except Exception as exc:
                print("Failed to create environment:", exc)
    else:
        ans = input(f"Use existing environment '{env_name}'? [Y/n] ").strip().lower()
        if ans.startswith("n"):
            env_name = input("Enter environment name to use: ").strip() or env_name

    CONFIG_FILE.parent.mkdir(exist_ok=True)
    cfg = (
        f'conda_path = "{conda}"\n'
        f'env_name = "{env_name}"\n'
        f'os = "{os_name}"\n'
        f'hardware = "{machine}"\n'
        f'gpu = "{gpu}"\n'
    )
    CONFIG_FILE.write_text(cfg)
    print(f"Configuration saved to {CONFIG_FILE}")

    # --- Whisper.cpp prerequisites ---
    print("Checking tools required for whisper.cpp (git, make, C compiler)")
    git_path = _check_tool(["git"], "git")
    make_path = _check_tool(["make"], "make")
    compiler_path = _check_tool(["gcc", "clang"], "C compiler")
    missing = [
        name
        for name, path in {
            "git": git_path,
            "make": make_path,
            "compiler": compiler_path,
        }.items()
        if path is None
    ]
    if missing:
        typer.echo(
            "Missing tools may prevent building whisper.cpp: " + ", ".join(missing)
        )
    else:
        typer.echo("All required tools found for whisper.cpp")

    print("Setup complete. You can rerun this wizard anytime.")


@app.command(name="import-flow")
def import_flow(
    file: str = typer.Option(..., help="Path to flow YAML/JSON"),
    py: bool = typer.Option(False, help="Also create Python stub"),
) -> None:
    """Import an external flow file as a routine."""
    from source.routines import import_flow as _import

    out = _import(Path(file), py=py)
    typer.echo(f"Routine saved to {out}")


def get_cli_schema() -> list[dict]:
    """Return a JSON serialisable schema of registered CLI commands."""
    schema: list[dict] = []
    for name, cmd in app.registered_commands.items():
        params = []
        for param in cmd.params:
            p_type = getattr(param.type, "name", str(param.type))
            params.append(
                {
                    "name": param.name,
                    "type": p_type,
                    "required": param.required,
                    "default": None if param.default is None else param.default,
                    "help": getattr(param, "help", "") or "",
                }
            )
        schema.append({"command": name, "params": params})
    return schema


def main() -> None:  # pragma: no cover - CLI entry
    app()


if __name__ == "__main__":
    main()
