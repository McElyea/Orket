from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_run_quant_sweep_injects_runtime_env_from_matrix_config(tmp_path: Path) -> None:
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

    fake_runner = tmp_path / "fake_runtime_env_runner.py"
    fake_runner.write_text(
        "\n".join(
            [
                "import argparse",
                "import json",
                "import os",
                "import sys",
                "p = argparse.ArgumentParser()",
                "p.add_argument('--task', required=True)",
                "p.add_argument('--runtime-target', default='x')",
                "p.add_argument('--execution-mode', default='y')",
                "p.add_argument('--run-dir', default='.')",
                "p.parse_args()",
                "if os.environ.get('ORKET_LLM_PROVIDER') != 'lmstudio':",
                "    sys.stderr.write('missing ORKET_LLM_PROVIDER=lmstudio')",
                "    raise SystemExit(3)",
                "if os.environ.get('ORKET_LLM_OPENAI_BASE_URL') != 'http://127.0.0.1:1234/v1':",
                "    sys.stderr.write('missing ORKET_LLM_OPENAI_BASE_URL')",
                "    raise SystemExit(4)",
                "if os.environ.get('ORKET_MODEL_CODER') != 'qwen3.5-0.8b':",
                "    sys.stderr.write('missing ORKET_MODEL_CODER')",
                "    raise SystemExit(5)",
                "print(json.dumps({'telemetry': {'init_latency': None, 'total_latency': 1.0, 'peak_memory_rss': 100.0, 'adherence_score': 1.0, 'token_metrics_status': 'OK', 'run_quality_status': 'CLEAN', 'run_quality_reasons': []}}))",
                "raise SystemExit(0)",
                "",
            ]
        ),
        encoding="utf-8",
    )

    matrix_cfg = tmp_path / "matrix.json"
    matrix_cfg.write_text(
        json.dumps(
            {
                "models": ["qwen3.5-0.8b"],
                "quants": ["Q8_0"],
                "task_bank": str(task_bank).replace("\\", "/"),
                "runs_per_quant": 1,
                "task_limit": 1,
                "canary_runs": 0,
                "runner_template": (
                    f"python {fake_runner} "
                    "--task {task_file} --runtime-target {runtime_target} --execution-mode {execution_mode} --run-dir {run_dir}"
                ),
                "runtime_env": {
                    "ORKET_LLM_PROVIDER": "lmstudio",
                    "ORKET_LLM_OPENAI_BASE_URL": "http://127.0.0.1:1234/v1",
                },
                "sanitize_model_cache": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    summary_out = tmp_path / "sweep_summary.json"
    result = subprocess.run(
        [
            "python",
            "scripts/MidTier/run_quant_sweep.py",
            "--model-id",
            "placeholder",
            "--quant-tags",
            "Q4_K_M",
            "--matrix-config",
            str(matrix_cfg),
            "--summary-out",
            str(summary_out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    summary = json.loads(summary_out.read_text(encoding="utf-8"))
    assert summary["matrix"]["runtime_env"]["ORKET_LLM_PROVIDER"] == "lmstudio"
    assert summary["matrix"]["runtime_env"]["ORKET_LLM_OPENAI_BASE_URL"] == "http://127.0.0.1:1234/v1"
