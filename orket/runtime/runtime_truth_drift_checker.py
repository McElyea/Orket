from __future__ import annotations

from typing import Any

from orket.runtime.artifact_provenance_block_policy import validate_artifact_provenance_block_policy
from orket.runtime.canonical_examples_library import validate_canonical_examples_library
from orket.runtime.capability_fallback_hierarchy import validate_capability_fallback_hierarchy
from orket.runtime.clock_time_authority_policy import validate_clock_time_authority_policy
from orket.runtime.cold_start_truth_test_contract import validate_cold_start_truth_test_contract
from orket.runtime.conformance_governance_contract import validate_conformance_governance_contract
from orket.runtime.decision_record_operating_principles_contract import (
    validate_decision_record_operating_principles_contract,
)
from orket.runtime.degradation_first_ui_standard import validate_degradation_first_ui_standard
from orket.runtime.demo_production_labeling_policy import validate_demo_production_labeling_policy
from orket.runtime.evidence_package_generator_contract import validate_evidence_package_generator_contract
from orket.runtime.execution_readiness_rubric import validate_execution_readiness_rubric
from orket.runtime.failure_replay_harness_contract import validate_failure_replay_harness_contract
from orket.runtime.feature_flag_expiration_policy import validate_feature_flag_expiration_policy
from orket.runtime.human_correction_capture_policy import validate_human_correction_capture_policy
from orket.runtime.idempotency_discipline_policy import validate_idempotency_discipline_policy
from orket.runtime.interface_freeze_windows import validate_interface_freeze_windows
from orket.runtime.interrupt_semantics_policy import validate_interrupt_semantics_policy
from orket.runtime.local_remote_route_policy import validate_local_remote_route_policy
from orket.runtime.long_session_soak_test_contract import validate_long_session_soak_test_contract
from orket.runtime.model_profile_bios import validate_model_profile_bios
from orket.runtime.naming_discipline_policy import validate_naming_discipline_policy
from orket.runtime.narration_effect_audit_policy import validate_narration_effect_audit_policy
from orket.runtime.non_fatal_error_budget import validate_non_fatal_error_budget
from orket.runtime.observability_redaction_test_contract import validate_observability_redaction_test_contract
from orket.runtime.operator_override_logging_policy import validate_operator_override_logging_policy
from orket.runtime.persistence_corruption_test_contract import validate_persistence_corruption_test_contract
from orket.runtime.promotion_rollback_criteria import validate_promotion_rollback_criteria
from orket.runtime.provider_quarantine_policy_contract import validate_provider_quarantine_policy_contract
from orket.runtime.provider_runtime_target import PROVIDER_CHOICES
from orket.runtime.provider_truth_table import provider_truth_table_snapshot
from orket.runtime.release_confidence_scorecard import validate_release_confidence_scorecard
from orket.runtime.resource_pressure_simulation_lane import validate_resource_pressure_simulation_lane
from orket.runtime.result_error_invariants import validate_result_error_invariant_contract
from orket.runtime.retry_classification_policy import validate_retry_classification_policy
from orket.runtime.run_phase_contract import CANONICAL_RUN_PHASE_ORDER
from orket.runtime.runtime_boundary_audit_checklist import validate_runtime_boundary_audit_checklist
from orket.runtime.runtime_config_ownership_map import validate_runtime_config_ownership_map
from orket.runtime.runtime_invariant_registry import runtime_invariant_registry_snapshot
from orket.runtime.runtime_truth_contracts import (
    degradation_taxonomy_snapshot,
    fail_behavior_registry_snapshot,
    runtime_status_vocabulary_snapshot,
    validate_degradation_taxonomy_contract,
    validate_fail_behavior_registry_contract,
    validate_runtime_status_vocabulary_contract,
)
from orket.runtime.safe_default_catalog import validate_safe_default_catalog
from orket.runtime.sampling_discipline_guide import validate_sampling_discipline_guide
from orket.runtime.source_attribution_policy import validate_source_attribution_policy
from orket.runtime.spec_debt_queue import validate_spec_debt_queue
from orket.runtime.state_transition_registry import state_transition_registry_snapshot
from orket.runtime.structured_warning_policy import validate_structured_warning_policy
from orket.runtime.timeout_streaming_contracts import (
    streaming_semantics_snapshot,
    timeout_semantics_snapshot,
)
from orket.runtime.trust_language_review_policy import validate_trust_language_review_policy
from orket.runtime.ui_lane_security_boundary_test_contract import validate_ui_lane_security_boundary_test_contract
from orket.runtime.unknown_input_policy import unknown_input_policy_snapshot, validate_unknown_input_policy
from orket.runtime.workspace_hygiene_rules import validate_workspace_hygiene_rules


