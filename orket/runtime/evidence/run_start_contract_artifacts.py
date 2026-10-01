from __future__ import annotations

from collections.abc import Callable
from typing import Any

from orket.core.contracts.result_error_invariants import result_error_invariant_contract_snapshot
from orket.runtime.config import model_profile_bios, provider_truth_table
from orket.runtime.evidence.artifact_provenance_block_policy import artifact_provenance_block_policy_snapshot
from orket.runtime.evidence.evidence_package_generator_contract import evidence_package_generator_contract_snapshot
from orket.runtime.evidence.failure_replay_harness_contract import failure_replay_harness_contract_snapshot
from orket.runtime.evidence.run_start_schema_payloads import (
    _capability_manifest_schema_payload,
    _ledger_event_schema_payload,
)
from orket.runtime.policy import (
    canonical_examples_library,
    capability_fallback_hierarchy,
    clock_time_authority_policy,
    cold_start_truth_test_contract,
    conformance_governance_contract,
    decision_record_operating_principles_contract,
    degradation_first_ui_standard,
    demo_production_labeling_policy,
    execution_readiness_rubric,
    feature_flag_expiration_policy,
    human_correction_capture_policy,
    idempotency_discipline_policy,
    interface_freeze_windows,
    interrupt_semantics_policy,
    local_remote_route_policy,
    long_session_soak_test_contract,
    naming_discipline_policy,
    narration_effect_audit_policy,
    non_fatal_error_budget,
    observability_redaction_test_contract,
    operator_override_logging_policy,
    persistence_corruption_test_contract,
    promotion_rollback_criteria,
    provider_quarantine_policy_contract,
    resource_pressure_simulation_lane,
    run_phase_contract,
    runtime_boundary_audit_checklist,
    runtime_config_ownership_map,
    runtime_truth_contracts,
    runtime_truth_drift_checker,
    safe_default_catalog,
    sampling_discipline_guide,
    timeout_streaming_contracts,
    ui_lane_security_boundary_test_contract,
    unknown_input_policy,
)
from orket.runtime.policy import retry_classification_policy as _retry_classification_policy
from orket.runtime.policy import source_attribution_policy as _source_attribution_policy
from orket.runtime.policy import trust_language_review_policy as _trust_language_review_policy
from orket.runtime.policy import workspace_hygiene_rules as _workspace_hygiene_rules
from orket.runtime.registry import runtime_invariant_registry, runtime_truth_trace_ids, state_transition_registry
from orket.runtime.summary import release_confidence_scorecard

