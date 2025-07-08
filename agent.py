#!/usr/bin/env python3
"""Utility agent for environment detection and docs scanning.

Example::

    $ python agent.py > report.md
"""
from __future__ import annotations
import os
import subprocess
import re
from pathlib import Path

ENV_DIR = Path("env")
DOCS_DIR = Path("docs")
PROGRESS: list[list[str]] = []


def log(step: str, status: str, notes: str = "", next_actions: str = "—") -> None:
    PROGRESS.append([step, status, notes or "—", next_actions or "—"])


def detect_environment() -> str:
    ENV_DIR.mkdir(exist_ok=True)
    if (ENV_DIR / "FULLSTACK_READY").exists():
        mode = "Full-Stack"
    elif (ENV_DIR / "BACKEND_READY").exists():
        mode = "Coder-Backend"
    elif (ENV_DIR / "FRONTEND_READY").exists():
        mode = "Frontend-Dev"
    else:
        mode = "Docs-Only"
    log("Detect environment", "✅ Completed", f"Mode: {mode}")
    return mode


def run_setup_script(mode: str) -> None:
    if mode == "Coder-Backend":
        step = "Run setup_coder_env.sh"
        script = Path("scripts/environment/setup_coder_env.sh")
    elif mode == "Frontend-Dev":
        step = "Run setup_frontend_env.sh"
        script = Path("scripts/environment/setup_frontend_env.sh")
    elif mode == "Full-Stack":
        step = "Run bootstrap_all.sh"
        script = Path("scripts/environment/bootstrap_all.sh")
    else:
        log("No setup script (Docs-Only)", "⚠️ Skipped")
        return
    if not script.exists():
        log(step, "❌ Failed", f"{script} not found", "Check repo")
        return
    log(step, "🔄 In Progress", "", "Awaiting script completion")
    result = subprocess.run(["bash", str(script)], capture_output=True, text=True)
    if result.returncode == 0:
        last_line = result.stdout.strip().splitlines()[-1] if result.stdout else ""
        log(step, "✅ Completed", last_line)
    else:
        log(step, "❌ Failed", result.stderr.strip(), "See output")


def scan_docs() -> list[str]:
    entries: list[str] = []
    if not DOCS_DIR.exists():
        return entries
    for path in sorted(DOCS_DIR.rglob("*.md")):
        rel = path.as_posix()
        desc = "No description"
        if path.name in {"architecture.md", "zoros_architecture.md"}:
            desc = "defines modules & workflows"
        elif re.fullmatch(r"tasks?_list.*\.md", path.name):
            desc = "master task registry"
        else:
            with path.open("r", encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    if line.strip().startswith("#"):
                        desc = line.lstrip("#").strip()
                        break
        entries.append(f"- {rel} ({desc})")
    return entries


def parse_task_info() -> tuple[str, str]:
    """Locate the current task entry in any tasks list and return name and gist."""
    candidates = list(DOCS_DIR.rglob("tasks_list.md")) + list(DOCS_DIR.rglob("task_list*.md"))
    if not candidates:
        log("Parse tasks list", "❌ Failed", "no tasks list found", "Check docs")
        return "Unknown", "Unknown"
    text = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in candidates)
    pattern = re.compile(r"\|\s*\*?\*?41\.(.*?)\|([^|]+)\|", re.DOTALL)
    m = pattern.search(text)
    if not m:
        log("Parse tasks list", "❌ Failed", "Task 041 entry not found", "Verify tasks list")
        return "Unknown", "Unknown"
    name = m.group(1).strip().strip('*').strip()
    gist = m.group(2).strip()
    log("Parse tasks list", "✅ Completed")
    return name, gist


def find_adjacent_specs() -> list[str]:
    specs_dir = DOCS_DIR / "specifications"
    results: list[str] = []
    if specs_dir.exists():
        for p in specs_dir.rglob("*.md"):
            content = p.read_text(encoding="utf-8", errors="ignore")
            if re.search(r"Task[- ]?041", content, re.IGNORECASE):
                results.append(f"- {p.as_posix()}")
    return results


