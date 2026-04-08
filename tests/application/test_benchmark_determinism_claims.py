from __future__ import annotations

# Layer: contract
import json
import subprocess
import sys
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
    assert payload["determinism_rate_valid"] is False
    assert payload["warnings"] == ["WARNING: runs_per_task=1 cannot prove determinism"]


def test_run_determinism_harness_hashes_stdout_only_when_stderr_differs(tmp_path: Path) -> None:
    """Layer: contract. Verifies stderr-only runner noise remains debug evidence, not hash input."""
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
    runner = tmp_path / "stderr_noise_runner.py"
    runner.write_text(
        "from __future__ import annotations\n"
        "import json\n"
        "import sys\n"
        "task_path = sys.argv[sys.argv.index('--task') + 1]\n"
        "sys.stderr.write(f'stderr-only-noise:{task_path}\\n')\n"
        "print(json.dumps({'result': 'ok'}))\n",
        encoding="utf-8",
    )
    out = tmp_path / "report.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/benchmarks/run_determinism_harness.py",
            "--task-bank",
            str(task_bank),
            "--runs",
            "2",
            "--runner-template",
            f"{sys.executable} {runner} --task {{task_file}}",
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
    hashes = {run["hash"] for run in detail["runs"]}

    assert payload["determinism_rate_valid"] is True
    assert detail["deterministic"] is True
    assert len(hashes) == 1
    assert "--- stderr ---" in detail["runs"][0]["normalized_output_preview"]
