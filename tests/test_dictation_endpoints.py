import os
from fastapi.testclient import TestClient

from backend.app import app
from backend.db import init_db

client = TestClient(app)


def setup_module(module):
    os.environ["DATABASE_URL"] = f"sqlite:///{module.__name__}.db"
    init_db()


def test_partial_endpoint():
    resp = client.post("/api/dictate/partial", data=b"audio")
    assert resp.status_code == 200
    assert "text" in resp.json()


def test_full_endpoint_persists():
    resp = client.post("/api/dictate/full", data=b"audio")
    data = resp.json()
    assert resp.status_code == 200
    assert "fiber_id" in data

    # confirm fiber exists
    inbox = client.get("/api/inbox").json()
    assert any(it.get("id") == data["fiber_id"] for it in inbox)


def test_backend_check():
    resp = client.get("/api/dictate/test-backend", params={"name": "StandardOpenAIWhisper"})
    assert resp.status_code == 200
    assert resp.json()["status"] in {"ok", "error"}
