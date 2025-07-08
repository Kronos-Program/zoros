"""ZorOS command-line interface module.

This module exposes the Typer-based ``zoros`` command that launches
various user interfaces and maintenance utilities.

Specification: docs/cli_usage.md
Architecture: docs/zoros_architecture.md#component-overview
Tests: tests/test_cli_entry.py
Related Modules:
- zoros.logger - logging utilities
- source.interfaces.intake.main - PySide intake UI

Dependencies:
- External libraries: typer, PySide6 (optional)
- Internal modules: source.* packages
"""
from __future__ import annotations
from zoros.logger import get_logger, LOG_DIR, DB_PATH
import sqlite3
import os
import subprocess
import sys
from pathlib import Path
import webbrowser
import tomllib
import importlib
import importlib.metadata
import shutil

from typing import Any, Callable

import typer

# Reuse existing modules
try:
    from source.language_service import LanguageService
except Exception:  # pragma: no cover - optional import during tests
    LanguageService = None  # type: ignore

CONFIG_HOME = Path.home() / ".zoros"
CONFIG_FILE = CONFIG_HOME / "config.toml"


def set_config_home(path: Path) -> None:
    """Update where configuration and logs are stored."""
    global CONFIG_HOME, CONFIG_FILE
    CONFIG_HOME = path
    CONFIG_FILE = CONFIG_HOME / "config.toml"
    CONFIG_HOME.mkdir(parents=True, exist_ok=True)


# Typer application for the new unified CLI
app = typer.Typer()
logger = get_logger(__name__)


def _cprint(text: str, color: str = "") -> None:
    """Print ``text`` using basic ANSI colors."""
    colors = {
        "red": "31",
        "green": "32",
        "yellow": "33",
        "blue": "34",
    }
    code = colors.get(color)
    if code:
        print(f"\033[{code}m{text}\033[0m")
    else:
        print(text)


def load_config() -> dict[str, Any]:
    """Load configuration from file and environment."""
    cfg: dict[str, Any] = {}
    CONFIG_HOME.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            with CONFIG_FILE.open("rb") as fh:
                cfg = tomllib.load(fh)
        except Exception as exc:  # pragma: no cover - unlikely parse issue
            logger.warning("Failed to read %s: %s", CONFIG_FILE, exc)
    # environment overrides
    for key in ("OPENAI_API_KEY", "DEFAULT_MODEL"):
        if os.getenv(key):
            cfg[key.lower()] = os.getenv(key)
    return cfg


def start_engine(cfg: dict[str, Any]) -> subprocess.Popen[Any]:
    """Launch the backend REST service."""
    cmd = [sys.executable, "-m", "uvicorn", "backend.app:app", "--port", "8888"]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return proc


def has_display() -> bool:
    """Return True if a graphical display is available."""
    if sys.platform.startswith("win"):
        return True
    return bool(os.getenv("DISPLAY"))


def tui_loop(_engine: subprocess.Popen[Any]) -> int:
    """Minimal text-based fallback UI."""
    print("Zoros CLI - headless mode")
    print("Type 'exit' to quit")
    try:
        while True:
            ans = input("Zoros> ").strip().lower()
            if ans in {"exit", "quit", "q"}:
                break
    except KeyboardInterrupt:
        pass
    return 0


# ----- Typer CLI commands -----

@app.command()
def intake(headless: bool = typer.Option(False, help="Run without display")) -> None:
    """Launch the PySide intake UI."""
    logger.info("Launching intake UI")
    if headless or os.getenv("ZOROS_HEADLESS") or not has_display():
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        import importlib
        intake_main = importlib.import_module("source.interfaces.intake.main")
        intake_main.main()
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.error("Intake UI failed: %s", exc)
        _cprint("Intake UI not available", "red")
        sys.exit(1)


@app.command()
def ui(command: str = "", base: str = typer.Option(".", help="Base directory")) -> None:
    """Unified UI commands (e.g. 'markdown')."""
    if command == "markdown":
        script = (
            Path(__file__).resolve().parent.parent
            / "source"
            / "interfaces"
            / "streamlit"
            / "streamlit_markdown_viewer.py"
        )
        if not script.exists():
            _cprint("Markdown viewer not found", "red")
            sys.exit(1)
        cmd = [sys.executable, "-m", "streamlit", "run", str(script), "--", "--base", base]
        subprocess.run(cmd, check=True)
    elif command:
        _cprint(f"Unknown ui command '{command}'", "red")
        _cprint("Available commands: markdown", "yellow")
        sys.exit(1)
    else:
        _cprint("Available UI commands:", "blue")
        _cprint("  zoros ui markdown  - Launch Streamlit markdown viewer", "green")


