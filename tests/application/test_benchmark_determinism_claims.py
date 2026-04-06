from __future__ import annotations

# Layer: contract
import json
import subprocess
from pathlib import Path


def test_run_determinism_harness_single_run_is_not_claimed_deterministic(tmp_path: Path) -> None:
    """Layer: contract. Verifies a single successful run is reported as unproven, not deterministic."""
    task_bank = tmp_path / "tasks.json"
    task_bank.write_text(
        json.dumps(
            [
                {
                    "id": "001",
                    "tier": 1,
                    "description": "Task 001",
                    "acceptance_contract": {
                        "mode": "function",
                        "required_artifacts": [],
                        "pass_conditions": ["ok"],
                        "determinism_profile": "strict",
                    },
                }
            ],
            indent=2,
        ),
        encoding="utf-8",
    )
    out = tmp_path / "report.json"
    result = subprocess.run(
        [
            "python",
            "scripts/benchmarks/run_determinism_harness.py",
            "--task-bank",
            str(task_bank),
            "--runs",
            "1",
            "--runner-template",
            "python scripts/benchmarks/determinism_control_runner.py --task {task_file} --venue {venue} --flow {flow}",
            "--output",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    detail = payload["details"]["001"]

    assert detail["deterministic"] is None
    assert detail["determinism_note"] == "single_run_insufficient"
