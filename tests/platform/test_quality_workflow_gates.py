from __future__ import annotations

import shlex
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit


def _job_command_gaps(jobs, required_commands, *, exact=False):
    """Observe explicit argv per job; text in another job/comment/echo is no gate."""
    gaps = []
    for name in ("architecture_gates", "quality"):
        commands = []
        for step in jobs[name]["steps"]:
            for line in str(step.get("run", "")).replace("\\\n", " ").splitlines():
                if line.strip().startswith(("python ", "pytest ", "bash ")):
                    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
                    lexer.whitespace_split = True
                    tokens = list(lexer)
                    # This guard admits simple argv only, not shell compound syntax.
                    if not any(set(token) <= set("();<>|&") for token in tokens):
                        commands.append(tokens)
        for required in required_commands:
            tokens = shlex.split(required)
            if tokens[0].startswith("tests/"):
                present = any((cmd[:3] == ["python", "-m", "pytest"] or cmd[:1] == ["pytest"])
                              and set(tokens).issubset(cmd) for cmd in commands)
            else:
                present = any((cmd == tokens if exact else cmd[:len(tokens)] == tokens) for cmd in commands)
            if not present:
                gaps.append((name, required))
    return gaps


def test_quality_workflow_enforces_architecture_and_volatility_gates() -> None:
    """Layer: unit. Inspect workflow declarations; this does not execute hosted gates."""
    workflow_path = Path(".gitea/workflows/quality.yml")
    text = workflow_path.read_text(encoding="utf-8")

    required_commands = [
        "python scripts/governance/check_dependency_direction.py",
        "python scripts/benchmarks/check_volatility_boundaries.py",
        "python -m pytest -q tests/platform/test_architecture_volatility_boundaries.py",
        "python scripts/governance/retention_plan.py --out benchmarks/results/governance/retention_plan.json",
        "python scripts/governance/check_retention_policy.py --plan benchmarks/results/governance/retention_plan.json --out benchmarks/results/governance/retention_policy_check.json --require-safety",
        "python scripts/benchmarks/check_offline_matrix.py --require-default-offline --out benchmarks/results/benchmarks/offline_matrix_check.json",
        "bash tests/acceptance/docs_gate/run.sh",
        "python -m pytest -q tests/application/test_docs_lint_script.py",
        "python scripts/protocol/run_protocol_ledger_parity_campaign.py --sqlite-db .ci/protocol_quality_workspace/.orket/durable/db/orket_persistence.db --protocol-root .ci/protocol_quality_workspace --strict --out benchmarks/results/protocol/protocol_governed/protocol_ledger_parity_campaign.json",
        "python scripts/protocol/run_protocol_determinism_campaign.py --runs-root .ci/protocol_quality_workspace/runs --run-id run-a --baseline-run-id run-a --strict --out benchmarks/results/protocol/protocol_governed/protocol_replay_campaign.json",
        "python scripts/protocol/publish_protocol_rollout_artifacts.py --workspace-root .ci/protocol_quality_workspace --out-dir benchmarks/results/protocol/protocol_governed/rollout_artifacts --run-id run-a --session-id run-a --baseline-run-id run-a --strict",
        "python scripts/protocol/summarize_protocol_error_codes.py --input benchmarks/results/protocol/protocol_governed/protocol_ledger_parity_campaign.json --out benchmarks/results/protocol/protocol_governed/protocol_error_code_summary.json",
        "python -m pytest -q tests/kernel/v1/test_odr_determinism_gate.py -k gate_pr",
        "python scripts/acceptance/run_monolith_variant_matrix.py --out benchmarks/results/acceptance/monolith_variant_matrix.json",
        "python scripts/acceptance/check_monolith_readiness_gate.py --matrix benchmarks/results/acceptance/monolith_variant_matrix.json --policy model/core/contracts/monolith_readiness_policy.json --allow-plan-only",
        "python scripts/acceptance/check_microservices_unlock.py --matrix benchmarks/results/acceptance/monolith_variant_matrix.json --readiness-policy model/core/contracts/monolith_readiness_policy.json --unlock-policy model/core/contracts/microservices_unlock_policy.json --live-report benchmarks/results/acceptance/live_acceptance_patterns.json --out benchmarks/results/acceptance/microservices_unlock_check.json",
        "python scripts/gitea/check_gitea_state_pilot_readiness.py --out benchmarks/results/gitea/gitea_state_pilot_readiness.json --require-ready",
        "python scripts/gitea/check_gitea_state_hardening.py --execute --out benchmarks/results/gitea/gitea_state_hardening_check.json --require-ready",
        "python scripts/gitea/check_gitea_state_phase3_readiness.py --execute --pilot-readiness benchmarks/results/gitea/gitea_state_pilot_readiness.json --hardening-readiness benchmarks/results/gitea/gitea_state_hardening_check.json --out benchmarks/results/gitea/gitea_state_phase3_readiness.json --require-ready",
        "python scripts/acceptance/run_architecture_pilot_matrix.py --out benchmarks/results/acceptance/architecture_pilot_matrix.json",
        "python scripts/benchmarks/run_benchmark_suite.py --task-bank benchmarks/task_bank/v1/tasks.json --policy model/core/contracts/benchmark_scoring_policy.json --runs 2 --venue standard --flow default --runner-template 'python scripts/benchmarks/determinism_control_runner.py --task {task_file} --venue {venue} --flow {flow}' --raw-out benchmarks/results/benchmarks/benchmark_determinism_report.json --scored-out benchmarks/results/benchmarks/benchmark_scored_report.json",
        "python scripts/benchmarks/check_orchestration_overhead_consistency.py --report benchmarks/results/benchmarks/benchmark_determinism_report.json --out benchmarks/results/benchmarks/orchestration_overhead_consistency.json",
        "python scripts/security/check_telemetry_artifact_fields.py --report benchmarks/results/benchmarks/benchmark_determinism_report.json --out benchmarks/results/security/telemetry_artifact_fields_check.json",
        "python scripts/benchmarks/check_benchmark_scoring_gate.py --scored-report benchmarks/results/benchmarks/benchmark_scored_report.json --policy model/core/contracts/benchmark_scoring_policy.json --out benchmarks/results/benchmarks/benchmark_scoring_gate.json --require-thresholds",
        "python scripts/ci/memory_fixture_smoke.py --profile quality --out-dir benchmarks/results/benchmarks/memory",
        "python scripts/ci/sandbox_leak_gate.py",
        "python scripts/ci/migration_smoke_validator.py --runtime-db .ci/runtime.db --webhook-db .ci/webhook.db --bootstrap",
        "python scripts/ci/migration_smoke_validator.py --runtime-db .ci/runtime.db --webhook-db .ci/webhook.db --validate",
        "python scripts/benchmarks/check_memory_determinism.py",
        "python scripts/benchmarks/compare_memory_determinism.py",
        "python scripts/replay/compare_replay_artifacts.py",
        "python -m pytest -q tests/kernel/v1",
        "python -m pytest -q tests/interfaces/test_api_kernel_lifecycle.py",
        "python scripts/governance/run_kernel_fire_drill.py",
    ]
    missing = [cmd for cmd in required_commands if cmd not in text]
    assert not missing, "quality workflow missing required architecture gates: " + ", ".join(missing)
    assert "Smoke: memory trace fixture contract and comparator identity check" in text
    assert "Enforce memory determinism contract smoke" not in text
    assert "--left benchmarks/results/benchmarks/memory/memory_trace_fixture_left.json" in text
    assert "--right benchmarks/results/benchmarks/memory/memory_trace_fixture_right.json" in text
    assert "--left-retrieval benchmarks/results/benchmarks/memory/memory_retrieval_trace_fixture_left.json" in text
    assert "--right-retrieval benchmarks/results/benchmarks/memory/memory_retrieval_trace_fixture_right.json" in text

    # The quick gate job and the full quality job should both run these checks.
    duplicated_in_both_jobs = [
        "tests/integration/test_bug_fix_event_inputs.py tests/integration/test_preview_required_events.py tests/integration/test_structural_required_events.py tests/integration/test_missing_read_event_inputs.py",
        "tests/integration/test_model_stream_iterator_lifetime.py tests/integration/test_model_stream_transport_lifetime.py tests/integration/test_model_stream_transport_inputs.py tests/integration/test_model_stream_transport_failure.py",
        "tests/integration/test_tool_runtime_ownership.py tests/integration/test_guarded_mutation_ownership.py tests/integration/test_application_root_inputs.py tests/integration/test_epic_execution_phase_ownership.py",
        "tests/integration/test_extension_capability_api_lifetime.py tests/integration/test_extension_generation_options_api.py tests/integration/test_piper_process_lifetime.py tests/integration/test_interaction_cancel_ownership.py tests/integration/test_operator_completion_views.py",
        "tests/integration/test_api_construction_ownership.py tests/integration/test_api_construction_inputs.py tests/integration/test_api_preparation_interruption.py tests/integration/test_api_server_bootstrap.py tests/integration/test_api_server_reload.py",
        "tests/integration/test_workload_publication_ownership.py tests/integration/test_workload_publication_inputs.py tests/integration/test_legacy_publication_ownership.py tests/integration/test_workload_policy_inputs.py tests/integration/test_workload_reproducibility_inputs.py tests/runtime/test_workload_policy.py tests/integration/test_extension_installation_ownership.py tests/integration/test_extension_catalog_publication.py tests/integration/test_extension_manager_preflight.py tests/integration/test_extension_git_lifetime.py tests/runtime/test_extension_source_policy.py tests/contracts/test_extension_cli_ownership.py tests/contracts/test_extension_git_cancellation.py tests/integration/test_sandbox_deploy_publication_recovery.py tests/rulesim/test_interruption_reproducibility.py",
        "tests/integration/test_extension_module_origin.py tests/integration/test_extension_load_ownership.py",
        "tests/integration/test_run_start_publication.py tests/integration/test_run_start_ownership.py",
        "tests/integration/test_sdk_process_lifetime.py tests/integration/test_sdk_process_control_plane.py tests/integration/test_sdk_exchange_ownership.py tests/contracts/test_sdk_process_observations.py tests/runtime/test_controller_dispatcher.py tests/runtime/test_controller_observability.py tests/integration/test_controller_schema_ownership.py tests/integration/test_extension_construction_inputs.py tests/integration/test_direct_extension_construction.py tests/integration/test_controller_construction_ownership.py",
        "tests/contracts/test_prompt_metadata_values.py tests/integration/test_prompt_command_ownership.py tests/integration/test_setup_command_ownership.py tests/integration/test_vision_command_ownership.py",
        "python -m pytest -q tests/contracts/test_core_effect_values.py tests/integration/test_core_effect_boundaries.py",
        "python scripts/governance/check_dependency_direction.py",
        "python scripts/benchmarks/check_volatility_boundaries.py",
        "python scripts/governance/retention_plan.py --out benchmarks/results/governance/retention_plan.json",
        "python scripts/governance/check_retention_policy.py --plan benchmarks/results/governance/retention_plan.json --out benchmarks/results/governance/retention_policy_check.json --require-safety",
        "python scripts/benchmarks/check_offline_matrix.py --require-default-offline --out benchmarks/results/benchmarks/offline_matrix_check.json",
        "bash tests/acceptance/docs_gate/run.sh",
        "python -m pytest -q tests/application/test_docs_lint_script.py",
    ]
    missing_dupes = _job_command_gaps(yaml.safe_load(text)["jobs"], duplicated_in_both_jobs)
    assert not missing_dupes, (
        "quality workflow gates must be present in both architecture_gates and quality jobs: "
        + ", ".join(f"{job}: {command}" for job, command in missing_dupes)
    )