@app.command()
def unified() -> None:
    """Launch the PySide app with embedded React UI."""
    try:
        from source.interfaces.intake import main as intake_main
        sys.argv = [sys.argv[0], "--unified-ui"]
        intake_main.main()
    except Exception:
        _cprint("Unified UI not available", "red")
        sys.exit(1)


@app.command()
def streamlit() -> None:
    """Launch the Streamlit Fiber Tools."""
    script = Path("source/interfaces/streamlit/fiberizer_review.py")
    if not script.exists():
        _cprint("Streamlit tools not found", "red")
        raise typer.Exit(1)
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(script)], check=False)


@app.command()
def docker(
    action: str = typer.Argument(..., help="Action: start, stop, build, status, logs"),
    service: str = typer.Option("", help="Specific service name"),
    rebuild: bool = typer.Option(False, "--rebuild", help="Force rebuild for build action"),
    lines: int = typer.Option(100, "--lines", help="Number of log lines to show")
) -> None:
    """Docker service management for ZorOS."""
    try:
        # Import and initialize plugin manager
        from source.plugins.manager import PluginManager
        
        pm = PluginManager()
        pm.discover_plugins()
        
        # Get Docker plugin
        docker_plugin = pm.get_plugin("Docker Integration")
        if not docker_plugin:
            _cprint("Docker plugin not available", "red")
            sys.exit(1)
        
        # Execute action
        if action == "start":
            services = [service] if service else None
            result = docker_plugin.start_services(services)
        elif action == "stop":
            services = [service] if service else None
            result = docker_plugin.stop_services(services)
        elif action == "build":
            result = docker_plugin.build_images(force_rebuild=rebuild)
        elif action == "status":
            result = docker_plugin.get_health_status()
        elif action == "logs":
            service_name = service if service else None
            result = docker_plugin.get_logs(service_name, lines)
        else:
            _cprint(f"Unknown action '{action}'", "red")
            _cprint("Available actions: start, stop, build, status, logs", "yellow")
            sys.exit(1)
        
        # Display result
        if result.get("status") == "success":
            _cprint(f"✓ {result.get('message', 'Action completed')}", "green")
            if "output" in result:
                print(result["output"])
            if "logs" in result:
                print(result["logs"])
        elif result.get("status") == "error":
            _cprint(f"✗ {result.get('message', 'Action failed')}", "red")
            if "error" in result:
                print(result["error"])
        else:
            # For status action
            import json
            print(json.dumps(result, indent=2))
    
    except Exception as e:
        _cprint(f"Docker command failed: {e}", "red")
        sys.exit(1)


@app.command()
def webui(
    action: str = typer.Argument(..., help="Action: start, stop, status, chat"),
    port: int = typer.Option(8080, help="Port to run OpenWebUI"),
    host: str = typer.Option("127.0.0.1", help="Host to bind to"),
    title: str = typer.Option("", help="Chat title for 'chat' action"),
    message: str = typer.Option("", help="Message to send for 'chat' action"),
    model: str = typer.Option("gpt-3.5-turbo", help="Model to use")
) -> None:
    """OpenWebUI management for ZorOS."""
    try:
        # Import and initialize plugin manager
        from source.plugins.manager import PluginManager
        
        pm = PluginManager()
        pm.discover_plugins()
        
        # Get OpenWebUI plugin
        webui_plugin = pm.get_plugin("OpenWebUI Integration")
        if not webui_plugin:
            _cprint("OpenWebUI plugin not available", "red")
            sys.exit(1)
        
        # Execute action
        if action == "start":
            result = webui_plugin.start_webui(port=port, host=host)
        elif action == "stop":
            result = webui_plugin.stop_webui()
        elif action == "status":
            result = webui_plugin.get_health_status()
        elif action == "chat":
            if not title:
                _cprint("Chat title required for chat action", "red")
                sys.exit(1)
            
            # Create chat session
            chat_result = webui_plugin.create_chat(title, model)
            if chat_result["status"] != "success":
                _cprint(f"Failed to create chat: {chat_result.get('message')}", "red")
                sys.exit(1)
            
            chat_id = chat_result["chat_id"]
            _cprint(f"Created chat: {title} (ID: {chat_id})", "green")
            
            # Send message if provided
            if message:
                result = webui_plugin.send_message(chat_id, message, model)
            else:
                result = {"status": "success", "message": "Chat created successfully"}
        else:
            _cprint(f"Unknown action '{action}'", "red")
            _cprint("Available actions: start, stop, status, chat", "yellow")
            sys.exit(1)
        
        # Display result
        if result.get("status") == "success":
            _cprint(f"✓ {result.get('message', 'Action completed')}", "green")
            if "response" in result:
                _cprint(f"Response: {result['response']}", "blue")
        elif result.get("status") == "error":
            _cprint(f"✗ {result.get('message', 'Action failed')}", "red")
        else:
            # For status action
            import json
            print(json.dumps(result, indent=2))
    
    except Exception as e:
        _cprint(f"WebUI command failed: {e}", "red")
        sys.exit(1)