# Capture callables at import time, preserving consumer-local monkeypatch targets.
canonical_examples_library_snapshot = canonical_examples_library.canonical_examples_library_snapshot
capability_fallback_hierarchy_snapshot = capability_fallback_hierarchy.capability_fallback_hierarchy_snapshot
clock_time_authority_policy_snapshot = clock_time_authority_policy.clock_time_authority_policy_snapshot
cold_start_truth_test_contract_snapshot = cold_start_truth_test_contract.cold_start_truth_test_contract_snapshot
conformance_governance_contract_snapshot = conformance_governance_contract.conformance_governance_contract_snapshot
decision_record_operating_principles_contract_snapshot = decision_record_operating_principles_contract.decision_record_operating_principles_contract_snapshot
degradation_first_ui_standard_snapshot = degradation_first_ui_standard.degradation_first_ui_standard_snapshot
demo_production_labeling_policy_snapshot = demo_production_labeling_policy.demo_production_labeling_policy_snapshot
execution_readiness_rubric_snapshot = execution_readiness_rubric.execution_readiness_rubric_snapshot
feature_flag_expiration_policy_snapshot = feature_flag_expiration_policy.feature_flag_expiration_policy_snapshot
human_correction_capture_policy_snapshot = human_correction_capture_policy.human_correction_capture_policy_snapshot
idempotency_discipline_policy_snapshot = idempotency_discipline_policy.idempotency_discipline_policy_snapshot
interface_freeze_windows_snapshot = interface_freeze_windows.interface_freeze_windows_snapshot
interrupt_semantics_policy_snapshot = interrupt_semantics_policy.interrupt_semantics_policy_snapshot
local_remote_route_policy_snapshot = local_remote_route_policy.local_remote_route_policy_snapshot
long_session_soak_test_contract_snapshot = long_session_soak_test_contract.long_session_soak_test_contract_snapshot
model_profile_bios_snapshot = model_profile_bios.model_profile_bios_snapshot
naming_discipline_policy_snapshot = naming_discipline_policy.naming_discipline_policy_snapshot
narration_effect_audit_policy_snapshot = narration_effect_audit_policy.narration_effect_audit_policy_snapshot
non_fatal_error_budget_snapshot = non_fatal_error_budget.non_fatal_error_budget_snapshot
observability_redaction_test_contract_snapshot = observability_redaction_test_contract.observability_redaction_test_contract_snapshot
operator_override_logging_policy_snapshot = operator_override_logging_policy.operator_override_logging_policy_snapshot
persistence_corruption_test_contract_snapshot = persistence_corruption_test_contract.persistence_corruption_test_contract_snapshot
promotion_rollback_criteria_snapshot = promotion_rollback_criteria.promotion_rollback_criteria_snapshot
provider_quarantine_policy_contract_snapshot = provider_quarantine_policy_contract.provider_quarantine_policy_contract_snapshot
provider_truth_table_snapshot = provider_truth_table.provider_truth_table_snapshot
release_confidence_scorecard_snapshot = release_confidence_scorecard.release_confidence_scorecard_snapshot
resource_pressure_simulation_lane_snapshot = resource_pressure_simulation_lane.resource_pressure_simulation_lane_snapshot
run_phase_contract_snapshot = run_phase_contract.run_phase_contract_snapshot
runtime_boundary_audit_checklist_snapshot = runtime_boundary_audit_checklist.runtime_boundary_audit_checklist_snapshot
runtime_config_ownership_map_snapshot = runtime_config_ownership_map.runtime_config_ownership_map_snapshot
runtime_invariant_registry_snapshot = runtime_invariant_registry.runtime_invariant_registry_snapshot
degradation_taxonomy_snapshot = runtime_truth_contracts.degradation_taxonomy_snapshot
fail_behavior_registry_snapshot = runtime_truth_contracts.fail_behavior_registry_snapshot
runtime_status_vocabulary_snapshot = runtime_truth_contracts.runtime_status_vocabulary_snapshot
runtime_truth_contract_drift_report = runtime_truth_drift_checker.runtime_truth_contract_drift_report
runtime_truth_trace_ids_snapshot = runtime_truth_trace_ids.runtime_truth_trace_ids_snapshot
safe_default_catalog_snapshot = safe_default_catalog.safe_default_catalog_snapshot
sampling_discipline_guide_snapshot = sampling_discipline_guide.sampling_discipline_guide_snapshot
state_transition_registry_snapshot = state_transition_registry.state_transition_registry_snapshot
streaming_semantics_snapshot = timeout_streaming_contracts.streaming_semantics_snapshot
timeout_semantics_snapshot = timeout_streaming_contracts.timeout_semantics_snapshot
ui_lane_security_boundary_test_contract_snapshot = ui_lane_security_boundary_test_contract.ui_lane_security_boundary_test_contract_snapshot
unknown_input_policy_snapshot = unknown_input_policy.unknown_input_policy_snapshot
retry_classification_policy_snapshot = _retry_classification_policy.retry_classification_policy_snapshot
validate_retry_classification_policy = _retry_classification_policy.validate_retry_classification_policy
source_attribution_policy_snapshot = _source_attribution_policy.source_attribution_policy_snapshot
validate_source_attribution_policy = _source_attribution_policy.validate_source_attribution_policy
trust_language_review_policy_snapshot = _trust_language_review_policy.trust_language_review_policy_snapshot
validate_trust_language_review_policy = _trust_language_review_policy.validate_trust_language_review_policy
validate_workspace_hygiene_rules = _workspace_hygiene_rules.validate_workspace_hygiene_rules
workspace_hygiene_rules_snapshot = _workspace_hygiene_rules.workspace_hygiene_rules_snapshot

ContractSnapshotFactory = Callable[[], dict[str, Any]]
ContractSnapshotDef = tuple[str, str, ContractSnapshotFactory, str]


def _checked_runtime_truth_contract_drift_report() -> dict[str, Any]:
    report = runtime_truth_contract_drift_report()
    if not bool(report.get("ok")):
        raise ValueError("E_RUN_TRUTH_CONTRACT_DRIFT")
    return report


def _checked_retry_classification_policy_payload() -> dict[str, Any]:
    payload = retry_classification_policy_snapshot()
    _ = validate_retry_classification_policy(payload)
    return payload


def _checked_source_attribution_policy_payload() -> dict[str, Any]:
    payload = source_attribution_policy_snapshot()
    _ = validate_source_attribution_policy(payload)
    return payload


