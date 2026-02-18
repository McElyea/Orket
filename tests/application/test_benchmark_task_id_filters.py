from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_run_determinism_harness_filters_task_id_range(tmp_path: Path) -> None:
    task_bank = tmp_path / "tasks.json"
    task_bank.write_text(
        json.dumps(
            [
                {"id": "060", "tier": 3, "description": "Task 060", "acceptance_contract": {"mode": "system", "required_artifacts": [], "pass_conditions": ["ok"], "determinism_profile": "bounded"}},
                {"id": "061", "tier": 4, "description": "Task 061", "acceptance_contract": {"mode": "system", "required_artifacts": [], "pass_conditions": ["ok"], "determinism_profile": "bounded"}},
                {"id": "100", "tier": 6, "description": "Task 100", "acceptance_contract": {"mode": "system", "required_artifacts": [], "pass_conditions": ["ok"], "determinism_profile": "convergence"}},
            ],
            indent=2,
        ),
        encoding="utf-8",
    )
    out = tmp_path / "report.json"
    result = subprocess.run(
        [
            "python",
            "scripts/run_determinism_harness.py",
            "--task-bank",
            str(task_bank),
            "--runs",
            "1",
            "--runner-template",
            "python scripts/determinism_control_runner.py --task {task_file} --venue {venue} --flow {flow}",
            "--task-id-min",
            "61",
            "--task-id-max",
            "100",
            "--output",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["total_tasks"] == 2
    assert set(payload["details"].keys()) == {"061", "100"}