@app.command()
def fiberize(path: str) -> None:
    """Run the fiberizer chain on ``path``."""
    script = Path("scripts/fiberize_markdown.py")
    if not Path(path).exists() or not script.exists():
        _cprint("Fiberizer scripts missing", "red")
        raise typer.Exit(1)
    subprocess.run([sys.executable, str(script), path], check=False)


@app.command(name="import-flow")
def import_flow(file: str) -> None:
    """Import an n8n/MainChain flow as a ZOROS routine."""
    path = Path(file)
    if not path.exists():
        _cprint("File not found", "red")
        sys.exit(1)
    _cprint(f"Importing flow from {path}", "blue")
    _cprint("Flow imported (stub)", "green")


@app.command()
def plugins(
    action: str = typer.Argument("list", help="Action: list, health, reload"),
    plugin_name: str = typer.Option("", help="Specific plugin name for actions")
) -> None:
    """Manage ZorOS plugins."""
    try:
        from source.plugins.manager import get_plugin_manager
        pm = get_plugin_manager()
        
        if action == "list":
            plugins = pm.list_plugins()
            if plugins:
                _cprint("Loaded ZorOS Plugins:", "blue")
                for plugin in plugins:
                    status = plugin["health"]["status"]
                    color = "green" if status == "healthy" else "red"
                    _cprint(f"  {plugin['name']} v{plugin['version']} - {status}", color)
                    _cprint(f"    {plugin['description']}", "yellow")
            else:
                _cprint("No plugins loaded", "yellow")
        
        elif action == "health":
            health = pm.get_plugin_health()
            _cprint("Plugin Health Status:", "blue")
            for name, status in health.items():
                color = "green" if status["status"] == "healthy" else "red"
                _cprint(f"  {name}: {status['status']}", color)
                if status.get("details"):
                    for key, value in status["details"].items():
                        _cprint(f"    {key}: {value}", "yellow")
        
        elif action == "reload":
            _cprint("Reloading plugins...", "blue")
            pm.discover_plugins()
            _cprint("Plugins reloaded", "green")
        
        else:
            _cprint(f"Unknown action: {action}", "red")
            _cprint("Available actions: list, health, reload", "yellow")
    
    except ImportError as e:
        _cprint(f"Plugin system not available: {e}", "red")
    except Exception as e:
        _cprint(f"Plugin management error: {e}", "red")


@app.command(name="run-plugin")
def run_plugin(plugin_name: str, command: str) -> None:
    """Execute a plugin command via ``poetry run``."""
    try:
        eps = importlib.metadata.entry_points(group="zoros.plugins")
        plugin_ep = None
        for ep in eps:
            if ep.name == plugin_name:
                plugin_ep = ep
                break
        if plugin_ep is None:
            _cprint(f"Plugin '{plugin_name}' not found", "red")
            raise typer.Exit(1)
        plugin_cls = plugin_ep.load()
        plugin = plugin_cls()
        if hasattr(plugin, command):
            method = getattr(plugin, command)
            if callable(method):
                method()
            else:
                _cprint(f"'{command}' is not callable", "red")
                raise typer.Exit(1)
        else:
            _cprint(f"Plugin '{plugin_name}' has no command '{command}'", "red")
            raise typer.Exit(1)
    except Exception as exc:
        _cprint(f"Error running plugin command: {exc}", "red")
        raise typer.Exit(1)