def runtime_truth_contract_drift_report() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    provider_snapshot = provider_truth_table_snapshot()
    provider_names = {
        str(row.get("provider") or "").strip().lower()
        for row in provider_snapshot.get("providers", [])
        if isinstance(row, dict)
    }
    provider_choices = {str(token).strip().lower() for token in PROVIDER_CHOICES}
    checks.append(
        {
            "check": "provider_truth_table_vs_provider_choices",
            "ok": provider_names == provider_choices,
            "expected": sorted(provider_choices),
            "observed": sorted(provider_names),
        }
    )

    status_snapshot = runtime_status_vocabulary_snapshot()
    status_terms = {
        str(token).strip().lower() for token in status_snapshot.get("runtime_status_terms", []) if str(token).strip()
    }
    transition_snapshot = state_transition_registry_snapshot()
    session_states: set[str] = set()
    run_states: set[str] = set()
    for row in transition_snapshot.get("domains", []):
        if not isinstance(row, dict):
            continue
        domain = str(row.get("domain") or "").strip().lower()
        states = {str(token).strip().lower() for token in row.get("states", []) if str(token).strip()}
        if domain == "session":
            session_states = states
        if domain == "run":
            run_states = states
    checks.append(
        {
            "check": "status_vocabulary_in_session_and_run_states",
            "ok": status_terms.issubset(session_states) and status_terms.issubset(run_states),
            "status_terms": sorted(status_terms),
            "session_states": sorted(session_states),
            "run_states": sorted(run_states),
        }
    )

    try:
        validated_terms = validate_runtime_status_vocabulary_contract(status_snapshot)
        checks.append(
            {
                "check": "runtime_status_vocabulary_contract_valid",
                "ok": True,
                "count": len(validated_terms),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "runtime_status_vocabulary_contract_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    degradation_snapshot = degradation_taxonomy_snapshot()
    try:
        levels = validate_degradation_taxonomy_contract(degradation_snapshot)
        checks.append(
            {
                "check": "degradation_taxonomy_contract_valid",
                "ok": True,
                "count": len(levels),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "degradation_taxonomy_contract_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    fail_behavior_snapshot = fail_behavior_registry_snapshot()
    try:
        subsystems = validate_fail_behavior_registry_contract(fail_behavior_snapshot)
        checks.append(
            {
                "check": "fail_behavior_registry_contract_valid",
                "ok": True,
                "count": len(subsystems),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "fail_behavior_registry_contract_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    checks.append(
        {
            "check": "canonical_run_phase_entry_and_terminal",
            "ok": bool(CANONICAL_RUN_PHASE_ORDER)
            and CANONICAL_RUN_PHASE_ORDER[0] == "input_normalize"
            and CANONICAL_RUN_PHASE_ORDER[-1] == "emit_observability",
            "observed": list(CANONICAL_RUN_PHASE_ORDER),
        }
    )

    timeout_snapshot = timeout_semantics_snapshot()
    timeout_surfaces = timeout_snapshot.get("timeout_surfaces", [])
    checks.append(
        {
            "check": "timeout_semantics_non_empty",
            "ok": isinstance(timeout_surfaces, list) and len(timeout_surfaces) >= 1,
            "count": len(timeout_surfaces) if isinstance(timeout_surfaces, list) else 0,
        }
    )

    streaming_snapshot = streaming_semantics_snapshot()
    terminal_events = list(streaming_snapshot.get("terminal_events", []))
    checks.append(
        {
            "check": "streaming_semantics_terminal_events",
            "ok": sorted(terminal_events) == ["error", "stopped"],
            "observed": sorted(terminal_events),
        }
    )

    unknown_input_policy = unknown_input_policy_snapshot()
    surfaces = list(unknown_input_policy.get("surfaces", []))
    provider_surface = next(
        (
            row
            for row in surfaces
            if isinstance(row, dict)
            and str(row.get("surface") or "").strip() == "provider_runtime_target.requested_provider"
        ),
        None,
    )
    checks.append(
        {
            "check": "unknown_input_policy_provider_surface",
            "ok": isinstance(provider_surface, dict)
            and str(provider_surface.get("on_unknown") or "").strip() == "fail_closed"
            and str(provider_surface.get("error_code") or "").strip() == "E_UNKNOWN_PROVIDER_INPUT",
        }
    )

    try:
        surfaces = validate_unknown_input_policy(unknown_input_policy)
        checks.append(
            {
                "check": "unknown_input_policy_contract_valid",
                "ok": True,
                "count": len(surfaces),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "unknown_input_policy_contract_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        config_keys = list(validate_runtime_config_ownership_map())
        checks.append(
            {
                "check": "runtime_config_ownership_map_valid",
                "ok": True,
                "count": len(config_keys),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "runtime_config_ownership_map_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        invariant_snapshot = runtime_invariant_registry_snapshot()
        invariant_count = len(list(invariant_snapshot.get("invariants") or []))
        checks.append(
            {
                "check": "runtime_invariant_registry_snapshot_valid",
                "ok": invariant_count >= 1,
                "count": invariant_count,
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "runtime_invariant_registry_snapshot_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        clock_policy = validate_clock_time_authority_policy()
        checks.append(
            {
                "check": "clock_time_authority_policy_valid",
                "ok": True,
                "defaults": dict(clock_policy.get("defaults") or {}),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "clock_time_authority_policy_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        env_keys = validate_provider_quarantine_policy_contract()
        checks.append(
            {
                "check": "provider_quarantine_policy_contract_valid",
                "ok": True,
                "count": len(env_keys),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "provider_quarantine_policy_contract_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        fallback_hierarchy = validate_capability_fallback_hierarchy()
        checks.append(
            {
                "check": "capability_fallback_hierarchy_valid",
                "ok": True,
                "capability_count": len(dict(fallback_hierarchy.get("fallback_hierarchy") or {})),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "capability_fallback_hierarchy_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        keys = validate_safe_default_catalog()
        checks.append(
            {
                "check": "safe_default_catalog_valid",
                "ok": True,
                "count": len(keys),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "safe_default_catalog_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        warning_codes = validate_structured_warning_policy()
        checks.append(
            {
                "check": "structured_warning_policy_valid",
                "ok": True,
                "count": len(warning_codes),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "structured_warning_policy_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        signals = validate_retry_classification_policy()
        checks.append(
            {
                "check": "retry_classification_policy_valid",
                "ok": True,
                "count": len(signals),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "retry_classification_policy_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        statuses = validate_result_error_invariant_contract()
        checks.append(
            {
                "check": "result_error_invariant_contract_valid",
                "ok": True,
                "count": len(statuses),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "result_error_invariant_contract_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        boundary_ids = validate_runtime_boundary_audit_checklist()
        checks.append(
            {
                "check": "runtime_boundary_audit_checklist_valid",
                "ok": True,
                "count": len(boundary_ids),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "runtime_boundary_audit_checklist_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        profile_ids = validate_model_profile_bios()
        checks.append(
            {
                "check": "model_profile_bios_valid",
                "ok": True,
                "count": len(profile_ids),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "model_profile_bios_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        surfaces = validate_interrupt_semantics_policy()
        checks.append(
            {
                "check": "interrupt_semantics_policy_valid",
                "ok": True,
                "count": len(surfaces),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "interrupt_semantics_policy_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        surfaces = validate_idempotency_discipline_policy()
        checks.append(
            {
                "check": "idempotency_discipline_policy_valid",
                "ok": True,
                "count": len(surfaces),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "idempotency_discipline_policy_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        required_fields = validate_artifact_provenance_block_policy()
        checks.append(
            {
                "check": "artifact_provenance_block_policy_valid",
                "ok": True,
                "count": len(required_fields),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "artifact_provenance_block_policy_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        tools = validate_narration_effect_audit_policy()
        checks.append(
            {
                "check": "narration_effect_audit_policy_valid",
                "ok": True,
                "count": len(tools),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "narration_effect_audit_policy_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        modes = validate_source_attribution_policy()
        checks.append(
            {
                "check": "source_attribution_policy_valid",
                "ok": True,
                "count": len(modes),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "source_attribution_policy_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        override_types = validate_operator_override_logging_policy()
        checks.append(
            {
                "check": "operator_override_logging_policy_valid",
                "ok": True,
                "count": len(override_types),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "operator_override_logging_policy_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        labels = validate_demo_production_labeling_policy()
        checks.append(
            {
                "check": "demo_production_labeling_policy_valid",
                "ok": True,
                "count": len(labels),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "demo_production_labeling_policy_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        target_surfaces = validate_human_correction_capture_policy()
        checks.append(
            {
                "check": "human_correction_capture_policy_valid",
                "ok": True,
                "count": len(target_surfaces),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "human_correction_capture_policy_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        event_classes = validate_sampling_discipline_guide()
        checks.append(
            {
                "check": "sampling_discipline_guide_valid",
                "ok": True,
                "count": len(event_classes),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "sampling_discipline_guide_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        criteria = validate_execution_readiness_rubric()
        checks.append(
            {
                "check": "execution_readiness_rubric_valid",
                "ok": True,
                "count": len(criteria),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "execution_readiness_rubric_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        dimensions = validate_release_confidence_scorecard()
        checks.append(
            {
                "check": "release_confidence_scorecard_valid",
                "ok": True,
                "count": len(dimensions),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "release_confidence_scorecard_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        required_fields = validate_feature_flag_expiration_policy()
        checks.append(
            {
                "check": "feature_flag_expiration_policy_valid",
                "ok": True,
                "count": len(required_fields),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "feature_flag_expiration_policy_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        rule_ids = validate_workspace_hygiene_rules()
        checks.append(
            {
                "check": "workspace_hygiene_rules_valid",
                "ok": True,
                "count": len(rule_ids),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "workspace_hygiene_rules_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        example_ids = validate_canonical_examples_library()
        checks.append(
            {
                "check": "canonical_examples_library_valid",
                "ok": True,
                "count": len(example_ids),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "canonical_examples_library_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        debt_ids = validate_spec_debt_queue()
        checks.append(
            {
                "check": "spec_debt_queue_valid",
                "ok": True,
                "count": len(debt_ids),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "spec_debt_queue_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        budget_ids = validate_non_fatal_error_budget()
        checks.append(
            {
                "check": "non_fatal_error_budget_valid",
                "ok": True,
                "count": len(budget_ids),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "non_fatal_error_budget_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        window_ids = validate_interface_freeze_windows()
        checks.append(
            {
                "check": "interface_freeze_windows_valid",
                "ok": True,
                "count": len(window_ids),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "interface_freeze_windows_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        required_sections = validate_evidence_package_generator_contract()
        checks.append(
            {
                "check": "evidence_package_generator_contract_valid",
                "ok": True,
                "count": len(required_sections),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "evidence_package_generator_contract_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        section_ids = validate_conformance_governance_contract()
        checks.append(
            {
                "check": "conformance_governance_contract_valid",
                "ok": True,
                "count": len(section_ids),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "conformance_governance_contract_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        check_ids = validate_observability_redaction_test_contract()
        checks.append(
            {
                "check": "observability_redaction_test_contract_valid",
                "ok": True,
                "count": len(check_ids),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "observability_redaction_test_contract_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        claims = validate_trust_language_review_policy()
        checks.append(
            {
                "check": "trust_language_review_policy_valid",
                "ok": True,
                "count": len(claims),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "trust_language_review_policy_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        lanes = validate_local_remote_route_policy()
        checks.append(
            {
                "check": "local_remote_route_policy_valid",
                "ok": True,
                "count": len(lanes),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "local_remote_route_policy_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        required_output_fields = validate_failure_replay_harness_contract()
        checks.append(
            {
                "check": "failure_replay_harness_contract_valid",
                "ok": True,
                "count": len(required_output_fields),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "failure_replay_harness_contract_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        check_ids = validate_cold_start_truth_test_contract()
        checks.append(
            {
                "check": "cold_start_truth_test_contract_valid",
                "ok": True,
                "count": len(check_ids),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "cold_start_truth_test_contract_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        check_ids = validate_persistence_corruption_test_contract()
        checks.append(
            {
                "check": "persistence_corruption_test_contract_valid",
                "ok": True,
                "count": len(check_ids),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "persistence_corruption_test_contract_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        check_ids = validate_long_session_soak_test_contract()
        checks.append(
            {
                "check": "long_session_soak_test_contract_valid",
                "ok": True,
                "count": len(check_ids),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "long_session_soak_test_contract_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        check_ids = validate_resource_pressure_simulation_lane()
        checks.append(
            {
                "check": "resource_pressure_simulation_lane_valid",
                "ok": True,
                "count": len(check_ids),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "resource_pressure_simulation_lane_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        check_ids = validate_ui_lane_security_boundary_test_contract()
        checks.append(
            {
                "check": "ui_lane_security_boundary_test_contract_valid",
                "ok": True,
                "count": len(check_ids),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "ui_lane_security_boundary_test_contract_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        check_ids = validate_degradation_first_ui_standard()
        checks.append(
            {
                "check": "degradation_first_ui_standard_valid",
                "ok": True,
                "count": len(check_ids),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "degradation_first_ui_standard_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        check_ids = validate_decision_record_operating_principles_contract()
        checks.append(
            {
                "check": "decision_record_operating_principles_contract_valid",
                "ok": True,
                "count": len(check_ids),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "decision_record_operating_principles_contract_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        conventions = validate_naming_discipline_policy()
        checks.append(
            {
                "check": "naming_discipline_policy_valid",
                "ok": True,
                "count": len(conventions),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "naming_discipline_policy_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    try:
        triggers = validate_promotion_rollback_criteria()
        checks.append(
            {
                "check": "promotion_rollback_criteria_valid",
                "ok": True,
                "count": len(triggers),
            }
        )
    except ValueError as exc:
        checks.append(
            {
                "check": "promotion_rollback_criteria_valid",
                "ok": False,
                "error": str(exc),
            }
        )

    return {
        "schema_version": "1.0",
        "ok": all(bool(check.get("ok")) for check in checks),
        "checks": checks,
    }


def assert_no_runtime_truth_contract_drift() -> dict[str, Any]:
    report = runtime_truth_contract_drift_report()
    if bool(report.get("ok")):
        return report
    failing = [str(row.get("check") or "unknown") for row in report.get("checks", []) if not bool(row.get("ok"))]
    raise ValueError(f"E_RUNTIME_TRUTH_CONTRACT_DRIFT:{','.join(failing)}")
