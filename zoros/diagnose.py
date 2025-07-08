from __future__ import annotations

"""System diagnostics helpers for the ``zoros diagnose`` command.

This module implements a set of basic health checks used by the command
line interface. Results are printed with simple colour codes.

Specification: docs/specs/codex_task_spec.md#L1-L25
Tests: tests/test_zoros_diagnose.py
"""

from dataclasses import dataclass
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Iterable
import tomllib


@dataclass
class CheckResult:
    """Outcome of a single system check."""

    label: str
    status: str  # "ok", "warn", or "fail"
    info: str
    fix: str | None = None


def _color(text: str, status: str) -> str:
    colors = {
        "ok": "\033[92m",
        "warn": "\033[93m",
        "fail": "\033[91m",
        "reset": "\033[0m",
    }
    return f"{colors.get(status, '')}{text}{colors['reset']}"


def _human_size(num: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if num < 1024:
            return f"{num:.1f}{unit}"
        num /= 1024
    return f"{num:.1f}TB"


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                continue
    return total


def check_python_version() -> CheckResult:
    ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    status = "ok" if sys.version_info >= (3, 11) else "fail"
    fix = None
    if status == "fail":
        fix = "Install Python 3.11+"
    return CheckResult("Python", status, ver, fix)


def check_poetry_version(run=subprocess.run) -> CheckResult:
    try:
        proc = run(["poetry", "--version"], capture_output=True, text=True, check=False)
    except Exception:
        return CheckResult("Poetry", "fail", "not found", "Install Poetry")
    if proc.returncode != 0:
        return CheckResult("Poetry", "fail", "not found", "Install Poetry")
    version = proc.stdout.strip().split()[-1]
    return CheckResult("Poetry", "ok", version)


def check_plugins(base: Path) -> Iterable[CheckResult]:
    pyproject = base / "pyproject.toml"
    if not pyproject.exists():
        return [CheckResult("Plugins", "fail", "pyproject.toml missing")]
    data = tomllib.loads(pyproject.read_text())
    plugins = (
        data.get("tool", {})
        .get("poetry", {})
        .get("plugins", {})
        .get("zoros.plugins", {})
    )
    results: list[CheckResult] = []
    for mod_path in plugins.values():
        module = mod_path.split(":")[0]
        path = base / module.replace(".", "/")
        size = _dir_size(path)
        status = "ok" if size < 50 * 1024 * 1024 else "warn"
        fix = None
        if status == "warn":
            fix = "Consider cleaning unused assets"
        results.append(CheckResult(module, status, _human_size(size), fix))
    if not results:
        results.append(CheckResult("Plugins", "warn", "none found"))
    return results


def check_disk_usage(path: Path, label: str, warn_mb: int | None = None) -> CheckResult:
    size = _dir_size(path) if path.is_dir() else path.stat().st_size if path.exists() else 0
    status = "ok"
    fix = None
    if warn_mb and size > warn_mb * 1024 * 1024:
        status = "warn"
        fix = f"Run 'zoros clean' to trim {label}"
    return CheckResult(label, status, _human_size(size), fix)


def check_sqlite(db: Path) -> CheckResult:
    if not db.exists():
        return CheckResult("SQLite", "warn", "no database")
    fibers = 0
    threads = 0
    last = "n/a"
    try:
        with sqlite3.connect(db) as conn:
            try:
                fibers = conn.execute("SELECT COUNT(*) FROM fibers").fetchone()[0]
            except sqlite3.OperationalError:
                fibers = 0
            try:
                threads = conn.execute("SELECT COUNT(*) FROM threads").fetchone()[0]
            except sqlite3.OperationalError:
                threads = 0
            try:
                row = conn.execute("SELECT MAX(created_at) FROM fibers").fetchone()
                if row and row[0]:
                    last = row[0]
            except sqlite3.OperationalError:
                pass
    except Exception:
        return CheckResult("SQLite", "fail", "unable to read", "Check DB path")
    info = f"fibers={fibers}, threads={threads}, last={last}"
    return CheckResult("SQLite", "ok", info)


def check_tool(names: list[str], label: str) -> CheckResult:
    for name in names:
        if shutil.which(name):
            return CheckResult(label, "ok", name)
    return CheckResult(label, "fail", "missing", f"Install {label}")


def run_diagnose(base: Path = Path.cwd()) -> int:
    """Run system diagnostics and print a health report."""
    checks: list[CheckResult] = []
    checks.append(check_python_version())
    checks.append(check_poetry_version())
    checks.extend(check_plugins(base))
    checks.append(check_disk_usage(base / "logs" / "errors", "Logs", warn_mb=500))
    checks.append(check_disk_usage(base / "zoros_plugins", "Plugins dir"))
    db = base / "data" / "fibers.db"
    checks.append(check_disk_usage(db, "DB"))
    checks.append(check_sqlite(db))
    checks.append(check_tool(["whisper.cpp", "whisper"], "Whisper"))
    checks.append(check_tool(["lmos"], "LMOS"))
    checks.append(check_tool(["ffmpeg"], "ffmpeg"))

    fail = False
    for c in checks:
        line = f"{c.label:12}: {_color(c.status.upper(), c.status)} - {c.info}"
        print(line)
        if c.fix:
            print(f"    Suggestion: {c.fix}")
        if c.status == "fail":
            fail = True
    return 1 if fail else 0
