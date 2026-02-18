from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_phase4_runner_executes_001_to_060_and_writes_report(tmp_path: Path) -> None:
    raw_out = tmp_path / "phase4_raw.json"
    scored_out = tmp_path / "phase4_scored.json"
    result = subprocess.run(
        [
            "python",
            "scripts/run_phase4_benchmark.py",
            "--runs",
            "1",
            "--runner-template",
            "python scripts/determinism_control_runner.py --task {task_file} --venue {venue} --flow {flow}",
            "--raw-out",
            str(raw_out),
            "--scored-out",
            str(scored_out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    raw = json.loads(raw_out.read_text(encoding="utf-8"))
    assert raw["task_id_min"] == 1
    assert raw["task_id_max"] == 60
    assert raw["total_tasks"] == 60
