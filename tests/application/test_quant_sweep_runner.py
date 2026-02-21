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
                "    'token_metrics_status': 'OK',",
                "    'run_quality_status': 'CLEAN',",
                "    'run_quality_reasons': [],",
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
    assert isinstance(summary["commit_sha"], str)
    assert isinstance(summary["generated_at"], str)
    assert isinstance(summary["hardware_fingerprint"], str)
    assert summary["matrix"]["models"] == ["qwen-coder"]
    assert summary["matrix"]["quants"] == ["Q8_0", "Q6_K", "Q4_K_M"]
    assert summary["matrix"]["task_bank"] == str(task_bank)
    assert summary["matrix"]["runs_per_quant"] == 1
    assert summary["matrix"]["latency_ceiling"] == 10.0
    assert summary["matrix"]["experimental_controls"] == {
        "seed": None,
        "threads": None,
        "affinity_policy": "",
        "warmup_steps": None,
    }

    assert len(summary["sessions"]) == 1
    session = summary["sessions"][0]
    assert session["model_id"] == "qwen-coder"
    assert session["baseline_quant"] == "Q8_0"
    assert session["efficiency_frontier"]["minimum_viable_quant_tag"] == "Q6_K"
    assert session["efficiency_frontier"]["best_value_quant_tag"] == "Q8_0"
    assert session["recommendation"] == "For this hardware, use Q6_K for best Vibe."
    assert session["efficiency_frontier"]["reason"] == "lowest quant meeting adherence and latency thresholds"
    assert session["recommendation_detail"] == {
        "minimum_viable_quant": "Q6_K",
        "best_value_quant": "Q8_0",
    }
    assert summary["stability_kpis"]["frontier_success_rate"] == 1.0
    assert summary["stability_kpis"]["missing_telemetry_rate"] == 0.0
    assert summary["stability_kpis"]["polluted_run_rate"] == 0.0

    per_quant = {row["quant_tag"]: row for row in session["per_quant"]}
    assert per_quant["Q8_0"]["vibe_delta"] == 0.0
    assert per_quant["Q8_0"]["vibe_delta_status"] == "OK"
    assert per_quant["Q6_K"]["vibe_delta"] == 0.029
    assert per_quant["Q6_K"]["vibe_delta_status"] == "OK"
    assert per_quant["Q4_K_M"]["vibe_delta"] == 0.183


