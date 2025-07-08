import os

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.db import init_db


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/test.db"
    init_db()
    yield


def test_create_and_inbox():
    client = TestClient(app)
    f_resp = client.post("/api/fibers", json={"content": "note", "source": "test"})
    fid = f_resp.json()["fiber_id"]
    t_resp = client.post(
        "/api/tasks",
        json={"fiber_id": fid, "title": "T1", "description": "line1\nline2"},
    )
    tid = t_resp.json()["task_id"]

    inbox = client.get("/api/inbox").json()
    ids = [row["id"] for row in inbox]
    assert tid in ids


def test_annotation_and_spin(monkeypatch):
    client = TestClient(app)
    fid = client.post("/api/fibers", json={"content": "n", "source": "test"}).json()[
        "fiber_id"
    ]
    tid = client.post(
        "/api/tasks",
        json={"fiber_id": fid, "title": "A", "description": "step"},
    ).json()["task_id"]

    # mock LanguageService.complete_turn
    called = {}

    def fake_complete(self, *a, **k):
        called["yes"] = True
        return {"content": "annotated"}

    monkeypatch.setattr("backend.app.LanguageService.__init__", lambda self: None)
    monkeypatch.setattr("backend.app.LanguageService.complete_turn", fake_complete)

    ann = client.post(f"/api/tasks/{tid}/annotate", json={"model": "gpt-4-turbo"})
    assert ann.json()["content"] == "annotated"

    spin = client.post(f"/api/tasks/{tid}/spin").json()
    assert len(spin["fiber_ids"]) == 1
    assert called["yes"]
