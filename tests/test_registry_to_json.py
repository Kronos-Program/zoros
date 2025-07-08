from pathlib import Path
from scripts import registry_to_json

def test_parse_tasks():
    tasks = registry_to_json.parse_tasks(Path('docs/tasks_list.md'))
    assert isinstance(tasks, list)
    assert any(t['id'] for t in tasks)

def test_update_task_status(tmp_path):
    md = tmp_path / 'tasks.md'
    md.write_text('## TASK-001\nExample Task\n### Related Modules\n- `foo`\n')
    task = registry_to_json.update_task_status('TASK-001', 'Completed', md)
    assert task['status'] == 'Completed'
    text = md.read_text()
    assert 'Status: Completed' in text

