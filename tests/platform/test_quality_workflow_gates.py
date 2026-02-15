from __future__ import annotations

from pathlib import Path


def test_quality_workflow_enforces_architecture_and_volatility_gates() -> None:
    workflow_path = Path(".gitea/workflows/quality.yml")
    text = workflow_path.read_text(encoding="utf-8")

    required_commands = [
        "python scripts/check_dependency_direction.py",
        "python scripts/check_volatility_boundaries.py",
        "python -m pytest -q tests/platform/test_architecture_volatility_boundaries.py",
        "python scripts/run_monolith_variant_matrix.py --out benchmarks/results/monolith_variant_matrix.json",
        "python scripts/check_monolith_readiness_gate.py --matrix benchmarks/results/monolith_variant_matrix.json --policy model/core/contracts/monolith_readiness_policy.json --allow-plan-only",
    ]
    missing = [cmd for cmd in required_commands if cmd not in text]
    assert not missing, "quality workflow missing required architecture gates: " + ", ".join(missing)

    # The quick gate job and the full quality job should both run these checks.
    duplicated_in_both_jobs = [
        "python scripts/check_dependency_direction.py",
        "python scripts/check_volatility_boundaries.py",
    ]
    missing_dupes = [cmd for cmd in duplicated_in_both_jobs if text.count(cmd) < 2]
    assert not missing_dupes, (
        "quality workflow gates must be present in both architecture_gates and quality jobs: "
        + ", ".join(missing_dupes)
    )