def detect_mismatches() -> list[str]:
    """Run git diff on architecture doc and propose rename fixes."""
    arch_candidates = [DOCS_DIR / "architecture.md", DOCS_DIR / "zoros_architecture.md"]
    arch = next((p for p in arch_candidates if p.exists()), None)
    if not arch:
        log("Diff architecture.md", "⚠️ Skipped", "architecture doc not found", "Add architecture.md")
        return []

    result = subprocess.run([
        "git",
        "diff",
        "HEAD",
        "--",
        str(arch)
    ], capture_output=True, text=True)

    script_files = {p.name for p in Path("scripts").glob("*.sh")}
    improvements: list[str] = []
    diff_text = result.stdout
    for line in diff_text.splitlines():
        match = re.search(r"setup_[a-z0-9_]+\.sh", line)
        if match:
            script = match.group(0)
            if script not in script_files:
                alt = script.replace("backend", "coder")
                if alt in script_files:
                    improvements.append(
                        f"- Rename “{script}” → “{alt}” in {arch.name} to match script filename."
                    )
                else:
                    improvements.append(
                        f"- Update reference to “{script}” in {arch.name} (script not found)."
                    )

    log("Diff architecture.md", "✅ Completed")
    return improvements


def collect_todos() -> list[str]:
    todos: list[str] = []
    pattern = re.compile(r"(TODO|TBD):?\s*(.*)", re.IGNORECASE)
    skip_dirs = {"coder-env", "node_modules", "env", ".git"}
    for path in Path(".").rglob("*"):
        if any(part in skip_dirs for part in path.parts):
            continue
        if path.suffix in {".md", ".py", ".js", ".sh"} and path.is_file():
            with path.open("r", encoding="utf-8", errors="ignore") as fh:
                for i, line in enumerate(fh, 1):
                    m = pattern.search(line)
                    if m:
                        todos.append(f"{path.as_posix()}:{i} – \"{m.group(2).strip()}\"")
    log("Collect TODOs", "✅ Completed")
    return todos


def main() -> None:
    mode = detect_environment()
    run_setup_script(mode)
    log("Run deep docs scan", "🔄 In Progress", "", "Scanning docs")
    summary = scan_docs()
    log("Run deep docs scan", "✅ Completed")
    name, gist = parse_task_info()
    specs = find_adjacent_specs()
    improvements = detect_mismatches()
    todos = collect_todos()

    print(f"_Environment:_ **{mode}**\n")
    print("## Context Summary")
    for entry in summary:
        print(entry)
    print("\n### Current Task")
    print(f"- Name: {name}")
    print(f"- Gist: {gist}")
    if specs:
        print("\n### Adjacent Specs")
        for s in specs:
            print(s)
    print("\n## Progress")
    print("| Step | Status | Notes / Errors | Next Actions |")
    print("| --- | --- | --- | --- |")
    for step, status, notes, nxt in PROGRESS:
        print(f"| {step} | {status} | {notes} | {nxt} |")
    print("\n## Improvement Plan")
    if improvements:
        for imp in improvements:
            print(imp)
    else:
        print("- No mismatches detected.")
    print("\n## Follow-Up Tasks")
    if todos:
        for i, item in enumerate(todos, 1):
            print(f"{i}. {item}")
    else:
        print("No TODO or TBD items found.")
    print("\n```md\n<!--\nBest Practices:\n1. Reference `architecture.md` when adding new code files.\n2. Co-locate new frontend components under `src/intake-ui/`.\n3. For any new Docker/CI changes, note the corresponding line in `ci/pipeline.yml`.\n4. When in Coder mode, run `pytest --maxfail=1` before committing.\n-->\n```")


if __name__ == "__main__":
    main()
