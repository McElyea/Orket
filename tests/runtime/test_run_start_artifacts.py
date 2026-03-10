from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from orket.runtime import run_start_artifacts, run_start_contract_artifacts
from orket.runtime.run_start_artifacts import capture_run_start_artifacts


# Layer: unit
def test_capture_run_start_artifacts_writes_required_run_start_files(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "a.txt").parent.mkdir(parents=True, exist_ok=True)
    (workspace / "a.txt").write_text("alpha", encoding="utf-8")
    payload = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-1",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )

    assert payload["run_identity"]["run_id"] == "run-1"
    assert payload["run_identity"]["workload"] == "core_epic"
    assert payload["run_identity"]["start_time"].startswith("2026-03-06T17:00:00")
    assert payload["run_determinism_class"] == "workspace"
    assert payload["run_phase_contract"]["schema_version"] == "1.0"
    assert payload["run_phase_contract"]["entry_phase"] == "input_normalize"
    assert payload["run_phase_contract"]["terminal_phase"] == "emit_observability"
    assert payload["runtime_status_vocabulary"]["schema_version"] == "1.0"
    assert "terminal_failure" in payload["runtime_status_vocabulary"]["runtime_status_terms"]
    assert payload["degradation_taxonomy"]["schema_version"] == "1.0"
    assert payload["fail_behavior_registry"]["schema_version"] == "1.0"
    assert payload["provider_truth_table"]["schema_version"] == "1.0"
    providers = [row["provider"] for row in payload["provider_truth_table"]["providers"]]
    assert providers == ["ollama", "openai_compat", "lmstudio"]
    assert payload["state_transition_registry"]["schema_version"] == "1.0"
    transition_domains = [row["domain"] for row in payload["state_transition_registry"]["domains"]]
    assert transition_domains == ["session", "run", "tool_invocation", "voice", "ui"]
    assert payload["timeout_semantics_contract"]["schema_version"] == "1.0"
    timeout_surfaces = [row["surface"] for row in payload["timeout_semantics_contract"]["timeout_surfaces"]]
    assert timeout_surfaces == [
        "local_model_completion_timeout",
        "model_stream_provider_timeout",
        "model_stream_turn_timeout",
        "provider_runtime_inventory_timeout",
    ]
    assert payload["streaming_semantics_contract"]["schema_version"] == "1.0"
    assert payload["streaming_semantics_contract"]["terminal_events"] == ["error", "stopped"]
    assert payload["runtime_truth_contract_drift_report"]["schema_version"] == "1.0"
    assert payload["runtime_truth_contract_drift_report"]["ok"] is True
    assert payload["runtime_truth_trace_ids"]["schema_version"] == "1.0"
    trace_artifacts = [row["artifact"] for row in payload["runtime_truth_trace_ids"]["trace_ids"]]
    assert "run_phase_contract" in trace_artifacts
    assert "route_decision_artifact" in trace_artifacts
    assert payload["runtime_invariant_registry"]["schema_version"] == "1.0"
    invariant_ids = [row["invariant_id"] for row in payload["runtime_invariant_registry"]["invariants"]]
    assert "INV-001" in invariant_ids
    assert payload["runtime_config_ownership_map"]["schema_version"] == "1.0"
    config_keys = [row["config_key"] for row in payload["runtime_config_ownership_map"]["rows"]]
    assert "ORKET_STATE_BACKEND_MODE" in config_keys
    assert "ORKET_PROVIDER_QUARANTINE" in config_keys
    assert payload["unknown_input_policy"]["schema_version"] == "1.0"
    unknown_surfaces = [row["surface"] for row in payload["unknown_input_policy"]["surfaces"]]
    assert "provider_runtime_target.requested_provider" in unknown_surfaces
    assert payload["clock_time_authority_policy"]["schema_version"] == "1.0"
    assert payload["clock_time_authority_policy"]["defaults"]["clock_mode"] == "wall"
    assert payload["capability_fallback_hierarchy"]["schema_version"] == "1.0"
    assert payload["capability_fallback_hierarchy"]["fallback_hierarchy"]["streaming"][0]["provider"] == "ollama"
    assert payload["model_profile_bios"]["schema_version"] == "1.0"
    model_profile_ids = [row["profile_id"] for row in payload["model_profile_bios"]["profiles"]]
    assert "ollama-default" in model_profile_ids
    assert payload["interrupt_semantics_policy"]["schema_version"] == "1.0"
    interrupt_surfaces = [row["surface"] for row in payload["interrupt_semantics_policy"]["rows"]]
    assert "run_execution" in interrupt_surfaces
    assert payload["idempotency_discipline_policy"]["schema_version"] == "1.0"
    idempotency_surfaces = [row["surface"] for row in payload["idempotency_discipline_policy"]["rows"]]
    assert "run_finalize" in idempotency_surfaces
    assert payload["artifact_provenance_block_policy"]["schema_version"] == "1.0"
    required_provenance_fields = payload["artifact_provenance_block_policy"]["required_provenance_fields"]
    assert "run_id" in required_provenance_fields
    assert payload["operator_override_logging_policy"]["schema_version"] == "1.0"
    override_types = payload["operator_override_logging_policy"]["override_types"]
    assert "route_override" in override_types
    assert payload["demo_production_labeling_policy"]["schema_version"] == "1.0"
    demo_labels = payload["demo_production_labeling_policy"]["labels"]
    assert "production_verified" in demo_labels
    assert payload["human_correction_capture_policy"]["schema_version"] == "1.0"
    correction_target_surfaces = payload["human_correction_capture_policy"]["target_surfaces"]
    assert "route_decision" in correction_target_surfaces
    assert payload["sampling_discipline_guide"]["schema_version"] == "1.0"
    sampling_event_classes = [row["event_class"] for row in payload["sampling_discipline_guide"]["rows"]]
    assert "fallback_event" in sampling_event_classes
    assert payload["execution_readiness_rubric"]["schema_version"] == "1.0"
    readiness_criteria = [row["criterion"] for row in payload["execution_readiness_rubric"]["criteria"]]
    assert "contract_drift_clean" in readiness_criteria
    assert payload["release_confidence_scorecard"]["schema_version"] == "1.0"
    scorecard_dimensions = [row["name"] for row in payload["release_confidence_scorecard"]["dimensions"]]
    assert "correctness" in scorecard_dimensions
    assert payload["feature_flag_expiration_policy"]["schema_version"] == "1.0"
    expiration_fields = payload["feature_flag_expiration_policy"]["required_fields"]
    assert "flag_name" in expiration_fields
    assert payload["workspace_hygiene_rules"]["schema_version"] == "1.0"
    hygiene_rule_ids = [row["rule_id"] for row in payload["workspace_hygiene_rules"]["rules"]]
    assert "WSH-001" in hygiene_rule_ids
    assert payload["canonical_examples_library"]["schema_version"] == "1.0"
    canonical_example_ids = [row["example_id"] for row in payload["canonical_examples_library"]["examples"]]
    assert "EX-ROUTE-DECISION-BASELINE" in canonical_example_ids
    assert payload["spec_debt_queue"]["schema_version"] == "1.0"
    debt_ids = [row["debt_id"] for row in payload["spec_debt_queue"]["entries"]]
    assert "SDQ-001" in debt_ids
    assert payload["non_fatal_error_budget"]["schema_version"] == "1.0"
    budget_ids = [row["budget_id"] for row in payload["non_fatal_error_budget"]["budgets"]]
    assert "degraded_completion_ratio" in budget_ids
    assert payload["interface_freeze_windows"]["schema_version"] == "1.0"
    freeze_window_ids = [row["window_id"] for row in payload["interface_freeze_windows"]["windows"]]
    assert "pre_promotion_contract_freeze" in freeze_window_ids
    assert payload["evidence_package_generator_contract"]["schema_version"] == "1.0"
    required_sections = payload["evidence_package_generator_contract"]["required_sections"]
    assert "gate_summary" in required_sections
    assert payload["observability_redaction_test_contract"]["schema_version"] == "1.0"
    redaction_check_ids = [row["check_id"] for row in payload["observability_redaction_test_contract"]["checks"]]
    assert "env_secret_values_masked" in redaction_check_ids
    assert payload["trust_language_review_policy"]["schema_version"] == "1.0"
    trust_claims = [row["claim"] for row in payload["trust_language_review_policy"]["claims"]]
    assert "verified" in trust_claims
    assert payload["local_remote_route_policy"]["schema_version"] == "1.0"
    route_lanes = [row["route_lane"] for row in payload["local_remote_route_policy"]["lanes"]]
    assert "protocol_governed" in route_lanes
    assert payload["failure_replay_harness_contract"]["schema_version"] == "1.0"
    replay_required_outputs = payload["failure_replay_harness_contract"]["required_output_fields"]
    assert "drift" in replay_required_outputs
    assert payload["cold_start_truth_test_contract"]["schema_version"] == "1.0"
    cold_start_check_ids = [row["check_id"] for row in payload["cold_start_truth_test_contract"]["checks"]]
    assert "stub_cold_start_true_loading_payload" in cold_start_check_ids
    assert payload["promotion_rollback_criteria"]["schema_version"] == "1.0"
    rollback_triggers = [row["trigger"] for row in payload["promotion_rollback_criteria"]["triggers"]]
    assert "acceptance_gate_failure" in rollback_triggers
    assert Path(payload["run_identity_path"]).exists()
    assert Path(payload["run_phase_contract_path"]).exists()
    assert Path(payload["runtime_status_vocabulary_path"]).exists()
    assert Path(payload["degradation_taxonomy_path"]).exists()
    assert Path(payload["fail_behavior_registry_path"]).exists()
    assert Path(payload["provider_truth_table_path"]).exists()
    assert Path(payload["state_transition_registry_path"]).exists()
    assert Path(payload["timeout_semantics_contract_path"]).exists()
    assert Path(payload["streaming_semantics_contract_path"]).exists()
    assert Path(payload["runtime_truth_contract_drift_report_path"]).exists()
    assert Path(payload["runtime_truth_trace_ids_path"]).exists()
    assert Path(payload["runtime_invariant_registry_path"]).exists()
    assert Path(payload["runtime_config_ownership_map_path"]).exists()
    assert Path(payload["unknown_input_policy_path"]).exists()
    assert Path(payload["clock_time_authority_policy_path"]).exists()
    assert Path(payload["capability_fallback_hierarchy_path"]).exists()
    assert Path(payload["model_profile_bios_path"]).exists()
    assert Path(payload["interrupt_semantics_policy_path"]).exists()
    assert Path(payload["idempotency_discipline_policy_path"]).exists()
    assert Path(payload["artifact_provenance_block_policy_path"]).exists()
    assert Path(payload["operator_override_logging_policy_path"]).exists()
    assert Path(payload["demo_production_labeling_policy_path"]).exists()
    assert Path(payload["human_correction_capture_policy_path"]).exists()
    assert Path(payload["sampling_discipline_guide_path"]).exists()
    assert Path(payload["execution_readiness_rubric_path"]).exists()
    assert Path(payload["release_confidence_scorecard_path"]).exists()
    assert Path(payload["feature_flag_expiration_policy_path"]).exists()
    assert Path(payload["workspace_hygiene_rules_path"]).exists()
    assert Path(payload["canonical_examples_library_path"]).exists()
    assert Path(payload["spec_debt_queue_path"]).exists()
    assert Path(payload["non_fatal_error_budget_path"]).exists()
    assert Path(payload["interface_freeze_windows_path"]).exists()
    assert Path(payload["evidence_package_generator_contract_path"]).exists()
    assert Path(payload["observability_redaction_test_contract_path"]).exists()
    assert Path(payload["trust_language_review_policy_path"]).exists()
    assert Path(payload["local_remote_route_policy_path"]).exists()
    assert Path(payload["failure_replay_harness_contract_path"]).exists()
    assert Path(payload["cold_start_truth_test_contract_path"]).exists()
    assert Path(payload["promotion_rollback_criteria_path"]).exists()
    assert Path(payload["ledger_event_schema_path"]).exists()
    assert Path(payload["capability_manifest_schema_path"]).exists()
    assert Path(payload["capability_manifest_path"]).exists()
    assert Path(payload["compatibility_map_snapshot_path"]).exists()
    assert Path(payload["workspace_state_snapshot_path"]).exists()
    workspace_snapshot = payload["workspace_state_snapshot"]
    assert workspace_snapshot["workspace_type"] == "filesystem"
    assert workspace_snapshot["workspace_path"] == str(workspace.resolve())
    assert workspace_snapshot["file_count"] == 1
    assert len(str(workspace_snapshot["workspace_hash"])) == 64


