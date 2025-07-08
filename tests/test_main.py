import subprocess
import os
import time
import trace
from pathlib import Path
import contextlib

from main import main


def test_main_entrypoint_runs(monkeypatch):
    """Execute the main script while capturing a trace log."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"main_run_{timestamp}.log"

    def fake_call(cmd):
        # avoid launching the heavy whisper subprocess
        return 0

    monkeypatch.setattr(subprocess, "call", fake_call)
    monkeypatch.setattr(os.path, "exists", lambda p: True)
    tracer = trace.Trace(trace=True, count=False)
    with log_path.open("w", encoding="utf-8") as fh:
        with contextlib.redirect_stdout(fh):
            exit_code = tracer.runfunc(main)
    assert exit_code == 0
    assert log_path.exists() and log_path.stat().st_size > 0

    report_path = Path("docs") / "main_run_report.md"
    lines = log_path.read_text().splitlines()
    calls = [l for l in lines if l.startswith(" --- modulename")][:10]
    with report_path.open("w", encoding="utf-8") as fh:
        fh.write("# Main Script Execution Report\n\n")
        fh.write("## Sample Trace\n\n")
        fh.write("```\n" + "\n".join(calls) + "\n```\n")
    assert report_path.exists()
