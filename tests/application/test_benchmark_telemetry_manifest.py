from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path


def test_run_determinism_harness_emits_telemetry_manifest_defaults(tmp_path: Path) -> None:
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
            "scripts/run_determinism_harness.py",
            "--task-bank",
            str(task_bank),
            "--runs",
            "1",
            "--runner-template",
            "python scripts/determinism_control_runner.py --task {task_file} --venue {venue} --flow {flow}",
            "--output",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "1.1.0"
    assert isinstance(payload["report_generated_at"], str)
    assert len(payload["test_runs"]) == 1
    telemetry = payload["test_runs"][0]["telemetry"]
    assert telemetry["init_latency"] is None
    assert telemetry["total_latency"] >= 0.0
    assert telemetry["peak_memory_rss"] == 0.0
    assert telemetry["adherence_score"] == 1.0


def test_run_determinism_harness_uses_runner_telemetry_when_present(tmp_path: Path) -> None:
    task_bank = tmp_path / "tasks.json"
    task_bank.write_text(
        json.dumps(
            [
                {
                    "id": "007",
                    "tier": 1,
                    "description": "Task 007",
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
    fake_runner = tmp_path / "fake_runner.py"
    fake_runner.write_text(
        "\n".join(
            [
                "import argparse",
                "import json",
                "parser = argparse.ArgumentParser()",
                "parser.add_argument('--task', required=True)",
                "parser.add_argument('--venue', default='x')",
                "parser.add_argument('--flow', default='y')",
                "parser.parse_args()",
                "print('noise line')",
                "print(json.dumps({",
                "  'telemetry': {",
                "    'init_latency': 0.12349,",
                "    'total_latency': 1.98765,",
                "    'peak_memory_rss': 256.44444,",
                "    'adherence_score': 0.66666",
                "  }",
                "}))",
                "raise SystemExit(0)",
                "",
            ]
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
            f"python {fake_runner} --task {{task_file}} --venue {{venue}} --flow {{flow}}",
            "--output",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    telemetry = payload["test_runs"][0]["telemetry"]
    assert telemetry == {
        "init_latency": 0.123,
        "total_latency": 1.988,
        "peak_memory_rss": 256.444,
        "adherence_score": 0.667,
    }


def test_constraint_validator_handles_ast_and_empty_rules() -> None:
    module_path = Path("scripts/live_card_benchmark_runner.py")
    spec = importlib.util.spec_from_file_location("live_card_benchmark_runner_test", module_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    validator = module.ConstraintValidator({"constraints": ["no imports", "use type hints"]})
    failed = validator.validate("import os\n\ndef run(x):\n    return x\n")
    assert failed["total_checks"] == 2
    assert failed["passed_checks"] == 0
    assert failed["adherence_score"] == 0.0

    passed = validator.validate("def run(x: int) -> int:\n    return x\n")
    assert passed["total_checks"] == 2
    assert passed["passed_checks"] == 2
    assert passed["adherence_score"] == 1.0

    no_rules = module.ConstraintValidator({})
    neutral = no_rules.validate("def run(x):\n    return x\n")
    assert neutral["total_checks"] == 0
    assert neutral["passed_checks"] == 0
    assert neutral["adherence_score"] == 1.0
