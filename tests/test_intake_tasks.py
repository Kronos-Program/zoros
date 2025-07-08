import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "intake_tasks.py"


def run(script_args, root):
    env = os.environ.copy()
    env["REPO_ROOT"] = str(root)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *script_args],
        capture_output=True,
        text=True,
        env=env,
        cwd=root,
    )


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_dry_run(tmp_path: Path):
    planning = tmp_path / "docs" / "task_planning.md"
    write_file(
        planning,
        """Task ID: TASK-100\nTask Name: Test One\nGist: G1\n\nTask ID: TASK-101\nTask Name: Test Two\nGist: G2\n""",
    )
    registry = tmp_path / "docs" / "tasks_list.md"
    write_file(registry, "# Header\n")

    result = run(["--dry-run"], tmp_path)
    assert result.returncode == 0
    assert "Added TASK-100" in result.stdout
    assert registry.read_text() == "# Header\n"


def test_update_and_idempotent(tmp_path: Path):
    planning = tmp_path / "docs" / "task_planning.md"
    write_file(
        planning,
        """Task ID: TASK-200\nTask Name: New Name\nGist: Gnew\n\nTask ID: TASK-201\nTask Name: Another\nGist: G2\n""",
    )
    registry = tmp_path / "docs" / "tasks_list.md"
    initial = "\n".join(
        [
            "# Header",
            "",
            "### Task ID: TASK-200",
            "**Name:** Old Name",
            "**Gist:** Gold",
            "**Related Modules:** _TBD_",
            "**Status:** _New_",
            "",
        ]
    )
    write_file(registry, initial)

    result = run([], tmp_path)
    assert result.returncode == 0
    text = registry.read_text()
    assert "New Name" in text
    assert "TASK-201" in text

    before = text
    result2 = run([], tmp_path)
    assert result2.returncode == 0
    assert registry.read_text() == before
