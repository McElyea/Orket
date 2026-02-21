from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_run_context_sweep_generates_per_context_summaries_and_ceiling(tmp_path: Path) -> None:
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
    fake_runner = tmp_path / "fake_context_runner.py"
    fake_runner.write_text(
        "\n".join(
            [
                "import argparse",
                "import json",
                "import os",
                "p = argparse.ArgumentParser()",
                "p.add_argument('--task', required=True)",
                "p.add_argument('--venue', default='x')",
                "p.add_argument('--flow', default='y')",
                "p.parse_args()",
                "ctx = int(os.environ.get('ORKET_CONTEXT_WINDOW', '0'))",
                "adherence = 1.0 if ctx <= 8192 else 0.8",
                "decode_tps = 30.0 if ctx <= 8192 else 15.0",
                "ttft = 100.0 if ctx <= 8192 else 400.0",
                "print(json.dumps({",
                "  'telemetry': {",
                "    'init_latency': None,",
                "    'total_latency': 1.0,",
                "    'peak_memory_rss': 100.0,",
                "    'adherence_score': adherence,",
                "    'token_metrics_status': 'OK',",
                "    'run_quality_status': 'CLEAN',",
                "    'run_quality_reasons': []",
                "  },",
                "  'hardware_sidecar': {",
                "    'ttft_ms': ttft,",
                "    'decode_tps': decode_tps,",
                "    'sidecar_parse_status': 'OK'",
                "  }",
                "}))",
                "raise SystemExit(0)",
                "",
            ]
        ),
        encoding="utf-8",
    )

    out_dir = tmp_path / "context_sweep"
    result = subprocess.run(
        [
            "python",
            "scripts/run_context_sweep.py",
            "--contexts",
            "4096,8192,16384",
            "--model-id",
            "qwen-coder",
            "--quant-tags",
            "Q8_0",
            "--task-bank",
            str(task_bank),
            "--runner-template",
            f"python {fake_runner} --task {{task_file}} --venue {{venue}} --flow {{flow}}",
            "--task-limit",
            "1",
            "--adherence-min",
            "0.95",
            "--execution-lane",
            "lab",
            "--vram-profile",
            "safe",
            "--provenance-ref",
            "run:test",
            "--out-dir",
            str(out_dir),
            "--context-ceiling-out",
            "ceiling.json",
            "--storage-mode",
            "ephemeral",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "OK"
    assert ".storage" in payload["storage_root"]
    assert len(payload["summary_paths"]) == 3

    ceiling = json.loads((out_dir / "ceiling.json").read_text(encoding="utf-8"))
    assert ceiling["safe_context_ceiling"] == 8192
    assert ceiling["execution_lane"] == "lab"
    assert ceiling["vram_profile"] == "safe"
    assert ceiling["provenance"]["ref"] == "run:test"


def test_run_context_sweep_can_resolve_context_profile(tmp_path: Path) -> None:
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
    profiles = tmp_path / "profiles.json"
    profiles.write_text(
        json.dumps(
            {
                "profiles": {
                    "safe": {
                        "contexts": [1024, 2048],
                        "adherence_min": 0.95,
                        "ttft_ceiling_ms": 0.0,
                        "decode_floor_tps": 0.0,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    fake_runner = tmp_path / "fake_context_runner.py"
    fake_runner.write_text(
        "\n".join(
            [
                "import argparse",
                "import json",
                "import os",
                "p = argparse.ArgumentParser()",
                "p.add_argument('--task', required=True)",
                "p.add_argument('--venue', default='x')",
                "p.add_argument('--flow', default='y')",
                "p.parse_args()",
                "ctx = int(os.environ.get('ORKET_CONTEXT_WINDOW', '0'))",
                "adherence = 1.0 if ctx <= 2048 else 0.8",
                "print(json.dumps({'telemetry': {'init_latency': None, 'total_latency': 1.0, 'peak_memory_rss': 100.0, 'adherence_score': adherence, 'token_metrics_status': 'OK', 'run_quality_status': 'CLEAN', 'run_quality_reasons': []}}))",
                "raise SystemExit(0)",
                "",
            ]
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "context_sweep"
    result = subprocess.run(
        [
            "python",
            "scripts/run_context_sweep.py",
            "--context-profile",
            "safe",
            "--context-profiles-config",
            str(profiles),
            "--model-id",
            "qwen-coder",
            "--quant-tags",
            "Q8_0",
            "--task-bank",
            str(task_bank),
            "--runner-template",
            f"python {fake_runner} --task {{task_file}} --venue {{venue}} --flow {{flow}}",
            "--task-limit",
            "1",
            "--out-dir",
            str(out_dir),
            "--storage-mode",
            "ephemeral",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(result.stdout)
    assert payload["context_profile"] == "safe"
    assert ".storage" in payload["storage_root"]
    assert payload["contexts"] == [1024, 2048]
    ceiling = json.loads((out_dir / "context_ceiling.json").read_text(encoding="utf-8"))
    assert ceiling["safe_context_ceiling"] == 2048


def test_run_context_sweep_can_resolve_matrix_config_defaults(tmp_path: Path) -> None:
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
    fake_runner = tmp_path / "fake_context_runner.py"
    fake_runner.write_text(
        "\n".join(
            [
                "import argparse",
                "import json",
                "p = argparse.ArgumentParser()",
                "p.add_argument('--task', required=True)",
                "p.add_argument('--venue', default='x')",
                "p.add_argument('--flow', default='y')",
                "p.parse_args()",
                "print(json.dumps({'telemetry': {'init_latency': None, 'total_latency': 1.0, 'peak_memory_rss': 100.0, 'adherence_score': 1.0, 'token_metrics_status': 'OK', 'run_quality_status': 'CLEAN', 'run_quality_reasons': []}}))",
                "raise SystemExit(0)",
                "",
            ]
        ),
        encoding="utf-8",
    )
    matrix = tmp_path / "matrix.json"
    matrix.write_text(
        json.dumps(
            {
                "models": ["resolved-model"],
                "quants": ["Q6_K"],
                "task_bank": str(task_bank).replace("\\", "/"),
                "runs_per_quant": 1,
                "runner_template": f"python {fake_runner} --task {{task_file}} --venue {{venue}} --flow {{flow}}",
            }
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "context_sweep"
    result = subprocess.run(
        [
            "python",
            "scripts/run_context_sweep.py",
            "--contexts",
            "1024",
            "--matrix-config",
            str(matrix),
            "--model-id",
            "",
            "--quant-tags",
            "",
            "--out-dir",
            str(out_dir),
            "--storage-mode",
            "ephemeral",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    summary_path = out_dir / "context_1024_summary.json"
    summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary_payload["sessions"][0]["model_id"] == "resolved-model"