def test_nightly_benchmark_workflow_uses_valid_determinism_runs_and_extracted_fixture() -> None:
    """Layer: unit. Inspect nightly determinism and memory-fixture command declarations."""
    workflow_path = Path(".gitea/workflows/nightly-benchmark.yml")
    text = workflow_path.read_text(encoding="utf-8")

    assert "--runs 2" in text
    assert (
        "python scripts/ci/memory_fixture_smoke.py --profile nightly --out-dir benchmarks/results/benchmarks/memory"
        in text
    )
    assert "python - <<'PY'" not in text


@pytest.mark.parametrize("case", ["extra-selector", "wrong-job", "comment", "echo", "inline-comment", "compound-echo"])
def test_job_selection_requires_real_pytest_argv_in_each_job(case):
    command = "python -m pytest -q tests/first.py tests/new.py tests/second.py"
    jobs = {name: {"steps": [{"run": command}]} for name in ("architecture_gates", "quality")}
    if case == "wrong-job":
        jobs["architecture_gates"]["steps"].append({"run": command})
        jobs["quality"]["steps"] = []
    elif case == "comment":
        jobs["quality"]["steps"] = [{"run": "# " + command}]
    elif case == "echo":
        jobs["quality"]["steps"] = [{"run": "echo '" + command + "'"}]
    elif case == "inline-comment":
        jobs["quality"]["steps"] = [{"run": "python -m pytest tests/first.py # tests/second.py"}]
    elif case == "compound-echo":
        jobs["quality"]["steps"] = [{"run": "python -m pytest tests/first.py && echo tests/second.py"}]
    gaps = _job_command_gaps(jobs, ["tests/first.py tests/second.py"])
    assert gaps == ([] if case == "extra-selector" else [("quality", "tests/first.py tests/second.py")])