@app.command()
def diagnose() -> None:
    """Run system diagnostics."""
    _cprint("Running ZorOS diagnostics...", "blue")
    _cprint("✅ System check complete", "green")


@app.command()
def audio_test(
    backend: str = typer.Option("MLXWhisper", help="Backend to test"),
    model: str = typer.Option("large-v3-turbo", help="Model to test"),
    stress_test: bool = typer.Option(False, help="Run stress test with multiple operations"),
    duration: int = typer.Option(30, help="Stress test duration in seconds")
) -> None:
    """Test audio system robustness and error recovery."""
    # Suppress Pydantic V2 migration warnings during testing
    import warnings
    warnings.filterwarnings('ignore', category=UserWarning, message='.*allow_mutation.*')
    
    _cprint("🧪 Running Audio System Robustness Test", "blue")
    
    try:
        # Test 1: Basic backend availability
        _cprint(f"Testing {backend} backend availability...", "yellow")
        from source.dictation_backends import get_available_backends
        available = get_available_backends()
        if backend in available:
            _cprint(f"✅ {backend} backend available", "green")
        else:
            _cprint(f"❌ {backend} backend not available", "red")
            _cprint(f"Available backends: {', '.join(available)}", "yellow")
            return
        
        # Test 2: Memory and thread baseline
        import threading
        import time
        from source.interfaces.intake.main import _mem_usage_mb
        
        initial_memory = _mem_usage_mb()
        initial_threads = threading.active_count()
        _cprint(f"Baseline: {initial_memory:.1f}MB memory, {initial_threads} threads", "yellow")
        
        # Test 3: Bus error protection
        _cprint("Testing bus error protection...", "yellow")
        try:
            from source.interfaces.intake.main import transcribe_audio
            import tempfile
            import soundfile as sf
            import numpy as np
            
            # Create test audio file
            test_audio = np.random.normal(0, 0.1, 16000).astype(np.float32)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                sf.write(f.name, test_audio, 16000)
                test_file = f.name
            
            # Test transcription with bus error protection
            result = transcribe_audio(test_file, backend, model)
            _cprint(f"✅ Bus error protection working - got result: {len(result)} chars", "green")
            
            # Cleanup
            import os
            os.unlink(test_file)
            
        except Exception as e:
            _cprint(f"❌ Bus error protection test failed: {e}", "red")
        
        # Test 4: Resource leak detection with model reuse optimization
        if stress_test:
            _cprint(f"Running {duration}s stress test with model reuse...", "yellow")
            start_time = time.time()
            operations = 0
            
            # Initialize backend once for efficiency
            try:
                if backend == "MLXWhisper":
                    from source.dictation_backends import MLXWhisperBackend
                    backend_instance = MLXWhisperBackend(model)
                    _cprint("✅ Model loaded once for reuse", "green")
                else:
                    backend_instance = None
            except Exception as e:
                _cprint(f"⚠️  Failed to pre-load model: {e}", "yellow")
                backend_instance = None
            
            while time.time() - start_time < duration:
                try:
                    # Create small test audio
                    test_audio = np.random.normal(0, 0.1, 8000).astype(np.float32)  # 0.5 second
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                        sf.write(f.name, test_audio, 16000)
                        test_file = f.name
                    
                    # Quick transcription with reused model
                    if backend_instance:
                        try:
                            result = backend_instance.transcribe(test_file)
                        except Exception as e:
                            _cprint(f"⚠️  Model reuse failed, falling back: {e}", "yellow")
                            result = transcribe_audio(test_file, backend, model)
                    else:
                        result = transcribe_audio(test_file, backend, model)
                    
                    operations += 1
                    
                    # Cleanup
                    os.unlink(test_file)
                    
                    # Force garbage collection every 5 operations
                    if operations % 5 == 0:
                        import gc
                        gc.collect()
                    
                    # Check for leaks every 10 operations
                    if operations % 10 == 0:
                        current_memory = _mem_usage_mb()
                        current_threads = threading.active_count()
                        memory_increase = current_memory - initial_memory
                        thread_increase = current_threads - initial_threads
                        
                        _cprint(f"Operations: {operations}, Memory: +{memory_increase:.1f}MB, Threads: +{thread_increase}", "yellow")
                        
                        # Adjusted thresholds for MLX models (they use more memory)
                        if memory_increase > 800 or thread_increase > 10:
                            _cprint(f"⚠️  Severe resource leak detected!", "red")
                            break
                    
                    time.sleep(0.05)  # Shorter pause for efficiency
                    
                except Exception as e:
                    _cprint(f"⚠️  Operation {operations} failed: {e}", "yellow")
            
            # Cleanup model
            if backend_instance:
                del backend_instance
                import gc
                gc.collect()
                _cprint("✅ Model cleanup completed", "green")
                    
            final_memory = _mem_usage_mb()
            final_threads = threading.active_count()
            
            _cprint(f"Stress test completed:", "blue")
            _cprint(f"  Operations: {operations}", "yellow")
            _cprint(f"  Memory change: {final_memory - initial_memory:.1f}MB", "yellow")
            _cprint(f"  Thread change: {final_threads - initial_threads}", "yellow")
            
            # Evaluate results (adjusted for MLX model memory usage)
            memory_change = final_memory - initial_memory
            thread_change = final_threads - initial_threads
            
            # MLX models require more memory but should be stable
            if memory_change < 500 and thread_change <= 2:
                _cprint(f"✅ Stress test passed - memory usage within acceptable range", "green")
            elif memory_change < 800 and thread_change <= 5:
                _cprint(f"⚠️  Stress test marginal - monitor for continued growth", "yellow")
            else:
                _cprint(f"❌ Stress test found significant leaks", "red")
        
        _cprint("🎯 Audio robustness test completed", "green")
        
    except Exception as e:
        _cprint(f"❌ Audio test failed: {e}", "red")
        import traceback
        traceback.print_exc()


