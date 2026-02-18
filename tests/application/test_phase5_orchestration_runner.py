from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _run_runner(task_payload: dict, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    task_path = tmp_path / "task.json"
    task_path.write_text(json.dumps(task_payload, indent=2), encoding="utf-8")
    return subprocess.run(
        [
            "python",
            "scripts/orchestration_runner.py",
            "--task",
            str(task_path),
            "--venue",
            "standard",
            "--flow",
            "default",
            "--run-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_orchestration_runner_emits_phase5_artifacts_with_compliance_checks(tmp_path: Path) -> None:
    task = {
        "id": "061",
        "tier": 4,
        "description": "Ambiguous architecture task #061.",
        "instruction": "Clarify ambiguity and scaffold one endpoint with rationale.",
        "acceptance_contract": {
            "mode": "system",
            "required_artifacts": ["run.log", "report.json"],
            "pass_conditions": [
                "Implementation completes without crash",
                "Required artifacts are produced",
                "Task-level checks pass",
            ],
            "determinism_profile": "bounded",
        },
    }
    result = _run_runner(task, tmp_path)
    assert result.returncode == 0

    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == "pass"
    assert report["compliance_checks"]["reviewer_compliance"]["status"] == "pass"
    assert report["compliance_checks"]["architecture_compliance"]["status"] == "pass"
    assert (tmp_path / "run.log").exists()


def test_orchestration_runner_emits_convergence_metrics_for_tier6(tmp_path: Path) -> None:
    task = {
        "id": "096",
        "tier": 6,
        "description": "Orchestration stress and convergence task #096.",
        "instruction": "Run convergence loops and publish convergence evidence.",
        "acceptance_contract": {
            "mode": "system",
            "required_artifacts": ["run.log", "report.json", "convergence_metrics.json"],
            "pass_conditions": [
                "Implementation completes without crash",
                "Required artifacts are produced",
            ],
            "determinism_profile": "convergence",
            "convergence_metrics": {
                "attempts_to_pass": "Iterations until checks pass.",
                "drift_rate": "Variance across runs.",
            },
        },
    }
    result = _run_runner(task, tmp_path)
    assert result.returncode == 0

    convergence = json.loads((tmp_path / "convergence_metrics.json").read_text(encoding="utf-8"))
    assert convergence["attempts_to_pass"]["value"] == 1
    assert convergence["drift_rate"]["value"] == 0.0
