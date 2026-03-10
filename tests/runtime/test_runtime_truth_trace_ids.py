from __future__ import annotations

import pytest

from orket.runtime.runtime_truth_trace_ids import (
    resolve_runtime_truth_trace_id,
    runtime_truth_trace_ids_snapshot,
)


# Layer: unit
def test_runtime_truth_trace_ids_snapshot_contains_expected_rows() -> None:
    payload = runtime_truth_trace_ids_snapshot()
    assert payload["schema_version"] == "1.0"
    artifacts = {row["artifact"] for row in payload["trace_ids"]}
    assert "run_phase_contract" in artifacts
    assert "runtime_truth_contract_drift_report" in artifacts
    assert "clock_time_authority_policy" in artifacts
    assert "capability_fallback_hierarchy" in artifacts
    assert "model_profile_bios" in artifacts
    assert "interrupt_semantics_policy" in artifacts
    assert "idempotency_discipline_policy" in artifacts
    assert "result_error_invariant_contract" in artifacts
    assert "artifact_provenance_block_policy" in artifacts
    assert "operator_override_logging_policy" in artifacts
    assert "demo_production_labeling_policy" in artifacts
    assert "human_correction_capture_policy" in artifacts
    assert "sampling_discipline_guide" in artifacts
    assert "execution_readiness_rubric" in artifacts
    assert "release_confidence_scorecard" in artifacts
    assert "feature_flag_expiration_policy" in artifacts
    assert "workspace_hygiene_rules" in artifacts
    assert "canonical_examples_library" in artifacts
    assert "spec_debt_queue" in artifacts
    assert "non_fatal_error_budget" in artifacts
    assert "interface_freeze_windows" in artifacts
    assert "evidence_package_generator_contract" in artifacts
    assert "observability_redaction_test_contract" in artifacts
    assert "trust_language_review_policy" in artifacts
    assert "local_remote_route_policy" in artifacts
    assert "failure_replay_harness_contract" in artifacts
    assert "cold_start_truth_test_contract" in artifacts
    assert "naming_discipline_policy" in artifacts
    assert "promotion_rollback_criteria" in artifacts
    assert "route_decision_artifact" in artifacts


# Layer: contract
def test_resolve_runtime_truth_trace_id_returns_registered_id() -> None:
    assert resolve_runtime_truth_trace_id("run_phase_contract") == "TRUTH-A-RUN-PHASE-CONTRACT"


# Layer: contract
def test_resolve_runtime_truth_trace_id_rejects_unknown_artifact() -> None:
    with pytest.raises(ValueError, match="E_RUNTIME_TRUTH_TRACE_ID_UNKNOWN:unknown_artifact"):
        _ = resolve_runtime_truth_trace_id("unknown_artifact")
