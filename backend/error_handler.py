import json
import os
import sqlite3
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from source.language_service import LanguageService


DB_PATH = Path(os.getenv("DATA_DIR", "data")) / "fibers.db"
LOG_DIR = Path("logs/errors")


def _ensure_tables() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fibers (
                id TEXT PRIMARY KEY,
                content TEXT,
                tags TEXT,
                created_at TEXT,
                source TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS suggestions (
                fiber_id TEXT,
                suggestion_text TEXT,
                created_at TEXT
            )
            """
        )
        conn.commit()


def _insert_error_fiber(content: str) -> str:
    _ensure_tables()
    fid = str(uuid4())
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO fibers (id, content, tags, created_at, source) VALUES (?,?,?,?,?)",
            (fid, content, json.dumps(["error"]), datetime.utcnow().isoformat(), "error_handler"),
        )
        conn.commit()
    return fid


def _insert_suggestion(fid: str, text: str) -> None:
    _ensure_tables()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO suggestions (fiber_id, suggestion_text, created_at) VALUES (?,?,?)",
            (fid, text, datetime.utcnow().isoformat()),
        )
        conn.commit()


def _log_error(request: Request, exc: Exception, trace: str) -> str:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"{datetime.utcnow():%Y-%m-%d}.jsonl"
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "path": request.url.path,
        "method": request.method,
        "error": str(exc),
        "traceback": trace,
    }
    with log_file.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    return trace


def _background_log(request: Request, exc: Exception) -> None:
    trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    _log_error(request, exc, trace)
    content = f"Error: {exc}\nTraceback: {trace}"
    fid = _insert_error_fiber(content)
    short = "\n".join(trace.splitlines()[-5:])
    prompt = f"Here is a traceback for {request.url.path}:\n{short}\nSuggest a fix."
    try:
        svc = LanguageService()
        resp = svc.complete_turn("suggest_fix", {"prompt": prompt})
        suggestion = resp.get("content", "")
    except Exception:
        suggestion = ""
    if suggestion:
        _insert_suggestion(fid, suggestion)


def init_error_handler(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def handle_exception(request: Request, exc: Exception) -> JSONResponse:  # type: ignore[override]
        threading.Thread(target=_background_log, args=(request, exc), daemon=True).start()
        return JSONResponse(
            status_code=500,
            content={"error": "Internal error. An error report has been generated."},
        )