def test_run_quant_sweep_recommends_mismatch_when_no_quant_meets_threshold(tmp_path: Path) -> None:
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

    fake_runner = tmp_path / "fake_quant_runner_slow.py"
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
                "    adherence, mem, latency = 1.0, 3000.0, 12.0",
                "else:",
                "    adherence, mem, latency = 0.7, 1500.0, 12.5",
                "print(json.dumps({",
                "  'telemetry': {",
                "    'init_latency': None,",
                "    'total_latency': latency,",
                "    'peak_memory_rss': mem,",
                "    'adherence_score': adherence,",
                "    'run_quality_status': 'CLEAN',",
                "    'run_quality_reasons': [],",
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

    summary_out = tmp_path / "sweep_summary.json"
    result = subprocess.run(
        [
            "python",
            "scripts/run_quant_sweep.py",
            "--model-id",
            "qwen-coder",
            "--quant-tags",
            "Q8_0,Q4_K_M",
            "--task-bank",
            str(task_bank),
            "--runs",
            "1",
            "--runner-template",
            f"python {fake_runner} --task {{task_file}} --venue {{venue}} --flow {{flow}}",
            "--summary-out",
            str(summary_out),
            "--task-limit",
            "1",
            "--latency-ceiling",
            "10.0",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    summary = json.loads(summary_out.read_text(encoding="utf-8"))
    session = summary["sessions"][0]
    assert session["efficiency_frontier"]["minimum_viable_quant_tag"] is None
    assert session["efficiency_frontier"]["best_value_quant_tag"] is None
    assert session["efficiency_frontier"]["reason"] == "no quant met adherence and latency thresholds"
    assert session["recommendation"] == "No quantization met the vibe threshold; hardware/model mismatch."
    assert summary["stability_kpis"]["frontier_success_rate"] == 0.0


def test_run_quant_sweep_canary_gate_blocks_on_missing_telemetry(tmp_path: Path) -> None:
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

    fake_runner = tmp_path / "fake_quant_runner_no_tokens.py"
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
                "print(json.dumps({",
                "  'telemetry': {",
                "    'init_latency': None,",
                "    'total_latency': 1.0,",
                "    'peak_memory_rss': 100.0,",
                "    'adherence_score': 1.0",
                "  }",
                "}))",
                "raise SystemExit(0)",
                "",
            ]
        ),
        encoding="utf-8",
    )

    summary_out = tmp_path / "sweep_summary.json"
    result = subprocess.run(
        [
            "python",
            "scripts/run_quant_sweep.py",
            "--model-id",
            "qwen-coder",
            "--quant-tags",
            "Q8_0,Q4_K_M",
            "--task-bank",
            str(task_bank),
            "--runs",
            "1",
            "--runner-template",
            f"python {fake_runner} --task {{task_file}} --venue {{venue}} --flow {{flow}}",
            "--summary-out",
            str(summary_out),
            "--task-limit",
            "1",
            "--canary-runs",
            "2",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "Canary gate failed; aborting quant sweep." in (result.stdout + "\n" + result.stderr)


def test_run_quant_sweep_dry_run_uses_matrix_config(tmp_path: Path) -> None:
    matrix_cfg = tmp_path / "matrix.json"
    matrix_cfg.write_text(
        json.dumps(
            {
                "models": ["qwen-coder"],
                "quants": ["Q8_0", "Q6_K"],
                "task_bank": "benchmarks/task_bank/v2_realworld/tasks.json",
                "runs_per_quant": 2,
                "task_limit": 3,
                "runtime_target": "local-hardware",
                "execution_mode": "live-card",
                "seed": 123,
                "threads": 12,
                "affinity_policy": "pcores",
                "warmup_steps": 2,
                "canary_runs": 5,
            }
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            "python",
            "scripts/run_quant_sweep.py",
            "--model-id",
            "placeholder-model",
            "--quant-tags",
            "Q4_K_M",
            "--matrix-config",
            str(matrix_cfg),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(result.stdout)
    plan = payload["dry_run"]
    assert isinstance(plan["commit_sha"], str)
    assert plan["models"] == ["qwen-coder"]
    assert plan["quants"] == ["Q8_0", "Q6_K"]
    assert plan["runs_per_quant"] == 2
    assert plan["task_limit"] == 3
    assert plan["task_bank"] == "benchmarks/task_bank/v2_realworld/tasks.json"
    assert plan["experimental_controls"] == {
        "seed": 123,
        "threads": 12,
        "affinity_policy": "pcores",
        "warmup_steps": 2,
    }
    assert plan["canary"]["enabled"] is True
    assert plan["canary"]["runs"] == 5


def test_run_quant_sweep_excludes_polluted_rows_unless_overridden(tmp_path: Path) -> None:
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

    fake_runner = tmp_path / "fake_quant_runner_polluted.py"
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
                "else:",
                "    adherence, mem = 0.98, 2300.0",
                "print(json.dumps({",
                "  'telemetry': {",
                "    'init_latency': None,",
                "    'total_latency': 1.0,",
                "    'peak_memory_rss': mem,",
                "    'adherence_score': adherence,",
                "    'run_quality_status': 'POLLUTED',",
                "    'run_quality_reasons': ['HIGH_SYSTEM_LOAD']",
                "  }",
                "}))",
                "raise SystemExit(0)",
                "",
            ]
        ),
        encoding="utf-8",
    )

    summary_default = tmp_path / "sweep_default.json"
    default_result = subprocess.run(
        [
            "python",
            "scripts/run_quant_sweep.py",
            "--model-id",
            "qwen-coder",
            "--quant-tags",
            "Q8_0,Q6_K",
            "--task-bank",
            str(task_bank),
            "--runs",
            "1",
            "--runner-template",
            f"python {fake_runner} --task {{task_file}} --venue {{venue}} --flow {{flow}}",
            "--summary-out",
            str(summary_default),
            "--task-limit",
            "1",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert default_result.returncode == 0, default_result.stdout + "\n" + default_result.stderr
    default_payload = json.loads(summary_default.read_text(encoding="utf-8"))
    default_session = default_payload["sessions"][0]
    assert default_session["efficiency_frontier"]["minimum_viable_quant_tag"] is None
    assert default_session["efficiency_frontier"]["best_value_quant_tag"] is None
    assert default_payload["stability_kpis"]["polluted_run_rate"] == 1.0
    assert default_payload["stability_kpis"]["frontier_success_rate"] == 0.0

    summary_override = tmp_path / "sweep_override.json"
    override_result = subprocess.run(
        [
            "python",
            "scripts/run_quant_sweep.py",
            "--model-id",
            "qwen-coder",
            "--quant-tags",
            "Q8_0,Q6_K",
            "--task-bank",
            str(task_bank),
            "--runs",
            "1",
            "--runner-template",
            f"python {fake_runner} --task {{task_file}} --venue {{venue}} --flow {{flow}}",
            "--summary-out",
            str(summary_override),
            "--task-limit",
            "1",
            "--allow-polluted-frontier",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert override_result.returncode == 0, override_result.stdout + "\n" + override_result.stderr
    override_payload = json.loads(summary_override.read_text(encoding="utf-8"))
    override_session = override_payload["sessions"][0]
    assert override_session["efficiency_frontier"]["minimum_viable_quant_tag"] == "Q6_K"
    assert override_payload["stability_kpis"]["polluted_run_rate"] == 1.0
    assert override_payload["stability_kpis"]["frontier_success_rate"] == 0.0


def test_run_quant_sweep_records_hardware_sidecar_output(tmp_path: Path) -> None:
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
    fake_runner = tmp_path / "fake_quant_runner_clean.py"
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
                "print(json.dumps({'telemetry': {'init_latency': None, 'total_latency': 1.0, 'peak_memory_rss': 100.0, 'adherence_score': 1.0, 'run_quality_status': 'CLEAN', 'run_quality_reasons': []}}))",
                "raise SystemExit(0)",
                "",
            ]
        ),
        encoding="utf-8",
    )
    sidecar = tmp_path / "fake_sidecar.py"
    sidecar.write_text(
        "\n".join(
            [
                "import json",
                "print(json.dumps({",
                "  'vram_total_mb': 24576,",
                "  'vram_used_mb': 21340,",
                "  'ttft_ms': 142,",
                "  'prefill_tps': 312.4,",
                "  'decode_tps': 28.7,",
                "  'thermal_start_c': 54,",
                "  'thermal_end_c': 71,",
                "  'kernel_launch_ms': 3.2,",
                "  'model_load_ms': 412,",
                "  'pcie_throughput_gbps': 22.1,",
                "  'cuda_graph_warmup_ms': 14.0,",
                "  'gpu_clock_mhz': 2730,",
                "  'power_draw_watts': 358,",
                "  'fan_speed_percent': 74",
                "}))",
            ]
        ),
        encoding="utf-8",
    )
    summary_out = tmp_path / "sweep_summary.json"
    result = subprocess.run(
        [
            "python",
            "scripts/run_quant_sweep.py",
            "--model-id",
            "qwen-coder",
            "--quant-tags",
            "Q8_0",
            "--task-bank",
            str(task_bank),
            "--runs",
            "1",
            "--runner-template",
            f"python {fake_runner} --task {{task_file}} --venue {{venue}} --flow {{flow}}",
            "--summary-out",
            str(summary_out),
            "--task-limit",
            "1",
            "--hardware-sidecar-template",
            f"python {sidecar}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    summary = json.loads(summary_out.read_text(encoding="utf-8"))
    assert summary["matrix"]["hardware_sidecar"]["enabled"] is True
    row = summary["sessions"][0]["per_quant"][0]
    assert row["hardware_sidecar"]["enabled"] is True
    assert row["hardware_sidecar"]["return_code"] == 0
    assert row["hardware_sidecar"]["vram_total_mb"] == 24576.0
    assert row["hardware_sidecar"]["decode_tps"] == 28.7
    assert row["hardware_sidecar"]["sidecar_parse_status"] == "OK"
    assert row["hardware_sidecar"]["sidecar_parse_errors"] == []


def test_run_quant_sweep_sidecar_required_field_missing_sets_status(tmp_path: Path) -> None:
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
    fake_runner = tmp_path / "fake_quant_runner_clean.py"
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
                "print(json.dumps({'telemetry': {'init_latency': None, 'total_latency': 1.0, 'peak_memory_rss': 100.0, 'adherence_score': 1.0, 'run_quality_status': 'CLEAN', 'run_quality_reasons': []}}))",
                "raise SystemExit(0)",
                "",
            ]
        ),
        encoding="utf-8",
    )
    sidecar = tmp_path / "fake_sidecar_missing.py"
    sidecar.write_text(
        "\n".join(
            [
                "import json",
                "print(json.dumps({'vram_total_mb': 24576, 'vram_used_mb': 20000}))",
            ]
        ),
        encoding="utf-8",
    )
    summary_out = tmp_path / "sweep_summary.json"
    result = subprocess.run(
        [
            "python",
            "scripts/run_quant_sweep.py",
            "--model-id",
            "qwen-coder",
            "--quant-tags",
            "Q8_0",
            "--task-bank",
            str(task_bank),
            "--runs",
            "1",
            "--runner-template",
            f"python {fake_runner} --task {{task_file}} --venue {{venue}} --flow {{flow}}",
            "--summary-out",
            str(summary_out),
            "--task-limit",
            "1",
            "--hardware-sidecar-template",
            f"python {sidecar}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    summary = json.loads(summary_out.read_text(encoding="utf-8"))
    sidecar_block = summary["sessions"][0]["per_quant"][0]["hardware_sidecar"]
    assert sidecar_block["sidecar_parse_status"] == "REQUIRED_FIELD_MISSING"
    assert "missing:ttft_ms" in sidecar_block["sidecar_parse_errors"]


def test_run_quant_sweep_sidecar_optional_field_missing_sets_status(tmp_path: Path) -> None:
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
    fake_runner = tmp_path / "fake_quant_runner_clean.py"
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
                "print(json.dumps({'telemetry': {'init_latency': None, 'total_latency': 1.0, 'peak_memory_rss': 100.0, 'adherence_score': 1.0, 'run_quality_status': 'CLEAN', 'run_quality_reasons': []}}))",
                "raise SystemExit(0)",
                "",
            ]
        ),
        encoding="utf-8",
    )
    sidecar = tmp_path / "fake_sidecar_required_only.py"
    sidecar.write_text(
        "\n".join(
            [
                "import json",
                "print(json.dumps({",
                "  'vram_total_mb': 24576,",
                "  'vram_used_mb': 21340,",
                "  'ttft_ms': 142,",
                "  'prefill_tps': 312.4,",
                "  'decode_tps': 28.7,",
                "  'thermal_start_c': 54,",
                "  'thermal_end_c': 71,",
                "  'kernel_launch_ms': 3.2,",
                "  'model_load_ms': 412",
                "}))",
            ]
        ),
        encoding="utf-8",
    )
    summary_out = tmp_path / "sweep_summary.json"
    result = subprocess.run(
        [
            "python",
            "scripts/run_quant_sweep.py",
            "--model-id",
            "qwen-coder",
            "--quant-tags",
            "Q8_0",
            "--task-bank",
            str(task_bank),
            "--runs",
            "1",
            "--runner-template",
            f"python {fake_runner} --task {{task_file}} --venue {{venue}} --flow {{flow}}",
            "--summary-out",
            str(summary_out),
            "--task-limit",
            "1",
            "--hardware-sidecar-template",
            f"python {sidecar}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    summary = json.loads(summary_out.read_text(encoding="utf-8"))
    sidecar_block = summary["sessions"][0]["per_quant"][0]["hardware_sidecar"]
    assert sidecar_block["sidecar_parse_status"] == "OPTIONAL_FIELD_MISSING"
    assert "missing:pcie_throughput_gbps" in sidecar_block["sidecar_parse_errors"]