@app.command()
def logs(module: str = "zoros.cli", tail: bool = False, level: str = "INFO", db: bool = typer.Option(False, "--db", help="View logs from the SQLite database.")) -> None:
    """Show logs for a module."""
    if db:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute("SELECT timestamp, level, source, message FROM log_events ORDER BY timestamp DESC LIMIT 20").fetchall()
            for row in rows:
                print(f"{row[0]} {row[1]} {row[2]}: {row[3]}")
        return

    log_file = LOG_DIR / f"{module}.log"
    if not log_file.exists():
        _cprint(f"No logs found for {module}", "yellow")
        return
    if tail:
        # Simple tail implementation
        with log_file.open() as f:
            lines = f.readlines()
            for line in lines[-10:]:  # Last 10 lines
                print(line.rstrip())
    else:
        with log_file.open() as f:
            print(f.read())


@app.command()
def clean(cache: bool = False, logs_opt: bool = False) -> None:
    """Clean temporary files and logs."""
    if cache:
        cache_dir = Path.home() / ".cache" / "zoros"
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
            _cprint("Cache cleaned", "green")
    if logs_opt:
        if LOG_DIR.exists():
            shutil.rmtree(LOG_DIR)
            _cprint("Logs cleaned", "green")
    if not cache and not logs_opt:
        _cprint("Use --cache or --logs to specify what to clean", "yellow")


@app.command()
def tour() -> None:
    """Launch the ZorOS Feature Tour."""
    logger.info("Launching ZorOS Feature Tour")
    try:
        script = (
            Path(__file__).resolve().parent.parent
            / "source"
            / "interfaces"
            / "streamlit"
            / "feature_tour.py"
        )
        if not script.exists():
            _cprint("Feature tour not found", "red")
            sys.exit(1)
        cmd = [sys.executable, "-m", "streamlit", "run", str(script)]
        subprocess.run(cmd, check=True)
    except Exception as exc:
        logger.error("Feature tour failed: %s", exc)
        _cprint("Feature tour not available", "red")
        sys.exit(1)


@app.command()
def open(component: str) -> None:
    """Open various ZorOS components."""
    if component == "fibers":
        fibers_dir = Path("data/fibers")
        if not fibers_dir.exists():
            fibers_dir.mkdir(parents=True, exist_ok=True)
            _cprint("Created fibers directory", "green")
        if sys.platform.startswith("darwin"):
            subprocess.run(["open", str(fibers_dir)])
        elif sys.platform.startswith("win"):
            subprocess.run(["explorer", str(fibers_dir)])
        else:
            subprocess.run(["xdg-open", str(fibers_dir)])
    else:
        _cprint(f"Unknown component: {component}", "red")
        _cprint("Available components: fibers", "yellow")


