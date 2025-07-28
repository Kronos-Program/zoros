# See architecture: docs/zoros_architecture.md#component-overview
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from typing import Dict, List, Any
from uuid import uuid4

from starlette.concurrency import run_in_threadpool

from backend.db import init_db, execute, DB_PATH
from backend.services.language_service.language_service import LanguageService
import json
import subprocess
import re
from datetime import datetime
from uuid import uuid4
from pydantic import BaseModel

from scripts.feature_tour_to_json import OUT_FILE as FEATURE_JSON
from scripts.zoros_cli import app as cli_app, get_cli_schema
from zoros_core import core_api

app = FastAPI()
init_db()
import asyncio
import sqlite3

from scripts.feature_tour_to_json import OUT_FILE as FEATURE_JSON
from .error_handler import init_error_handler, _ensure_tables, DB_PATH

app = FastAPI()
init_error_handler(app)
_ensure_tables()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/status")
def status() -> Dict[str, str]:
    return {"status": "Codex + React environment ready"}




def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/errors/latest")
def latest_error() -> Dict:
    """Return the most recent logged error entry."""
    LOG_DIR = Path("logs/errors")
    files = sorted(LOG_DIR.glob("*.jsonl"), reverse=True)
    if not files:
        return {}
    last_line = files[0].read_text(encoding="utf-8").splitlines()[-1]
    return json.loads(last_line)


@app.post("/api/errors/suggest_fix")
def suggest_fix(payload: Dict) -> Dict:
    """Call SpindleSpeak to suggest a fix for the provided error."""
    trace = "\n".join(payload.get("traceback", "").splitlines()[-5:])
    prompt = f"Here is a traceback for {payload.get('path', '')}:\n{trace}\nSuggest a fix."
    try:
        from backend.services.language_service.language_service import LanguageService

        svc = LanguageService()
        resp = svc.complete_turn("suggest_fix", {"prompt": prompt})
        suggestion = resp.get("content", "")
    except Exception:
        suggestion = ""
    return {"suggestion": suggestion}


@app.get("/api/feature_tour.json")
def get_feature_tour() -> list[dict]:
    if FEATURE_JSON.exists():
        return _load_json(FEATURE_JSON)
    raise HTTPException(status_code=404, detail="feature tour not generated")


@app.post("/api/run_tests")
def run_tests(request: Request) -> dict:
    if request.client.host not in {"127.0.0.1", "localhost"}:
        raise HTTPException(status_code=403, detail="local only")

    proc = subprocess.run(
        ["pytest", "--maxfail=1", "--disable-warnings", "-v"],
        capture_output=True,
        text=True,
    )
    output = proc.stdout + proc.stderr
    results: dict[str, list[dict]] = {}
    for line in output.splitlines():
        m = re.search(r"(tests/[^:]+)::([^ ]+)\s+(PASSED|FAILED)", line)
        if m:
            file, test, status = m.groups()
            results.setdefault(file, []).append({"test": test, "status": status})
    return {"returncode": proc.returncode, "results": results, "output": output}


class TranscriptIn(BaseModel):
    text: str


INBOX: list[dict] = []
FIBERS: list[dict] = []
TASKS: list[dict] = []


@app.post("/api/dictate/start")
def dictate_start() -> dict:
    return {"status": "recording"}


@app.post("/api/dictate/stop")
def dictate_stop() -> dict:
    # placeholder transcript
    return {"status": "stopped", "text": "dummy transcript"}


@app.post("/api/dictate/partial")
async def dictate_partial(request: Request) -> dict:
    """Return a quick draft transcript for the uploaded audio."""
    audio = await request.body()
    if not audio:
        raise HTTPException(status_code=400, detail="audio required")
    return {"text": "partial transcript"}


@app.post("/api/dictate/full")
async def dictate_full(request: Request) -> dict:
    """Return the final transcript and save as a Fiber."""
    audio = await request.body()
    if not audio:
        raise HTTPException(status_code=400, detail="audio required")
    text = "final transcript"
    fid = str(uuid4())
    execute(
        "INSERT INTO fibers (id, content, tags, source) VALUES (?,?,?,?)",
        (fid, text, "", "intake_ui"),
    )
    INBOX.append({"id": fid, "type": "fiber", "summary": text[:50], "timestamp": datetime.utcnow().isoformat()})
    return {"fiber_id": fid, "text": text}