def _checked_workspace_hygiene_rules_payload() -> dict[str, Any]:
    payload = workspace_hygiene_rules_snapshot()
    _ = validate_workspace_hygiene_rules(payload)
    return payload


def _checked_trust_language_review_policy_payload() -> dict[str, Any]:
    payload = trust_language_review_policy_snapshot()
    _ = validate_trust_language_review_policy(payload)
    return payload


CONTRACT_SNAPSHOT_DEFS: tuple[ContractSnapshotDef, ...] = (
    ("run_phase_contract", "run_phase_contract.json", run_phase_contract_snapshot, "E_RUN_PHASE_CONTRACT_IMMUTABLE"),
    (
        "runtime_status_vocabulary",
        "runtime_status_vocabulary.json",
        runtime_status_vocabulary_snapshot,
        "E_RUN_STATUS_VOCABULARY_IMMUTABLE",
    ),
    (
        "degradation_taxonomy",
        "degradation_taxonomy.json",
        degradation_taxonomy_snapshot,
        "E_RUN_DEGRADATION_TAXONOMY_IMMUTABLE",
    ),
    (
        "fail_behavior_registry",
        "fail_behavior_registry.json",
        fail_behavior_registry_snapshot,
        "E_RUN_FAIL_BEHAVIOR_REGISTRY_IMMUTABLE",
    ),
    (
        "provider_truth_table",
        "provider_truth_table.json",
        provider_truth_table_snapshot,
        "E_RUN_PROVIDER_TRUTH_TABLE_IMMUTABLE",
    ),
    (
        "state_transition_registry",
        "state_transition_registry.json",
        state_transition_registry_snapshot,
        "E_RUN_STATE_TRANSITION_REGISTRY_IMMUTABLE",
    ),
    (
        "timeout_semantics_contract",
        "timeout_semantics_contract.json",
        timeout_semantics_snapshot,
        "E_RUN_TIMEOUT_SEMANTICS_IMMUTABLE",
    ),
    (
        "streaming_semantics_contract",
        "streaming_semantics_contract.json",
        streaming_semantics_snapshot,
        "E_RUN_STREAMING_SEMANTICS_IMMUTABLE",
    ),
    (
        "runtime_truth_contract_drift_report",
        "runtime_truth_contract_drift_report.json",
        _checked_runtime_truth_contract_drift_report,
        "E_RUN_TRUTH_CONTRACT_DRIFT_REPORT_IMMUTABLE",
    ),
    (
        "runtime_truth_trace_ids",
        "runtime_truth_trace_ids.json",
        runtime_truth_trace_ids_snapshot,
        "E_RUN_TRUTH_TRACE_IDS_IMMUTABLE",
    ),
    (
        "runtime_invariant_registry",
        "runtime_invariant_registry.json",
        runtime_invariant_registry_snapshot,
        "E_RUN_INVARIANT_REGISTRY_IMMUTABLE",
    ),
    (
        "runtime_config_ownership_map",
        "runtime_config_ownership_map.json",
        runtime_config_ownership_map_snapshot,
        "E_RUN_CONFIG_OWNERSHIP_MAP_IMMUTABLE",
    ),
    (
        "unknown_input_policy",
        "unknown_input_policy.json",
        unknown_input_policy_snapshot,
        "E_RUN_UNKNOWN_INPUT_POLICY_IMMUTABLE",
    ),
    (
        "clock_time_authority_policy",
        "clock_time_authority_policy.json",
        clock_time_authority_policy_snapshot,
        "E_RUN_CLOCK_TIME_AUTHORITY_POLICY_IMMUTABLE",
    ),
    (
        "provider_quarantine_policy_contract",
        "provider_quarantine_policy_contract.json",
        provider_quarantine_policy_contract_snapshot,
        "E_RUN_PROVIDER_QUARANTINE_POLICY_CONTRACT_IMMUTABLE",
    ),
    (
        "safe_default_catalog",
        "safe_default_catalog.json",
        safe_default_catalog_snapshot,
        "E_RUN_SAFE_DEFAULT_CATALOG_IMMUTABLE",
    ),
    (
        "capability_fallback_hierarchy",
        "capability_fallback_hierarchy.json",
        capability_fallback_hierarchy_snapshot,
        "E_RUN_CAPABILITY_FALLBACK_HIERARCHY_IMMUTABLE",
    ),
    (
        "model_profile_bios",
        "model_profile_bios.json",
        model_profile_bios_snapshot,
        "E_RUN_MODEL_PROFILE_BIOS_IMMUTABLE",
    ),
    (
        "interrupt_semantics_policy",
        "interrupt_semantics_policy.json",
        interrupt_semantics_policy_snapshot,
        "E_RUN_INTERRUPT_SEMANTICS_POLICY_IMMUTABLE",
    ),
    (
        "retry_classification_policy",
        "retry_classification_policy.json",
        _checked_retry_classification_policy_payload,
        "E_RUN_RETRY_CLASSIFICATION_POLICY_IMMUTABLE",
    ),
    (
        "runtime_boundary_audit_checklist",
        "runtime_boundary_audit_checklist.json",
        runtime_boundary_audit_checklist_snapshot,
        "E_RUN_RUNTIME_BOUNDARY_AUDIT_CHECKLIST_IMMUTABLE",
    ),
    (
        "idempotency_discipline_policy",
        "idempotency_discipline_policy.json",
        idempotency_discipline_policy_snapshot,
        "E_RUN_IDEMPOTENCY_DISCIPLINE_POLICY_IMMUTABLE",
    ),
    (
        "result_error_invariant_contract",
        "result_error_invariant_contract.json",
        result_error_invariant_contract_snapshot,
        "E_RUN_RESULT_ERROR_INVARIANT_CONTRACT_IMMUTABLE",
    ),
    (
        "artifact_provenance_block_policy",
        "artifact_provenance_block_policy.json",
        artifact_provenance_block_policy_snapshot,
        "E_RUN_ARTIFACT_PROVENANCE_BLOCK_POLICY_IMMUTABLE",
    ),
    (
        "narration_effect_audit_policy",
        "narration_effect_audit_policy.json",
        narration_effect_audit_policy_snapshot,
        "E_RUN_NARRATION_EFFECT_AUDIT_POLICY_IMMUTABLE",
    ),
    (
        "source_attribution_policy",
        "source_attribution_policy.json",
        _checked_source_attribution_policy_payload,
        "E_RUN_SOURCE_ATTRIBUTION_POLICY_IMMUTABLE",
    ),
    (
        "operator_override_logging_policy",
        "operator_override_logging_policy.json",
        operator_override_logging_policy_snapshot,
        "E_RUN_OPERATOR_OVERRIDE_LOGGING_POLICY_IMMUTABLE",
    ),
    (
        "demo_production_labeling_policy",
        "demo_production_labeling_policy.json",
        demo_production_labeling_policy_snapshot,
        "E_RUN_DEMO_PRODUCTION_LABELING_POLICY_IMMUTABLE",
    ),
    (
        "human_correction_capture_policy",
        "human_correction_capture_policy.json",
        human_correction_capture_policy_snapshot,
        "E_RUN_HUMAN_CORRECTION_CAPTURE_POLICY_IMMUTABLE",
    ),
    (
        "sampling_discipline_guide",
        "sampling_discipline_guide.json",
        sampling_discipline_guide_snapshot,
        "E_RUN_SAMPLING_DISCIPLINE_GUIDE_IMMUTABLE",
    ),
    (
        "execution_readiness_rubric",
        "execution_readiness_rubric.json",
        execution_readiness_rubric_snapshot,
        "E_RUN_EXECUTION_READINESS_RUBRIC_IMMUTABLE",
    ),
    (
        "release_confidence_scorecard",
        "release_confidence_scorecard.json",
        release_confidence_scorecard_snapshot,
        "E_RUN_RELEASE_CONFIDENCE_SCORECARD_IMMUTABLE",
    ),
    (
        "feature_flag_expiration_policy",
        "feature_flag_expiration_policy.json",
        feature_flag_expiration_policy_snapshot,
        "E_RUN_FEATURE_FLAG_EXPIRATION_POLICY_IMMUTABLE",
    ),
    (
        "workspace_hygiene_rules",
        "workspace_hygiene_rules.json",
        _checked_workspace_hygiene_rules_payload,
        "E_RUN_WORKSPACE_HYGIENE_RULES_IMMUTABLE",
    ),
    (
        "canonical_examples_library",
        "canonical_examples_library.json",
        canonical_examples_library_snapshot,
        "E_RUN_CANONICAL_EXAMPLES_LIBRARY_IMMUTABLE",
    ),
    (
        "non_fatal_error_budget",
        "non_fatal_error_budget.json",
        non_fatal_error_budget_snapshot,
        "E_RUN_NON_FATAL_ERROR_BUDGET_IMMUTABLE",
    ),
    (
        "interface_freeze_windows",
        "interface_freeze_windows.json",
        interface_freeze_windows_snapshot,
        "E_RUN_INTERFACE_FREEZE_WINDOWS_IMMUTABLE",
    ),
    (
        "evidence_package_generator_contract",
        "evidence_package_generator_contract.json",
        evidence_package_generator_contract_snapshot,
        "E_RUN_EVIDENCE_PACKAGE_GENERATOR_CONTRACT_IMMUTABLE",
    ),
    (
        "conformance_governance_contract",
        "conformance_governance_contract.json",
        conformance_governance_contract_snapshot,
        "E_RUN_CONFORMANCE_GOVERNANCE_CONTRACT_IMMUTABLE",
    ),
    (
        "observability_redaction_test_contract",
        "observability_redaction_test_contract.json",
        observability_redaction_test_contract_snapshot,
        "E_RUN_OBSERVABILITY_REDACTION_TEST_CONTRACT_IMMUTABLE",
    ),
    (
        "trust_language_review_policy",
        "trust_language_review_policy.json",
        _checked_trust_language_review_policy_payload,
        "E_RUN_TRUST_LANGUAGE_REVIEW_POLICY_IMMUTABLE",
    ),
    (
        "local_remote_route_policy",
        "local_remote_route_policy.json",
        local_remote_route_policy_snapshot,
        "E_RUN_LOCAL_REMOTE_ROUTE_POLICY_IMMUTABLE",
    ),
    (
        "failure_replay_harness_contract",
        "failure_replay_harness_contract.json",
        failure_replay_harness_contract_snapshot,
        "E_RUN_FAILURE_REPLAY_HARNESS_CONTRACT_IMMUTABLE",
    ),
    (
        "cold_start_truth_test_contract",
        "cold_start_truth_test_contract.json",
        cold_start_truth_test_contract_snapshot,
        "E_RUN_COLD_START_TRUTH_TEST_CONTRACT_IMMUTABLE",
    ),
    (
        "persistence_corruption_test_contract",
        "persistence_corruption_test_contract.json",
        persistence_corruption_test_contract_snapshot,
        "E_RUN_PERSISTENCE_CORRUPTION_TEST_CONTRACT_IMMUTABLE",
    ),
    (
        "long_session_soak_test_contract",
        "long_session_soak_test_contract.json",
        long_session_soak_test_contract_snapshot,
        "E_RUN_LONG_SESSION_SOAK_TEST_CONTRACT_IMMUTABLE",
    ),
    (
        "resource_pressure_simulation_lane",
        "resource_pressure_simulation_lane.json",
        resource_pressure_simulation_lane_snapshot,
        "E_RUN_RESOURCE_PRESSURE_SIMULATION_LANE_IMMUTABLE",
    ),
    (
        "ui_lane_security_boundary_test_contract",
        "ui_lane_security_boundary_test_contract.json",
        ui_lane_security_boundary_test_contract_snapshot,
        "E_RUN_UI_LANE_SECURITY_BOUNDARY_TEST_CONTRACT_IMMUTABLE",
    ),
    (
        "degradation_first_ui_standard",
        "degradation_first_ui_standard.json",
        degradation_first_ui_standard_snapshot,
        "E_RUN_DEGRADATION_FIRST_UI_STANDARD_IMMUTABLE",
    ),
    (
        "decision_record_operating_principles_contract",
        "decision_record_operating_principles_contract.json",
        decision_record_operating_principles_contract_snapshot,
        "E_RUN_DECISION_RECORD_OPERATING_PRINCIPLES_CONTRACT_IMMUTABLE",
    ),
    (
        "naming_discipline_policy",
        "naming_discipline_policy.json",
        naming_discipline_policy_snapshot,
        "E_RUN_NAMING_DISCIPLINE_POLICY_IMMUTABLE",
    ),
    (
        "promotion_rollback_criteria",
        "promotion_rollback_criteria.json",
        promotion_rollback_criteria_snapshot,
        "E_RUN_PROMOTION_ROLLBACK_CRITERIA_IMMUTABLE",
    ),
    (
        "ledger_event_schema",
        "ledger_event_schema.json",
        _ledger_event_schema_payload,
        "E_RUN_LEDGER_EVENT_SCHEMA_IMMUTABLE",
    ),
    (
        "capability_manifest_schema",
        "capability_manifest_schema.json",
        _capability_manifest_schema_payload,
        "E_RUN_CAPABILITY_MANIFEST_SCHEMA_IMMUTABLE",
    ),
)
