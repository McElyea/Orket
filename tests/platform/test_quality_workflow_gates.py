from __future__ import annotations

from pathlib import Path


def test_quality_workflow_enforces_architecture_and_volatility_gates() -> None:
    workflow_path = Path(".gitea/workflows/quality.yml")
    text = workflow_path.read_text(encoding="utf-8")

    required_commands = [
        "python scripts/governance/check_dependency_direction.py --legacy-edge-enforcement fail",
        "python scripts/benchmarks/check_volatility_boundaries.py",
        "python -m pytest -q tests/platform/test_architecture_volatility_boundaries.py",
        "python scripts/governance/retention_plan.py --out benchmarks/results/governance/retention_plan.json",
        "python scripts/governance/check_retention_policy.py --plan benchmarks/results/governance/retention_plan.json --out benchmarks/results/governance/retention_policy_check.json --require-safety",
        "python scripts/benchmarks/check_offline_matrix.py --require-default-offline --out benchmarks/results/benchmarks/offline_matrix_check.json",
        "python scripts/governance/docs_lint.py --project core-pillars --strict --json",
        "python scripts/protocol/run_protocol_ledger_parity_campaign.py --sqlite-db .ci/protocol_quality_workspace/.orket/durable/db/orket_persistence.db --protocol-root .ci/protocol_quality_workspace --strict --out benchmarks/results/protocol/protocol_governed/protocol_ledger_parity_campaign.json",
        "python scripts/protocol/run_protocol_determinism_campaign.py --runs-root .ci/protocol_quality_workspace/runs --run-id run-a --baseline-run-id run-a --strict --out benchmarks/results/protocol/protocol_governed/protocol_replay_campaign.json",
        "python scripts/protocol/publish_protocol_rollout_artifacts.py --workspace-root .ci/protocol_quality_workspace --out-dir benchmarks/results/protocol/protocol_governed/rollout_artifacts --run-id run-a --session-id run-a --baseline-run-id run-a --strict",
        "python scripts/protocol/summarize_protocol_error_codes.py --input benchmarks/results/protocol/protocol_governed/protocol_ledger_parity_campaign.json --out benchmarks/results/protocol/protocol_governed/protocol_error_code_summary.json",
        "python scripts/acceptance/run_monolith_variant_matrix.py --out benchmarks/results/acceptance/monolith_variant_matrix.json",
        "python scripts/acceptance/check_monolith_readiness_gate.py --matrix benchmarks/results/acceptance/monolith_variant_matrix.json --policy model/core/contracts/monolith_readiness_policy.json --allow-plan-only",
        "python scripts/acceptance/check_microservices_unlock.py --matrix benchmarks/results/acceptance/monolith_variant_matrix.json --readiness-policy model/core/contracts/monolith_readiness_policy.json --unlock-policy model/core/contracts/microservices_unlock_policy.json --live-report benchmarks/results/acceptance/live_acceptance_patterns.json --out benchmarks/results/acceptance/microservices_unlock_check.json",
        "python scripts/gitea/check_gitea_state_pilot_readiness.py --out benchmarks/results/gitea/gitea_state_pilot_readiness.json --require-ready",
        "python scripts/gitea/check_gitea_state_hardening.py --execute --out benchmarks/results/gitea/gitea_state_hardening_check.json --require-ready",
        "python scripts/gitea/check_gitea_state_phase3_readiness.py --execute --pilot-readiness benchmarks/results/gitea/gitea_state_pilot_readiness.json --hardening-readiness benchmarks/results/gitea/gitea_state_hardening_check.json --out benchmarks/results/gitea/gitea_state_phase3_readiness.json --require-ready",
        "python scripts/acceptance/run_architecture_pilot_matrix.py --out benchmarks/results/acceptance/architecture_pilot_matrix.json",
        "python scripts/benchmarks/run_benchmark_suite.py --task-bank benchmarks/task_bank/v1/tasks.json --policy model/core/contracts/benchmark_scoring_policy.json --runs 1 --venue standard --flow default --runner-template 'python scripts/benchmarks/determinism_control_runner.py --task {task_file} --venue {venue} --flow {flow}' --raw-out benchmarks/results/benchmarks/benchmark_determinism_report.json --scored-out benchmarks/results/benchmarks/benchmark_scored_report.json",
        "python scripts/benchmarks/check_orchestration_overhead_consistency.py --report benchmarks/results/benchmarks/benchmark_determinism_report.json --out benchmarks/results/benchmarks/orchestration_overhead_consistency.json",
        "python scripts/security/check_telemetry_artifact_fields.py --report benchmarks/results/benchmarks/benchmark_determinism_report.json --out benchmarks/results/security/telemetry_artifact_fields_check.json",
        "python scripts/benchmarks/check_benchmark_scoring_gate.py --scored-report benchmarks/results/benchmarks/benchmark_scored_report.json --policy model/core/contracts/benchmark_scoring_policy.json --out benchmarks/results/benchmarks/benchmark_scoring_gate.json --require-thresholds",
        "python scripts/benchmarks/check_memory_determinism.py",
        "python scripts/benchmarks/compare_memory_determinism.py",
        "python scripts/replay/compare_replay_artifacts.py",
        "python -m pytest -q tests/kernel/v1",
        "python -m pytest -q tests/interfaces/test_api_kernel_lifecycle.py",
        "python scripts/governance/run_kernel_fire_drill.py",
    ]
    missing = [cmd for cmd in required_commands if cmd not in text]
    assert not missing, "quality workflow missing required architecture gates: " + ", ".join(missing)

    # The quick gate job and the full quality job should both run these checks.
    duplicated_in_both_jobs = [
        "python scripts/governance/check_dependency_direction.py --legacy-edge-enforcement fail",
        "python scripts/benchmarks/check_volatility_boundaries.py",
        "python scripts/governance/retention_plan.py --out benchmarks/results/governance/retention_plan.json",
        "python scripts/governance/check_retention_policy.py --plan benchmarks/results/governance/retention_plan.json --out benchmarks/results/governance/retention_policy_check.json --require-safety",
        "python scripts/benchmarks/check_offline_matrix.py --require-default-offline --out benchmarks/results/benchmarks/offline_matrix_check.json",
        "python scripts/governance/docs_lint.py --project core-pillars --strict --json",
    ]
    missing_dupes = [cmd for cmd in duplicated_in_both_jobs if text.count(cmd) < 2]
    assert not missing_dupes, (
        "quality workflow gates must be present in both architecture_gates and quality jobs: "
        + ", ".join(missing_dupes)
    )
