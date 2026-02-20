from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_run_quant_sweep_builds_summary_and_frontier(tmp_path: Path) -> None:
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

    fake_runner = tmp_path / "fake_quant_runner.py"
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
                "quant = os.environ.get('ORKET_QUANT_TAG', 'unknown')",
                "if quant == 'Q8_0':",
                "    adherence, mem = 1.0, 3000.0",
                "elif quant == 'Q6_K':",
                "    adherence, mem = 0.98, 2300.0",
                "else:",
                "    adherence, mem = 0.75, 1600.0",
                "print(json.dumps({",
                "  'telemetry': {",
                "    'init_latency': None,",
                "    'total_latency': 1.0,",
                "    'peak_memory_rss': mem,",
                "    'adherence_score': adherence,",
                "    'vibe_metrics': {",
                "      'latency_variance': None,",
                "      'code_density': 0.9,",
                "      'gen_retries': 0,",
                "      'vibe_delta': None,",
                "      'vibe_delta_status': 'NO_BASELINE'",
                "    }",
                "  }",
                "}))",
                "raise SystemExit(0)",
                "",
            ]
        ),
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    summary_out = tmp_path / "sweep_summary.json"
    result = subprocess.run(
        [
            "python",
            "scripts/run_quant_sweep.py",
            "--model-id",
            "qwen-coder",
            "--quant-tags",
            "Q8_0,Q6_K,Q4_K_M",
            "--task-bank",
            str(task_bank),
            "--runs",
            "1",
            "--runner-template",
            f"python {fake_runner} --task {{task_file}} --venue {{venue}} --flow {{flow}}",
            "--out-dir",
            str(out_dir),
            "--summary-out",
            str(summary_out),
            "--task-limit",
            "1",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    summary = json.loads(summary_out.read_text(encoding="utf-8"))

    assert summary["schema_version"] == "1.1.3"
    assert isinstance(summary["generated_at"], str)
    assert isinstance(summary["hardware_fingerprint"], str)
    assert summary["matrix"]["models"] == ["qwen-coder"]
    assert summary["matrix"]["quants"] == ["Q8_0", "Q6_K", "Q4_K_M"]
    assert summary["matrix"]["task_bank"] == str(task_bank)
    assert summary["matrix"]["runs_per_quant"] == 1

    assert len(summary["sessions"]) == 1
    session = summary["sessions"][0]
    assert session["model_id"] == "qwen-coder"
    assert session["baseline_quant"] == "Q8_0"
    assert session["efficiency_frontier"]["optimal_quant_tag"] == "Q6_K"
    assert session["recommendation"] == "For this hardware, use Q6_K for best Vibe."
    assert session["efficiency_frontier"]["reason"] == "lowest quant meeting >=95% baseline adherence"

    per_quant = {row["quant_tag"]: row for row in session["per_quant"]}
    assert per_quant["Q8_0"]["vibe_delta"] is None
    assert per_quant["Q8_0"]["vibe_delta_status"] == "OK"
    assert per_quant["Q6_K"]["vibe_delta"] == 0.029
    assert per_quant["Q6_K"]["vibe_delta_status"] == "OK"
    assert per_quant["Q4_K_M"]["vibe_delta"] == 0.183
