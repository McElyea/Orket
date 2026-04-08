from __future__ import annotations

from pathlib import Path


def test_baseline_retention_weekly_workflow_uses_one_artifact_directory() -> None:
    """Layer: contract. Verifies the workflow prepares, writes, and uploads the same artifact directory."""
    workflow_path = Path(".gitea/workflows/baseline-retention-weekly.yml")
    workflow_text = workflow_path.read_text(encoding="utf-8")

    expected_dir = "benchmarks/results/quant/quant_sweep"
    unexpected_dir = "benchmarks/results/benchmarks/quant_sweep"

    assert f"mkdir -p {expected_dir}" in workflow_text
    assert f"> {expected_dir}/baseline_health_weekly.json" in workflow_text
    assert f"> {expected_dir}/baseline_prune_weekly.json" in workflow_text
    assert f"> {expected_dir}/baseline_prune_apply_weekly.json" in workflow_text
    assert f"{expected_dir}/baseline_health_weekly.json" in workflow_text
    assert f"{expected_dir}/baseline_prune_weekly.json" in workflow_text
    assert f"{expected_dir}/baseline_prune_apply_weekly.json" in workflow_text
    assert "if: ${{ github.event_name == 'schedule' }}" in workflow_text
    assert unexpected_dir not in workflow_text
