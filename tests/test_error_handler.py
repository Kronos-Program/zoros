import sqlite3
from fastapi.testclient import TestClient
from unittest import mock

def create_app():
    from importlib import reload
    import backend.app as backend_app
    reload(backend_app)
    @backend_app.app.get("/api/boom")
    def boom():
        raise RuntimeError("boom")
    return backend_app.app


def test_error_handler_creates_fiber(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    app = create_app()
    from backend.error_handler import DB_PATH

    patcher = mock.patch("source.language_service.LanguageService")
    svc_cls = patcher.start()
    svc = svc_cls.return_value
    svc.complete_turn.return_value = {"content": "fix it"}
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/boom")
    assert resp.status_code == 500
    import time
    time.sleep(0.3)
    patcher.stop()

    db = DB_PATH
    with sqlite3.connect(db) as conn:
        cur = conn.execute("SELECT COUNT(*) FROM fibers")
        assert cur.fetchone()[0] >= 1






