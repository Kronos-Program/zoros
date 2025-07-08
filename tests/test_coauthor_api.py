import os
import json
from fastapi.testclient import TestClient
from backend.app import app
from backend.db import init_db, DB_PATH

client = TestClient(app)


def _setup(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"
    monkeypatch.setattr('backend.db.DB_PATH', db_file, raising=False)
    init_db()
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "sample.md").write_text("# T\n\n## A\ntext")
    os.chdir(tmp_path)


def test_coauthor_endpoints(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)

    resp = client.get("/api/coauthor/docs")
    assert resp.status_code == 200
    assert "sample.md" in resp.json()

    resp = client.get("/api/coauthor/doc", params={"path": "sample.md"})
    assert resp.status_code == 200
    assert resp.json()["content"].startswith("# T")

    monkeypatch.setattr("backend.app.LanguageService.__init__", lambda self: None)
    monkeypatch.setattr("backend.app.LanguageService.complete_turn", lambda self, *a, **k: {"content": "edit"})
    r = client.post("/api/coauthor/rewrite", json={"text": "x"})
    assert r.json()["text"] == "edit"

    blocks = [{"before": "## A\ntext", "after": "## A\nchanged"}]
    res = client.post("/api/coauthor/save", json={"path": "sample.md", "blocks": blocks})
    assert res.status_code == 200
    tid = res.json()["thread_id"]
    thread = json.loads((tmp_path / "data" / "threads" / f"{tid}.json").read_text())
    assert thread["fiber_ids"]