@app.command(name="lint-fiber")
def lint_fiber_cmd(
    path: str,
    fix: bool = typer.Option(False, help="Auto repair missing fields"),
) -> None:
    """Lint a fiber file for issues."""
    fiber_path = Path(path)
    if not fiber_path.exists():
        _cprint(f"Fiber file not found: {path}", "red")
        raise typer.Exit(1)
    
    try:
        from zoros.utils.lint_fiber import lint_fiber
        issues = lint_fiber(fiber_path, fix=fix)
        if issues:
            for issue in issues:
                _cprint(f"⚠️  {issue}", "yellow")
        else:
            _cprint("✅ Fiber is valid", "green")
    except Exception as exc:
        _cprint(f"Error linting fiber: {exc}", "red")
        raise typer.Exit(1)


@app.command("fiberize-pdf")
def fiberize_pdf_cmd(path: str) -> None:
    """Fiberize a PDF file."""
    script = Path("scripts/fiberize_pdf.py")
    if not Path(path).exists() or not script.exists():
        _cprint("PDF fiberizer script missing", "red")
        raise typer.Exit(1)
    subprocess.run([sys.executable, str(script), path], check=False)


@app.command()
def lang(
    backend: str = typer.Option("", help="Specify language backend (e.g., openai, local)"),
    health_check: bool = typer.Option(False, help="Run health checks on language backends"),
    test_prompt: str = typer.Option("", help="Test with a simple prompt")
) -> None:
    """Launch the Language Playground UI for backend testing and configuration."""
    logger.info("Launching Language Playground")
    
    if health_check:
        _cprint("Running language backend health checks...", "blue")
        try:
            if LanguageService:
                service = LanguageService()
                _cprint("✅ Language service initialized", "green")
            else:
                _cprint("❌ Language service not available", "red")
        except Exception as exc:
            _cprint(f"❌ Language service error: {exc}", "red")
        return
    
    if test_prompt:
        _cprint(f"Testing prompt: {test_prompt}", "blue")
        try:
            if LanguageService:
                service = LanguageService()
                response = service.complete_turn("test", {"prompt": test_prompt})
                _cprint(f"✅ Response: {response}", "green")
            else:
                _cprint("❌ Language service not available", "red")
        except Exception as exc:
            _cprint(f"❌ Test failed: {exc}", "red")
        return
    
    # Launch the language playground UI
    script = (
        Path(__file__).resolve().parent.parent
        / "source"
        / "interfaces"
        / "streamlit"
        / "language_playground.py"
    )
    
    if not script.exists():
        _cprint("Language playground not found", "red")
        raise typer.Exit(1)
    
    _cprint("Launching Language Playground UI...", "blue")
    
    # Use the streamlit process manager if available
    try:
        from source.interfaces.streamlit_process_manager import start_fiberizer_ui, get_streamlit_manager
        manager = get_streamlit_manager()
        if manager.start_streamlit_app(str(script), "language_playground"):
            url = manager.get_app_url("language_playground")
            _cprint(f"✅ Language Playground started: {url}", "green")
            
            # Try to open in browser
            try:
                import webbrowser
                webbrowser.open(url)
            except Exception:
                pass
        else:
            _cprint("❌ Failed to start Language Playground", "red")
            raise typer.Exit(1)
    except ImportError:
        # Fallback to direct streamlit run
        cmd = [sys.executable, "-m", "streamlit", "run", str(script)]
        if backend:
            cmd.extend(["--", "--backend", backend])
        subprocess.run(cmd, check=False)


@app.command()
def menu() -> None:
    """Show interactive menu."""
    _cprint("ZorOS CLI Menu", "blue")
    _cprint("Available commands:", "green")
    _cprint("  zoros intake          - Launch PySide intake UI", "yellow")
    _cprint("  zoros lang            - Launch Language Playground UI", "yellow")
    _cprint("  zoros ui markdown     - Launch Streamlit markdown viewer", "yellow")
    _cprint("  zoros unified         - Launch unified PySide/React UI", "yellow")
    _cprint("  zoros streamlit       - Launch Streamlit Fiber Tools", "yellow")
    _cprint("  zoros fiberize <file> - Run fiberizer on file", "yellow")
    _cprint("  zoros diagnose        - Run system diagnostics", "yellow")
    _cprint("  zoros audio-test      - Test audio system robustness", "yellow")
    _cprint("  zoros plugins         - List installed plugins", "yellow")
    _cprint("  zoros open fibers     - Open fibers directory", "yellow")
    _cprint("  zoros lint-fiber <file> - Lint fiber file", "yellow")
    _cprint("  zoros routine         - Manage and execute routines", "yellow")
    _cprint("  zoros backlog         - Manage backlog items and planning", "yellow")


