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
        "python scripts/check_microservices_unlock.py --matrix benchmarks/results/monolith_variant_matrix.json --readiness-policy model/core/contracts/monolith_readiness_policy.json --unlock-policy model/core/contracts/microservices_unlock_policy.json --live-report benchmarks/results/live_acceptance_patterns.json --out benchmarks/results/microservices_unlock_check.json",
        "python scripts/check_gitea_state_pilot_readiness.py --out benchmarks/results/gitea_state_pilot_readiness.json --require-ready",
        "python scripts/check_gitea_state_hardening.py --execute --out benchmarks/results/gitea_state_hardening_check.json --require-ready",
        "python scripts/check_gitea_state_phase3_readiness.py --execute --pilot-readiness benchmarks/results/gitea_state_pilot_readiness.json --hardening-readiness benchmarks/results/gitea_state_hardening_check.json --out benchmarks/results/gitea_state_phase3_readiness.json --require-ready",
        "python scripts/run_architecture_pilot_matrix.py --out benchmarks/results/architecture_pilot_matrix.json",
        "python scripts/run_benchmark_suite.py --task-bank benchmarks/task_bank/v1/tasks.json --policy model/core/contracts/benchmark_scoring_policy.json --runs 1 --venue standard --flow default --runner-template 'python scripts/determinism_control_runner.py --task {task_file} --venue {venue} --flow {flow}' --raw-out benchmarks/results/benchmark_determinism_report.json --scored-out benchmarks/results/benchmark_scored_report.json",
        "python scripts/check_orchestration_overhead_consistency.py --report benchmarks/results/benchmark_determinism_report.json --out benchmarks/results/orchestration_overhead_consistency.json",
        "python scripts/check_telemetry_artifact_fields.py --report benchmarks/results/benchmark_determinism_report.json --out benchmarks/results/telemetry_artifact_fields_check.json",
        "python scripts/check_benchmark_scoring_gate.py --scored-report benchmarks/results/benchmark_scored_report.json --policy model/core/contracts/benchmark_scoring_policy.json --out benchmarks/results/benchmark_scoring_gate.json --require-thresholds",
        "python scripts/check_memory_determinism.py",
        "python scripts/compare_memory_determinism.py",
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
