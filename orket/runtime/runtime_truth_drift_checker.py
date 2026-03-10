from __future__ import annotations

from typing import Any

from orket.runtime.capability_fallback_hierarchy import validate_capability_fallback_hierarchy
from orket.runtime.canonical_examples_library import validate_canonical_examples_library
from orket.runtime.clock_time_authority_policy import validate_clock_time_authority_policy
from orket.runtime.artifact_provenance_block_policy import validate_artifact_provenance_block_policy
from orket.runtime.demo_production_labeling_policy import validate_demo_production_labeling_policy
from orket.runtime.execution_readiness_rubric import validate_execution_readiness_rubric
from orket.runtime.feature_flag_expiration_policy import validate_feature_flag_expiration_policy
from orket.runtime.human_correction_capture_policy import validate_human_correction_capture_policy
from orket.runtime.idempotency_discipline_policy import validate_idempotency_discipline_policy
from orket.runtime.interrupt_semantics_policy import validate_interrupt_semantics_policy
from orket.runtime.model_profile_bios import validate_model_profile_bios
from orket.runtime.operator_override_logging_policy import validate_operator_override_logging_policy
from orket.runtime.promotion_rollback_criteria import validate_promotion_rollback_criteria
from orket.runtime.release_confidence_scorecard import validate_release_confidence_scorecard
from orket.runtime.sampling_discipline_guide import validate_sampling_discipline_guide
from orket.runtime.spec_debt_queue import validate_spec_debt_queue
from orket.runtime.workspace_hygiene_rules import validate_workspace_hygiene_rules
from orket.runtime.provider_runtime_target import PROVIDER_CHOICES
from orket.runtime.runtime_boundary_audit_checklist import validate_runtime_boundary_audit_checklist
from orket.runtime.runtime_config_ownership_map import validate_runtime_config_ownership_map
from orket.runtime.retry_classification_policy import validate_retry_classification_policy
from orket.runtime.safe_default_catalog import validate_safe_default_catalog
from orket.runtime.structured_warning_policy import validate_structured_warning_policy
from orket.runtime.provider_truth_table import provider_truth_table_snapshot
from orket.runtime.run_phase_contract import CANONICAL_RUN_PHASE_ORDER
from orket.runtime.runtime_truth_contracts import runtime_status_vocabulary_snapshot
from orket.runtime.unknown_input_policy import unknown_input_policy_snapshot
from orket.runtime.state_transition_registry import state_transition_registry_snapshot
from orket.runtime.timeout_streaming_contracts import (
    streaming_semantics_snapshot,
    timeout_semantics_snapshot,
)


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
        str(token).strip().lower()
        for token in status_snapshot.get("runtime_status_terms", [])
        if str(token).strip()
    }
    transition_snapshot = state_transition_registry_snapshot()
    session_states: set[str] = set()
    run_states: set[str] = set()
    for row in transition_snapshot.get("domains", []):
        if not isinstance(row, dict):
            continue
        domain = str(row.get("domain") or "").strip().lower()
        states = {
            str(token).strip().lower()
            for token in row.get("states", [])
            if str(token).strip()
        }
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