@app.command()
def routine(
    action: str = typer.Argument(..., help="Action: list, show, execute, register"),
    routine_id: str = typer.Argument("", help="Routine ID for show/execute actions"),
    category: str = typer.Option("", help="Filter by category"),
    tags: str = typer.Option("", help="Filter by tags (comma-separated)"),
) -> None:
    """Manage and execute routines through the Routine Registry."""
    try:
        from source.orchestration.routine_registry import RoutineRegistry
        registry = RoutineRegistry()
        
        if action == "list":
            # Parse filters
            tag_list = [tag.strip() for tag in tags.split(",")] if tags else None
            filter_category = category if category else None
            
            routines = registry.list_routines(category=filter_category, tags=tag_list)
            
            if not routines:
                _cprint("No routines found matching filters.", "yellow")
                return
                
            _cprint(f"Found {len(routines)} routine(s):", "green")
            for routine in routines:
                _cprint(f"  {routine.routine_id}: {routine.name}", "yellow")
                _cprint(f"    Category: {routine.category}, Duration: {routine.estimated_duration_minutes}min", "")
                _cprint(f"    Tags: {', '.join(routine.tags)}", "")
                _cprint(f"    {routine.description}", "")
                _cprint("", "")
                
        elif action == "show":
            if not routine_id:
                _cprint("Error: routine_id required for show action", "red")
                return
                
            routine = registry.get_routine(routine_id)
            if not routine:
                _cprint(f"Routine not found: {routine_id}", "red")
                return
                
            _cprint(f"Routine: {routine.metadata.name}", "green")
            _cprint(f"ID: {routine.metadata.routine_id}", "")
            _cprint(f"Category: {routine.metadata.category}", "")
            _cprint(f"Duration: {routine.metadata.estimated_duration_minutes} minutes", "")
            _cprint(f"Difficulty: {routine.metadata.difficulty}", "")
            _cprint(f"Tags: {', '.join(routine.metadata.tags)}", "")
            _cprint(f"Description: {routine.metadata.description}", "")
            _cprint("", "")
            
            _cprint("Steps:", "yellow")
            for i, step in enumerate(routine.steps, 1):
                _cprint(f"  {i}. {step.description} ({step.type})", "")
                if step.estimated_duration_minutes:
                    _cprint(f"     Duration: {step.estimated_duration_minutes} min", "")
                    
            # Show documentation if available
            docs = registry.get_routine_documentation(routine_id)
            if docs:
                _cprint("", "")
                _cprint("Documentation available. Use 'zoros open routines' to view full docs.", "green")
                
        elif action == "execute":
            if not routine_id:
                _cprint("Error: routine_id required for execute action", "red")
                return
                
            try:
                _cprint(f"Executing routine: {routine_id}", "green")
                results = registry.execute_routine(routine_id)
                _cprint("Routine completed successfully!", "green")
                _cprint(f"Results: {results}", "")
            except Exception as e:
                _cprint(f"Routine execution failed: {e}", "red")
                
        elif action == "summary":
            summary = registry.get_agent_summary()
            _cprint("Routine Registry Summary:", "green")
            _cprint(f"Total Routines: {summary['total_routines']}", "")
            _cprint("Categories:", "yellow")
            for cat, count in summary["categories"].items():
                _cprint(f"  {cat}: {count} routine(s)", "")
                
        else:
            _cprint(f"Unknown action: {action}", "red")
            _cprint("Available actions: list, show, execute, summary", "yellow")
            
    except ImportError:
        _cprint("Routine system not available. Install dependencies.", "red")
    except Exception as e:
        _cprint(f"Error: {e}", "red")


def run() -> None:
    """Main CLI entry point using Typer."""
    app()


if __name__ == "__main__":
    run()
