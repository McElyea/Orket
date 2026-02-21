from __future__ import annotations

import importlib.util
import json
import os
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

    assert payload["schema_version"] == "1.1.3"
    assert isinstance(payload["report_generated_at"], str)
    assert len(payload["test_runs"]) == 1
    telemetry = payload["test_runs"][0]["telemetry"]
    assert telemetry["init_latency"] is None
    assert telemetry["total_latency"] >= 0.0
    assert telemetry["peak_memory_rss"] == 0.0
    assert telemetry["adherence_score"] == 1.0
    assert telemetry["internal_model_seconds"] is None
    assert telemetry["orchestration_overhead_ratio"] is None
    assert telemetry["run_quality_status"] == "POLLUTED"
    assert telemetry["run_quality_reasons"] == ["MISSING_EXPERIMENTAL_CONTROLS", "MISSING_TOKEN_TIMINGS"]
    assert telemetry["system_load_start"] == {}
    assert telemetry["system_load_end"] == {}
    assert telemetry["experimental_controls"] == {
        "seed": None,
        "threads": None,
        "affinity_policy": "",
        "warmup_steps": None,
    }
    assert telemetry["token_metrics_status"] == "TOKEN_AND_TIMING_UNAVAILABLE"
    assert telemetry["token_metrics"] == {
        "status": "TOKEN_AND_TIMING_UNAVAILABLE",
        "counts": {
            "prompt_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
        },
        "latencies": {
            "prefill_seconds": None,
            "decode_seconds": None,
            "total_turn_seconds": telemetry["total_latency"],
        },
        "throughput": {
            "prompt_tokens_per_second": None,
            "generation_tokens_per_second": None,
        },
        "audit": {
            "raw_usage": {},
            "raw_timings": {},
        },
    }
    assert telemetry["vibe_metrics"] == {
        "latency_variance": None,
        "code_density": 0.0,
        "gen_retries": 0,
        "vibe_delta": None,
        "vibe_delta_status": "NO_BASELINE",
    }


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
                "    'adherence_score': 0.66666,",
                "    'token_metrics_status': 'OK',",
                "    'token_metrics': {",
                "      'status': 'OK',",
                "      'counts': {",
                "        'prompt_tokens': 512,",
                "        'output_tokens': 128,",
                "        'total_tokens': 640",
                "      },",
                "      'latencies': {",
                "        'prefill_seconds': 0.8504,",
                "        'decode_seconds': 5.121,",
                "        'total_turn_seconds': 6.1",
                "      },",
                "      'throughput': {",
                "        'prompt_tokens_per_second': 602.35294,",
                "        'generation_tokens_per_second': 24.99512",
                "      },",
                "      'audit': {",
                "        'raw_usage': {'prompt_tokens': 512, 'completion_tokens': 128, 'total_tokens': 640},",
                "        'raw_timings': {'prompt_ms': 850.4, 'predicted_ms': 5121.0}",
                "      }",
                "    },",
                "    'vibe_metrics': {",
                "      'latency_variance': 12.34567,",
                "      'code_density': 0.75491,",
                "      'gen_retries': 2,",
                "      'vibe_delta': 0.33339,",
                "      'vibe_delta_status': 'OK'",
                "    }",
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
        "internal_model_seconds": None,
        "orchestration_overhead_ratio": None,
        "run_quality_status": "POLLUTED",
        "run_quality_reasons": [],
        "system_load_start": {},
        "system_load_end": {},
        "experimental_controls": {
            "seed": None,
            "threads": None,
            "affinity_policy": "",
            "warmup_steps": None,
        },
        "token_metrics_status": "OK",
        "token_metrics": {
            "status": "OK",
            "counts": {
                "prompt_tokens": 512,
                "output_tokens": 128,
                "total_tokens": 640,
            },
            "latencies": {
                "prefill_seconds": 0.85,
                "decode_seconds": 5.121,
                "total_turn_seconds": 6.1,
            },
            "throughput": {
                "prompt_tokens_per_second": 602.35,
                "generation_tokens_per_second": 25.0,
            },
            "audit": {
                "raw_usage": {"prompt_tokens": 512, "completion_tokens": 128, "total_tokens": 640},
                "raw_timings": {"prompt_ms": 850.4, "predicted_ms": 5121.0},
            },
        },
        "vibe_metrics": {
            "latency_variance": 12.346,
            "code_density": 0.755,
            "gen_retries": 2,
            "vibe_delta": 0.333,
            "vibe_delta_status": "OK",
        },
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


def test_baseline_selection_and_vibe_delta(tmp_path: Path) -> None:
    module_path = Path("scripts/live_card_benchmark_runner.py")
    spec = importlib.util.spec_from_file_location("live_card_benchmark_runner_test_baseline", module_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    cwd = Path.cwd()
    try:
        os.chdir(tmp_path)
        baseline_dir = tmp_path / ".orket" / "durable" / "diagnostics" / "baselines"
        baseline_dir.mkdir(parents=True, exist_ok=True)
        baseline_path = baseline_dir / "001.json"
        baseline_path.write_text(
            json.dumps(
                {
                    "test_id": "001",
                    "history": [
                        {
                            "baseline_metadata": {
                                "test_run_id": "old-ref",
                                "hardware_fingerprint": "linux-1|cpu|8c|32gb|none",
                                "task_revision": "v1",
                                "created_at": "2026-01-01T00:00:00Z",
                            },
                            "gold_telemetry": {"adherence_score": 1.0, "peak_memory_rss": 4096.0, "total_latency": 10.0},
                        },
                        {
                            "baseline_metadata": {
                                "test_run_id": "new-ref",
                                "hardware_fingerprint": "linux-1|cpu|8c|32gb|none",
                                "task_revision": "v1",
                                "created_at": "2026-02-01T00:00:00Z",
                            },
                            "gold_telemetry": {"adherence_score": 1.0, "peak_memory_rss": 3072.0, "total_latency": 8.0},
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        selected, status = module._select_baseline_record(
            test_id="001",
            hardware_fingerprint="linux-1|cpu|8c|32gb|none",
            task_revision="v1",
        )
        assert status == "OK"
        assert selected["baseline_metadata"]["test_run_id"] == "new-ref"
        delta = module._compute_vibe_delta(
            {"adherence_score": 0.9, "peak_memory_rss": 2048.0},
            selected["gold_telemetry"],
        )
        assert delta == 0.1
    finally:
        os.chdir(cwd)