TRUTHFUL_CHECKER_COMMANDS = (
    "python scripts/governance/enforce_test_taxonomy.py --strict",
    "python scripts/governance/check_noop_critical_paths.py",
    "python scripts/governance/check_current_authority.py",
)


def test_quality_runs_native_checkers_in_both_truthful_checker_steps() -> None:
    """Layer: unit. Exact declared argv does not prove hosted execution or findings."""
    jobs = yaml.safe_load(Path(".gitea/workflows/quality.yml").read_text(encoding="utf-8"))["jobs"]
    selected = {}
    for name in ("architecture_gates", "quality"):
        steps = [step for step in jobs[name]["steps"] if step.get("name") == "Enforce truthful quality checker observations"]
        assert len(steps) == 1, f"{name}: expected one truthful-checker step"
        assert "if" not in steps[0], f"{name}: truthful-checker step must not be conditional"
        assert not steps[0].get("continue-on-error"), f"{name}: truthful-checker failures must fail the job"
        assert steps[0].get("env", {}).get("ORKET_DISABLE_SANDBOX") == "1"
        selected[name] = {"steps": steps}
    assert not _job_command_gaps(selected, TRUTHFUL_CHECKER_COMMANDS, exact=True)
    assert not _job_command_gaps(selected, [
        "tests/scripts/test_enforce_test_taxonomy.py",
        "tests/scripts/test_check_noop_critical_paths.py",
        "tests/platform/test_quality_workflow_gates.py",
        "tests/scripts/test_current_authority_source.py",
        "tests/platform/test_current_authority_map.py",
        "tests/platform/test_remediation_authority_docs.py",
    ])


@pytest.mark.parametrize("command", TRUTHFUL_CHECKER_COMMANDS)
@pytest.mark.parametrize("case", ["exact", "wrong-job", "comment", "echo", "compound", "root-override", "inline-option"])
def test_native_checker_gate_requires_exact_argv_in_each_job(command, case):
    """Layer: unit. Adverse declarations cannot impersonate the default-root command."""
    observed = {
        "exact": command,
        "wrong-job": "",
        "comment": "# " + command,
        "echo": "echo '" + command + "'",
        "compound": command + " || true",
        "root-override": command + " --root tests/one.py",
        "inline-option": command.replace(" --strict", "") + " # --strict --root tests/one.py",
    }[case]
    jobs = {name: {"steps": [{"run": command}]} for name in ("architecture_gates", "quality")}
    jobs["quality"]["steps"] = [{"run": observed}]
    # A comment after an already-complete no-op command does not change its argv.
    accepted = case == "exact" or (case == "inline-option" and "--strict" not in command)
    expected = [] if accepted else [("quality", command)]
    assert _job_command_gaps(jobs, [command], exact=True) == expected