# Layer: contract
def test_capture_run_start_artifacts_reuses_existing_run_identity_for_same_run(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    first = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    second = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 18, 0, 0, tzinfo=UTC),
    )

    assert first["run_identity"] == second["run_identity"]
    assert first["run_identity"]["start_time"].startswith("2026-03-06T17:00:00")


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_run_identity_workload_mismatch(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-mismatch",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )

    with pytest.raises(ValueError, match="E_RUN_IDENTITY_IMMUTABLE:workload_mismatch"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-mismatch",
            workload="other_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_run_phase_contract_mutation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-phase-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    run_phase_contract_path = (
        workspace
        / "observability"
        / "run-phase-immutable"
        / "runtime_contracts"
        / "run_phase_contract.json"
    )
    run_phase_contract_path.write_text(
        '{"schema_version":"999.0","entry_phase":"route","terminal_phase":"persist","canonical_phase_order":[]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_PHASE_CONTRACT_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-phase-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_runtime_status_vocabulary_mutation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-status-vocab-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    runtime_status_vocabulary_path = (
        workspace
        / "observability"
        / "run-status-vocab-immutable"
        / "runtime_contracts"
        / "runtime_status_vocabulary.json"
    )
    runtime_status_vocabulary_path.write_text(
        '{"schema_version":"999.0","runtime_status_terms":["running"]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_STATUS_VOCABULARY_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-status-vocab-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_provider_truth_table_mutation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-provider-truth-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    provider_truth_table_path = (
        workspace
        / "observability"
        / "run-provider-truth-immutable"
        / "runtime_contracts"
        / "provider_truth_table.json"
    )
    provider_truth_table_path.write_text(
        '{"schema_version":"999.0","providers":[]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_PROVIDER_TRUTH_TABLE_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-provider-truth-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_state_transition_registry_mutation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-state-transition-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    state_transition_registry_path = (
        workspace
        / "observability"
        / "run-state-transition-immutable"
        / "runtime_contracts"
        / "state_transition_registry.json"
    )
    state_transition_registry_path.write_text(
        '{"schema_version":"999.0","domains":[]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_STATE_TRANSITION_REGISTRY_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-state-transition-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_streaming_semantics_mutation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-streaming-semantics-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    streaming_semantics_path = (
        workspace
        / "observability"
        / "run-streaming-semantics-immutable"
        / "runtime_contracts"
        / "streaming_semantics_contract.json"
    )
    streaming_semantics_path.write_text(
        '{"schema_version":"999.0","event_trace_order":[],"terminal_events":[],"rules":[]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_STREAMING_SEMANTICS_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-streaming-semantics-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_clock_time_authority_policy_mutation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-clock-policy-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    clock_policy_path = (
        workspace
        / "observability"
        / "run-clock-policy-immutable"
        / "runtime_contracts"
        / "clock_time_authority_policy.json"
    )
    clock_policy_path.write_text(
        '{"schema_version":"999.0","defaults":{"clock_mode":"artifact_replay"}}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_CLOCK_TIME_AUTHORITY_POLICY_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-clock-policy-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_capability_fallback_hierarchy_mutation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-fallback-hierarchy-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    fallback_hierarchy_path = (
        workspace
        / "observability"
        / "run-fallback-hierarchy-immutable"
        / "runtime_contracts"
        / "capability_fallback_hierarchy.json"
    )
    fallback_hierarchy_path.write_text(
        '{"schema_version":"999.0","fallback_hierarchy":{}}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_CAPABILITY_FALLBACK_HIERARCHY_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-fallback-hierarchy-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_model_profile_bios_mutation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-model-profile-bios-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    model_profile_bios_path = (
        workspace
        / "observability"
        / "run-model-profile-bios-immutable"
        / "runtime_contracts"
        / "model_profile_bios.json"
    )
    model_profile_bios_path.write_text(
        '{"schema_version":"999.0","profiles":[]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_MODEL_PROFILE_BIOS_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-model-profile-bios-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_interrupt_semantics_policy_mutation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-interrupt-policy-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    interrupt_policy_path = (
        workspace
        / "observability"
        / "run-interrupt-policy-immutable"
        / "runtime_contracts"
        / "interrupt_semantics_policy.json"
    )
    interrupt_policy_path.write_text(
        '{"schema_version":"999.0","rows":[]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_INTERRUPT_SEMANTICS_POLICY_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-interrupt-policy-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_idempotency_discipline_policy_mutation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-idempotency-policy-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    idempotency_policy_path = (
        workspace
        / "observability"
        / "run-idempotency-policy-immutable"
        / "runtime_contracts"
        / "idempotency_discipline_policy.json"
    )
    idempotency_policy_path.write_text(
        '{"schema_version":"999.0","rows":[]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_IDEMPOTENCY_DISCIPLINE_POLICY_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-idempotency-policy-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_artifact_provenance_block_policy_mutation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-artifact-provenance-policy-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    provenance_policy_path = (
        workspace
        / "observability"
        / "run-artifact-provenance-policy-immutable"
        / "runtime_contracts"
        / "artifact_provenance_block_policy.json"
    )
    provenance_policy_path.write_text(
        '{"schema_version":"999.0","enforcement_mode":"strict_block","required_provenance_fields":[],"blocked_artifact_types_when_missing":[],"exemptions":[]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_ARTIFACT_PROVENANCE_BLOCK_POLICY_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-artifact-provenance-policy-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_operator_override_logging_policy_mutation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-operator-override-policy-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    override_policy_path = (
        workspace
        / "observability"
        / "run-operator-override-policy-immutable"
        / "runtime_contracts"
        / "operator_override_logging_policy.json"
    )
    override_policy_path.write_text(
        '{"schema_version":"999.0","required_fields":[],"override_types":[],"persistence":{}}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_OPERATOR_OVERRIDE_LOGGING_POLICY_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-operator-override-policy-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_demo_production_labeling_policy_mutation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-demo-production-policy-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    demo_policy_path = (
        workspace
        / "observability"
        / "run-demo-production-policy-immutable"
        / "runtime_contracts"
        / "demo_production_labeling_policy.json"
    )
    demo_policy_path.write_text(
        '{"schema_version":"999.0","labels":[],"surfaces":[],"rules":[]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_DEMO_PRODUCTION_LABELING_POLICY_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-demo-production-policy-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_human_correction_capture_policy_mutation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-human-correction-policy-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    correction_policy_path = (
        workspace
        / "observability"
        / "run-human-correction-policy-immutable"
        / "runtime_contracts"
        / "human_correction_capture_policy.json"
    )
    correction_policy_path.write_text(
        '{"schema_version":"999.0","required_fields":[],"target_surfaces":[],"persistence":{}}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_HUMAN_CORRECTION_CAPTURE_POLICY_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-human-correction-policy-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_sampling_discipline_guide_mutation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-sampling-discipline-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    sampling_guide_path = (
        workspace
        / "observability"
        / "run-sampling-discipline-immutable"
        / "runtime_contracts"
        / "sampling_discipline_guide.json"
    )
    sampling_guide_path.write_text(
        '{"schema_version":"999.0","rows":[]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_SAMPLING_DISCIPLINE_GUIDE_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-sampling-discipline-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_execution_readiness_rubric_mutation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-execution-readiness-rubric-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    readiness_rubric_path = (
        workspace
        / "observability"
        / "run-execution-readiness-rubric-immutable"
        / "runtime_contracts"
        / "execution_readiness_rubric.json"
    )
    readiness_rubric_path.write_text(
        '{"schema_version":"999.0","minimum_score":0.0,"criteria":[]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_EXECUTION_READINESS_RUBRIC_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-execution-readiness-rubric-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_release_confidence_scorecard_mutation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-release-confidence-scorecard-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    scorecard_path = (
        workspace
        / "observability"
        / "run-release-confidence-scorecard-immutable"
        / "runtime_contracts"
        / "release_confidence_scorecard.json"
    )
    scorecard_path.write_text(
        '{"schema_version":"999.0","promotion_threshold":0.0,"dimensions":[]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_RELEASE_CONFIDENCE_SCORECARD_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-release-confidence-scorecard-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_feature_flag_expiration_policy_mutation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-feature-flag-expiration-policy-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    expiration_policy_path = (
        workspace
        / "observability"
        / "run-feature-flag-expiration-policy-immutable"
        / "runtime_contracts"
        / "feature_flag_expiration_policy.json"
    )
    expiration_policy_path.write_text(
        '{"schema_version":"999.0","enforcement_mode":"block_on_expired","required_fields":[],"max_default_ttl_days":0}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_FEATURE_FLAG_EXPIRATION_POLICY_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-feature-flag-expiration-policy-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_workspace_hygiene_rules_mutation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-workspace-hygiene-rules-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    hygiene_rules_path = (
        workspace
        / "observability"
        / "run-workspace-hygiene-rules-immutable"
        / "runtime_contracts"
        / "workspace_hygiene_rules.json"
    )
    hygiene_rules_path.write_text(
        '{"schema_version":"999.0","rules":[]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_WORKSPACE_HYGIENE_RULES_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-workspace-hygiene-rules-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_canonical_examples_library_mutation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-canonical-examples-library-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    canonical_examples_path = (
        workspace
        / "observability"
        / "run-canonical-examples-library-immutable"
        / "runtime_contracts"
        / "canonical_examples_library.json"
    )
    canonical_examples_path.write_text(
        '{"schema_version":"999.0","examples":[]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_CANONICAL_EXAMPLES_LIBRARY_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-canonical-examples-library-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_spec_debt_queue_mutation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-spec-debt-queue-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    spec_debt_queue_path = (
        workspace
        / "observability"
        / "run-spec-debt-queue-immutable"
        / "runtime_contracts"
        / "spec_debt_queue.json"
    )
    spec_debt_queue_path.write_text(
        '{"schema_version":"999.0","entries":[]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_SPEC_DEBT_QUEUE_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-spec-debt-queue-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_promotion_rollback_criteria_mutation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-promotion-rollback-criteria-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    rollback_criteria_path = (
        workspace
        / "observability"
        / "run-promotion-rollback-criteria-immutable"
        / "runtime_contracts"
        / "promotion_rollback_criteria.json"
    )
    rollback_criteria_path.write_text(
        '{"schema_version":"999.0","triggers":[]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_PROMOTION_ROLLBACK_CRITERIA_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-promotion-rollback-criteria-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_truth_contract_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    monkeypatch.setattr(
        run_start_contract_artifacts,
        "runtime_truth_contract_drift_report",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "checks": [
                {
                    "check": "provider_truth_table_vs_provider_choices",
                    "ok": False,
                }
            ],
        },
    )
    with pytest.raises(ValueError, match="E_RUN_TRUTH_CONTRACT_DRIFT"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-truth-drift",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
        )
