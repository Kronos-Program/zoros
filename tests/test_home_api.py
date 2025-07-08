from fastapi.testclient import TestClient
from backend import app

client = TestClient(app.app)


def test_dictate_cycle():
    resp = client.post('/api/dictate/start')
    assert resp.status_code == 200
    resp = client.post('/api/dictate/stop')
    assert resp.status_code == 200
    assert 'text' in resp.json()


def test_task_and_inbox():
    client.post('/api/tasks', json={'text': 'hello'})
    client.post('/api/fibers', json={'text': 'world'})
    resp = client.get('/api/inbox')
    assert resp.status_code == 200
    data = resp.json()
    assert any(it['type'] == 'task' for it in data)
    assert any(it['type'] == 'fiber' for it in data)
