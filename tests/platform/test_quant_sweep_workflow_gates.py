from __future__ import annotations

from pathlib import Path


def test_quant_sweep_full_workflow_enforces_policy_gates() -> None:
    workflow = Path(".gitea/workflows/quant-sweep-full-selfhosted.yml").read_text(encoding="utf-8")
    required_commands = [
        "python scripts/quant/check_quant_sweep_kpis.py",
        "python scripts/benchmarks/check_lab_guards.py",
        "python scripts/quant/check_sidecar_parse_policy.py",
        "python scripts/quant/check_valid_run_policy.py",
        "python scripts/quant/analyze_vram_fragmentation.py",
        "python scripts/benchmarks/prototype_model_selector.py",
    ]
    missing = [cmd for cmd in required_commands if cmd not in workflow]
    assert not missing, "quant-sweep full workflow missing required policy gates: " + ", ".join(missing)


def test_quant_sweep_smoke_workflow_runs_real_execution_smoke() -> None:
    workflow = Path(".gitea/workflows/quant-sweep-smoke.yml").read_text(encoding="utf-8")
    assert "Matrix Execution Smoke" in workflow
    execution_step = workflow.split("Matrix Execution Smoke", 1)[1]
    assert "stub_quant_runner.py" in execution_step
    assert "--summary-out benchmarks/results/quant/quant_sweep/smoke/sweep_summary.json" in execution_step
    assert "--dry-run" not in execution_step
