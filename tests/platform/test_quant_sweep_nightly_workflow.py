from __future__ import annotations

from pathlib import Path


def test_quant_sweep_nightly_workflow_is_truthful_dry_run_contract() -> None:
    """Layer: contract. Verifies the nightly quant workflow is labeled as a dry-run artifact lane, not a fake KPI gate."""
    workflow_path = Path(".gitea/workflows/quant-sweep-nightly.yml")
    text = workflow_path.read_text(encoding="utf-8")

    required_commands = [
        "Generate Quant Sweep Dry Run Plan",
        "Validate Quant Sweep Dry Run Plan",
        "--dry-run > benchmarks/results/quant/quant_sweep/nightly_dry_run_plan.json",
        "quant-sweep-nightly-dry-run-artifacts",
        "benchmarks/results/quant/quant_sweep/nightly_dry_run_plan.json",
    ]
    missing = [cmd for cmd in required_commands if cmd not in text]
    assert not missing, "nightly quant workflow missing required dry-run contract markers: " + ", ".join(missing)
    assert "Build KPI Sample Artifact" not in text
    assert "Enforce KPI Thresholds" not in text
    assert "nightly_sample_summary.json" not in text
    assert "nightly_sample_kpis.json" not in text
