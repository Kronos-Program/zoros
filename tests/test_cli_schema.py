from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)


def test_schema_lists_echo():
    resp = client.get('/api/cli/schema')
    assert resp.status_code == 200
    commands = [c['command'] for c in resp.json()]
    assert 'echo-test' in commands


def test_schema_lists_wizard():
    resp = client.get('/api/cli/schema')
    assert resp.status_code == 200
    commands = [c['command'] for c in resp.json()]
    assert 'wizard' in commands


def test_schema_lists_lint_fiber():
    resp = client.get('/api/cli/schema')
    assert resp.status_code == 200
    commands = [c['command'] for c in resp.json()]
    assert 'lint-fiber' in commands


def test_cli_run_echo():
    resp = client.post('/api/cli/run', json={'command': 'echo-test', 'args': {'text': 'hi'}})
    assert resp.status_code == 200
    data = resp.json()
    assert data['returncode'] == 0
    assert 'hi' in data['stdout']


def test_cli_run_invalid():
    resp = client.post('/api/cli/run', json={'command': 'echo-test', 'args': {'wrong': 1}})
    assert resp.status_code == 400


def test_cli_run_lint_fiber(tmp_path):
    import yaml
    data = {'id': '1', 'title': 'demo', 'status': 'new'}
    path = tmp_path / 'fiber.yml'
    path.write_text(yaml.safe_dump(data))
    resp = client.post(
        '/api/cli/run',
        json={'command': 'lint-fiber', 'args': {'path': str(path)}},
    )
    assert resp.status_code == 200
    out = resp.json()
    assert out['returncode'] == 0
