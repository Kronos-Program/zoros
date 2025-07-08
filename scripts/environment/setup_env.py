#!/usr/bin/env python3
"""
Setup Environment for Zoros SpindleSpeak

This script installs Python requirements and any JavaScript dependencies
found in `package.json`. It's designed to work in both development and
production environments, with support for headless server configurations.

Features:
- Automatic setup and upgrade of Python build tools (pip, setuptools, wheel)
- Python dependency installation via pip with build tool verification
- JavaScript dependency installation via npm
- Headless server support (offscreen Qt, dummy audio)
- Comprehensive error handling and logging
- Cross-platform compatibility

Example:
    python scripts/environment/setup_env.py

Dependencies:
    - Python 3.x
    - pip
    - npm (if package.json exists)
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
import os
import traceback

ROOT = Path(__file__).resolve().parent.parent.parent

# Configure basic logging for debugging purposes
logging.basicConfig(level=logging.INFO, format="[setup_env] %(message)s")


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Execute a subprocess while logging the command and errors."""
    logging.info("Running: %s", " ".join(map(str, cmd)))
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if check and proc.returncode != 0:
        logging.error("Command failed with code %s: %s", proc.returncode, cmd)
        if proc.stdout:
            logging.error("stdout:\n%s", proc.stdout)
        if proc.stderr:
            logging.error("stderr:\n%s", proc.stderr)
        raise subprocess.CalledProcessError(proc.returncode, cmd,
                                            output=proc.stdout,
                                            stderr=proc.stderr)
    return proc


def check_and_upgrade_build_tools() -> None:
    """Check and upgrade essential Python build tools."""
    logging.info("Checking and upgrading Python build tools...")
    
    # Check if pip is working
    try:
        proc = run([sys.executable, "-m", "pip", "--version"], check=False)
        if proc.returncode != 0:
            logging.warning("pip not working properly, trying to fix...")
            run([sys.executable, "-m", "ensurepip", "--upgrade"])
    except Exception as e:
        logging.warning("pip check failed: %s", e)
        try:
            run([sys.executable, "-m", "ensurepip", "--upgrade"])
        except Exception:
            logging.error("Failed to ensure pip is installed")
            raise
    
    # Upgrade core build tools
    essential_packages = ["pip", "setuptools", "wheel"]
    for package in essential_packages:
        try:
            logging.info("Upgrading %s...", package)
            run([sys.executable, "-m", "pip", "install", "--upgrade", package])
        except subprocess.CalledProcessError as e:
            logging.warning("Failed to upgrade %s: %s", package, e)
            # Try force reinstall for setuptools if upgrade fails
            if package == "setuptools":
                try:
                    logging.info("Attempting force reinstall of setuptools...")
                    run([sys.executable, "-m", "pip", "install", "--force-reinstall", "setuptools"])
                except subprocess.CalledProcessError:
                    logging.error("Critical: Cannot install setuptools. This may cause build failures.")
                    raise
    
    # Verify setuptools can be imported
    try:
        proc = run([sys.executable, "-c", "import setuptools; print(f'setuptools {setuptools.__version__} OK')"])
        logging.info("setuptools verification: %s", proc.stdout.strip())
    except subprocess.CalledProcessError:
        logging.error("setuptools verification failed - builds may fail")
        raise


def main() -> None:
    """Install Python and JavaScript dependencies.

    Sets Qt to offscreen mode when no display is detected so PySide and other
    GUI libraries can initialise on headless servers.
    """
    if "DISPLAY" not in os.environ:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    
    # First, ensure build tools are properly installed and up to date
    try:
        check_and_upgrade_build_tools()
    except Exception:
        logging.error("Failed to setup build tools - continuing anyway, but builds may fail")
        traceback.print_exc()
    
    req = ROOT / "requirements.txt"
    if req.exists():
        try:
            run([sys.executable, "-m", "pip", "install", "-r", str(req)])
        except subprocess.CalledProcessError:
            logging.error("pip install failed - attempting fallback strategy")
            traceback.print_exc()
            
            # Try installing with more permissive strategies
            try:
                logging.info("Attempting pip install with --no-build-isolation...")
                run([sys.executable, "-m", "pip", "install", "--no-build-isolation", "-r", str(req)])
            except subprocess.CalledProcessError:
                try:
                    logging.info("Attempting pip install with --only-binary=:all:...")
                    run([sys.executable, "-m", "pip", "install", "--only-binary=:all:", "-r", str(req)])
                except subprocess.CalledProcessError:
                    logging.error("All pip install strategies failed")
                    raise
    pkg_json = ROOT / "package.json"
    if pkg_json.exists():
        try:
            run(["npm", "install"], cwd=ROOT)
        except subprocess.CalledProcessError:
            logging.error("npm install failed")
            traceback.print_exc()
            raise
    else:
        logging.info("No package.json found; skipping npm install.")


if __name__ == "__main__":
    main() 