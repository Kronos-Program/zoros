import yaml
from zoros.utils.lint_fiber import lint_fiber


def test_lint_ok(tmp_path):
    data = {"id": "1", "title": "demo", "status": "new"}
    path = tmp_path / "fiber.yml"
    path.write_text(yaml.safe_dump(data))
    ok, messages = lint_fiber(path)
    assert ok
    assert all('Missing' not in m for m in messages)


def test_lint_fix(tmp_path):
    data = {"id": "1", "title": "demo"}
    path = tmp_path / "fiber.yml"
    path.write_text(yaml.safe_dump(data))
    ok, messages = lint_fiber(path, fix=True)
    assert ok
    assert "Missing required field 'status'" in messages[0]
    loaded = yaml.safe_load(path.read_text())
    assert loaded["status"] == "unchecked"
