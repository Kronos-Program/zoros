"""Logging utilities for ZorOS.

This module provides ``get_logger`` for unified log configuration. It
supports YAML configuration and a SQLite-backed handler for persistent
records.

Specification: docs/PROJECT_DOCS.txt#L3185-L3196
Architecture: docs/zoros_architecture.md#observability
Tests: tests/test_logger.py
Operational: logging_config.yaml
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import os
try:
    import yaml
except Exception:  # pragma: no cover - optional dependency
    yaml = None  # type: ignore

# Paths configurable for tests
CONFIG_PATH = Path(os.getenv("ZOROS_LOG_CONFIG", "logging_config.yaml"))
LOG_DIR = Path(os.getenv("ZOROS_LOG_DIR", "logs"))
DB_PATH = Path(os.getenv("DATA_DIR", "data")) / "logs.db"

_LOG_CONFIG: Optional[dict] = None
_ERROR_COUNT: Dict[tuple[str, str], int] = {}


def _load_config() -> dict:
    global _LOG_CONFIG
    if _LOG_CONFIG is not None:
        return _LOG_CONFIG
    if CONFIG_PATH.exists() and yaml:
        try:
            if yaml is not None:
                _LOG_CONFIG = yaml.safe_load(CONFIG_PATH.read_text()) or {}
            else:
                from source.language_service import _load_simple_yaml
                _LOG_CONFIG = _load_simple_yaml(CONFIG_PATH)
        except Exception:
            _LOG_CONFIG = {}
    else:
        _LOG_CONFIG = {}
    return _LOG_CONFIG


class SQLiteHandler(logging.Handler):
    """Logging handler that stores events in SQLite."""

    def __init__(self) -> None:
        super().__init__()
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS log_events (timestamp TEXT, level TEXT, source TEXT, message TEXT)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS log_fibers (id TEXT PRIMARY KEY, timestamp TEXT, level TEXT, source TEXT, message TEXT, tags TEXT)"
            )
            conn.commit()

    def emit(self, record: logging.LogRecord) -> None:
        ts = datetime.utcfromtimestamp(record.created).isoformat()
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO log_events (timestamp, level, source, message) VALUES (?,?,?,?)",
                (ts, record.levelname, record.name, record.getMessage()),
            )
            conn.commit()
        if record.levelno >= logging.WARNING:
            repeat = _increment_error(record)
            from backend.core.models.log_fiber import LogFiber

            fiber = LogFiber.create_from_log(record, repeat=repeat)
            fiber.save()


def _increment_error(record: logging.LogRecord) -> bool:
    key = (record.name, record.getMessage())
    _ERROR_COUNT[key] = _ERROR_COUNT.get(key, 0) + 1
    return _ERROR_COUNT[key] > 1


def get_logger(name: str) -> logging.Logger:
    cfg = _load_config()
    logger = logging.getLogger(name)

    # Ensure handlers are attached once with consistent formatting
    if not logger.handlers:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        fmt = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")

        fh = logging.FileHandler(LOG_DIR / f"{name}.log")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        logger.addHandler(SQLiteHandler())

        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        logger.addHandler(sh)

    # Resolve level from config with module override
    level = cfg.get("modules", {}).get(name, cfg.get("default_level", "INFO"))
    lvl = getattr(logging, str(level).upper(), logging.INFO)

    suppress = bool(cfg.get("suppress_debug"))
    if suppress and lvl < logging.INFO:
        # Override any DEBUG/NOTSET to INFO when suppression is enabled
        lvl = logging.INFO

    # Apply computed level to the logger
    logger.setLevel(lvl)

    # When suppressing debug, guard handlers too in case logger level is later changed.
    if suppress:
        class _NoDebugFilter(logging.Filter):
            def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
                # Allow INFO and above; drop DEBUG/NOTSET
                return record.levelno >= logging.INFO

        for h in logger.handlers:
            # Ensure handlers won't emit DEBUG even if logger level changes elsewhere
            h.setLevel(max(getattr(h, "level", logging.NOTSET) or logging.NOTSET, logging.INFO))
            h.addFilter(_NoDebugFilter())

    return logger