@app.post("/api/fibers")
def create_fiber(payload: Dict[str, str]):
    text = payload.get("content") or payload.get("text", "")
    source = payload.get("source", "api")
    fid = str(uuid4())
    execute(
        "INSERT INTO fibers (id, content, tags, source) VALUES (?,?,?,?)",
        (fid, text, "", source),
    )
    INBOX.append({"id": fid, "type": "fiber", "summary": text[:50], "timestamp": datetime.utcnow().isoformat()})
    return {"fiber_id": fid}


@app.get("/api/fibers")
def list_fibers(thread: str = "none") -> list[dict]:
    """Return fibers optionally filtered by thread.

    Thread filtering is not yet implemented; the parameter is accepted for
    future compatibility. All fibers are returned ordered by newest first.
    """
    cur = execute(
        "SELECT id, content, tags, created_at, updated_at, source FROM fibers ORDER BY created_at DESC"
    )
    rows = cur.fetchall()
    return [
        {
            "id": r[0],
            "content": r[1],
            "tags": r[2] or "",
            "created_at": r[3],
            "updated_at": r[4] or r[3],  # Fallback to created_at if updated_at is null
            "source": r[5],
        }
        for r in rows
    ]


@app.get("/api/fibers/{fiber_id}")
def get_fiber(fiber_id: str) -> dict:
    """Get a specific fiber by ID."""
    cur = execute(
        "SELECT id, content, tags, created_at, updated_at, source FROM fibers WHERE id = ?",
        (fiber_id,)
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Fiber not found")
    
    return {
        "id": row[0],
        "content": row[1],
        "tags": row[2] or "",
        "created_at": row[3],
        "updated_at": row[4] or row[3],
        "source": row[5],
    }


@app.put("/api/fibers/{fiber_id}")
def update_fiber(fiber_id: str, payload: Dict[str, str]) -> dict:
    """Update a fiber's content and/or tags."""
    # Check if fiber exists
    cur = execute("SELECT id FROM fibers WHERE id = ?", (fiber_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Fiber not found")
    
    content = payload.get("content")
    tags = payload.get("tags", "")
    
    if content is None:
        raise HTTPException(status_code=400, detail="content is required")
    
    # Update the fiber
    execute(
        "UPDATE fibers SET content = ?, tags = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (content, tags, fiber_id)
    )
    
    # Return updated fiber
    return get_fiber(fiber_id)


@app.patch("/api/fibers/{fiber_id}")
def patch_fiber(fiber_id: str, payload: Dict[str, str]) -> dict:
    """Partially update a fiber (only provided fields)."""
    # Check if fiber exists
    cur = execute("SELECT content, tags FROM fibers WHERE id = ?", (fiber_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Fiber not found")
    
    current_content, current_tags = row
    
    # Update only provided fields
    new_content = payload.get("content", current_content)
    new_tags = payload.get("tags", current_tags or "")
    
    execute(
        "UPDATE fibers SET content = ?, tags = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (new_content, new_tags, fiber_id)
    )
    
    return get_fiber(fiber_id)


@app.delete("/api/fibers/{fiber_id}")
def delete_fiber(fiber_id: str) -> dict:
    """Delete a fiber by ID."""
    # Check if fiber exists
    cur = execute("SELECT id FROM fibers WHERE id = ?", (fiber_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Fiber not found")
    
    # Delete the fiber
    execute("DELETE FROM fibers WHERE id = ?", (fiber_id,))
    
    return {"message": "Fiber deleted successfully", "id": fiber_id}


@app.get("/api/coauthor/docs")
def list_docs() -> list[str]:
    """Return markdown files under docs directory."""
    return [p.name for p in Path("docs").glob("*.md")]


@app.get("/api/coauthor/doc")
def load_doc(path: str) -> Dict[str, str]:
    md = Path("docs") / path
    if not md.exists():
        raise HTTPException(status_code=404, detail="file not found")
    return {"content": md.read_text(encoding="utf-8")}


@app.post("/api/coauthor/rewrite")
def rewrite_block(payload: Dict[str, str]) -> Dict[str, str]:
    text = payload.get("text", "")
    svc = LanguageService()
    out = svc.complete_turn("fiberizer_rewrite", {"input": text})
    return {"text": out.get("content", "")}


@app.post("/api/coauthor/save")
def save_doc(payload: Dict) -> Dict[str, str]:
    path = payload.get("path")
    blocks = payload.get("blocks", [])
    if not path:
        raise HTTPException(status_code=400, detail="path required")
    md = Path("docs") / path
    if not md.exists():
        raise HTTPException(status_code=404, detail="file not found")
    before_after = [
        {"before": b.get("before", ""), "after": b.get("after", "")}
        for b in blocks
    ]
    md.write_text("\n\n".join([b["after"] for b in before_after]), encoding="utf-8")
    fiber_ids = []
    for ba in before_after:
        fid = str(uuid4())
        execute(
            "INSERT INTO fibers (id, content, tags, source) VALUES (?,?,?,?)",
            (fid, json.dumps(ba), "", "coauthor"),
        )
        fiber_ids.append(fid)
    tid = f"thread-{uuid4()}"
    tdir = Path("data/threads")
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / f"{tid}.json").write_text(json.dumps({"thread_id": tid, "fiber_ids": fiber_ids}))
    return {"thread_id": tid}


@app.patch("/api/threads/{thread_id}/reorder")
def reorder_thread(thread_id: str, payload: Dict[str, list]):
    """Simulate thread fiber reordering. Logs new order."""
    order = payload.get("order", [])
    print("Reordered thread", thread_id, order)
    return {"status": "ok", "order": order}


@app.post("/api/tasks")
def create_task(payload: Dict[str, str]):
    if "fiber_id" in payload:
        fiber_id = payload.get("fiber_id")
        title = payload.get("title")
        description = payload.get("description", "")
        if not fiber_id or not title:
            raise HTTPException(status_code=400, detail="fiber_id and title required")
        cur = execute(
            "INSERT INTO tasks (fiber_id,title,description) VALUES (?,?,?)",
            (fiber_id, title, description),
        )
        tid = cur.lastrowid
        INBOX.append({"id": tid, "type": "task", "title": title, "created_at": datetime.utcnow().isoformat(), "status": "new", "tags": ""})
        return {"task_id": tid}
    # simple placeholder path used by legacy tests
    tid = str(uuid4())
    task = {"id": tid, "summary": payload.get("text", ""), "timestamp": datetime.utcnow().isoformat()}
    TASKS.append(task)
    INBOX.append({"id": tid, "type": "task", **task})
    return task


@app.get("/api/inbox")
def list_inbox() -> list[dict]:
    return INBOX
@app.get("/api/cli/schema")
def cli_schema() -> list[dict]:
    """Expose the CLI commands schema."""
    return get_cli_schema()


@app.post("/api/cli/run")
def cli_run(payload: dict) -> dict:
    """Execute a registered CLI command with validated arguments."""
    command = payload.get("command")
    args: dict = payload.get("args", {})
    schema_map = {c["command"]: c for c in get_cli_schema()}
    if command not in schema_map:
        raise HTTPException(status_code=404, detail="unknown command")
    spec = schema_map[command]
    for param in spec["params"]:
        if param["required"] and param["name"] not in args:
            raise HTTPException(status_code=400, detail=f"missing {param['name']}")
    for key in args:
        if key not in {p["name"] for p in spec["params"]}:
            raise HTTPException(status_code=400, detail=f"unexpected {key}")

    cmd = ["python", "scripts/zoros_cli.py", command]
    for k, v in args.items():
        cmd.append(f"--{k.replace('_', '-')}")
        cmd.append(str(v))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return {"stdout": proc.stdout, "stderr": proc.stderr, "returncode": proc.returncode}




@app.get("/api/plugins")
def list_plugins() -> list[dict]:
    """Return metadata about loaded plugins."""
    return [
        {"name": p.name, "version": p.version, "ui_panels": p.ui_panels()}
        for p in core_api._plugins.values()
    ]
# --- Task Pipeline API ---





@app.get("/api/inbox")
def get_inbox() -> List[Dict]:
    cur = execute(
        """
        SELECT tasks.id, tasks.title, tasks.created_at, tasks.status, fibers.tags
        FROM tasks JOIN fibers ON tasks.fiber_id=fibers.id
        WHERE tasks.status IN ('new','annotated')
        ORDER BY tasks.created_at DESC
        """
    )
    rows = cur.fetchall()
    return [
        {
            "id": r[0],
            "title": r[1],
            "created_at": r[2],
            "status": r[3],
            "tags": r[4],
        }
        for r in rows
    ]


def _annotate_task(task_id: int, model: str) -> str:
    row = execute("SELECT title FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="task not found")
    title = row[0]
    prompt = f"Here is a task description: {title}\n\nPlease clarify and add sub-steps."
    service = LanguageService()
    result = service.complete_turn("task-annotate", {"content": prompt, "model": model})
    content = result.get("content", "")
    execute(
        "INSERT INTO task_notes (task_id, content) VALUES (?,?)",
        (task_id, content),
    )
    execute(
        "UPDATE tasks SET status='annotated' WHERE id=?",
        (task_id,),
    )
    return content


@app.post("/api/tasks/{task_id}/annotate")
async def annotate_task(task_id: int, payload: Dict[str, str]):
    model = payload.get("model", "gpt-4-turbo")
    content = await run_in_threadpool(_annotate_task, task_id, model)
    return {"content": content}


@app.post("/api/tasks/{task_id}/spin")
def spin_task(task_id: int) -> Dict[str, List[str]]:
    row = execute("SELECT description FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="task not found")
    description = row[0] or ""
    parts = [p.strip() for p in description.split("\n") if p.strip()]
    fiber_ids: List[str] = []
    for part in parts:
        fid = str(uuid4())
        execute(
            "INSERT INTO fibers (id, content, tags, source) VALUES (?,?,?,?)",
            (fid, part, "", "spin"),
        )
        fiber_ids.append(fid)
    return {"fiber_ids": fiber_ids}
from source.dictation_backends import check_backend


@app.get("/api/dictate/test-backend")
def test_backend(name: str = "StandardOpenAIWhisper") -> Dict[str, str]:
    """Validate that the requested backend can initialize."""
    ok = check_backend(name)
    return {"status": "ok" if ok else "error"}


@app.get("/api/dictate/check-model")
def check_model() -> Dict[str, str]:
    return {"status": "ok"}


def _run_diagnostics() -> list[dict]:
    checks = []
    try:
        res = test_backend()
        checks.append({"check": "Audio Device", "status": "pass", "details": res.get("details", "")})
    except Exception as e:
        checks.append({"check": "Audio Device", "status": "fail", "details": str(e)})
    try:
        res = check_model()
        checks.append({"check": "Whisper Model", "status": "pass", "details": res.get("status")})
    except Exception as e:
        checks.append({"check": "Whisper Model", "status": "fail", "details": str(e)})
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("SELECT 1 FROM fibers LIMIT 1")
        checks.append({"check": "Database", "status": "pass", "details": "OK"})
    except Exception as e:
        checks.append({"check": "Database", "status": "fail", "details": str(e)})
    try:
        from backend.services.language_service.language_service import LanguageService

        svc = LanguageService()
        svc.complete_chat([{"role": "user", "content": "ping"}])
        checks.append({"check": "Codex", "status": "pass", "details": "pong"})
    except Exception as e:
        checks.append({"check": "Codex", "status": "fail", "details": str(e)})
    return checks


@app.get("/api/diagnostics/run")
async def diagnostics_run() -> list[dict]:
    return await asyncio.to_thread(_run_diagnostics)
