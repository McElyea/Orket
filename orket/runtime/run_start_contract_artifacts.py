from __future__ import annotations

from typing import Any, Callable

from orket.runtime.artifact_provenance_block_policy import artifact_provenance_block_policy_snapshot
from orket.runtime.capability_fallback_hierarchy import capability_fallback_hierarchy_snapshot
from orket.runtime.canonical_examples_library import canonical_examples_library_snapshot
from orket.runtime.clock_time_authority_policy import clock_time_authority_policy_snapshot
from orket.runtime.demo_production_labeling_policy import demo_production_labeling_policy_snapshot
from orket.runtime.evidence_package_generator_contract import evidence_package_generator_contract_snapshot
from orket.runtime.execution_readiness_rubric import execution_readiness_rubric_snapshot
from orket.runtime.feature_flag_expiration_policy import feature_flag_expiration_policy_snapshot
from orket.runtime.human_correction_capture_policy import human_correction_capture_policy_snapshot
from orket.runtime.idempotency_discipline_policy import idempotency_discipline_policy_snapshot
from orket.runtime.interface_freeze_windows import interface_freeze_windows_snapshot
from orket.runtime.interrupt_semantics_policy import interrupt_semantics_policy_snapshot
from orket.runtime.local_remote_route_policy import local_remote_route_policy_snapshot
from orket.runtime.model_profile_bios import model_profile_bios_snapshot
from orket.runtime.non_fatal_error_budget import non_fatal_error_budget_snapshot
from orket.runtime.observability_redaction_test_contract import observability_redaction_test_contract_snapshot
from orket.runtime.operator_override_logging_policy import operator_override_logging_policy_snapshot
from orket.runtime.promotion_rollback_criteria import promotion_rollback_criteria_snapshot
from orket.runtime.provider_truth_table import provider_truth_table_snapshot
from orket.runtime.release_confidence_scorecard import release_confidence_scorecard_snapshot
from orket.runtime.run_phase_contract import run_phase_contract_snapshot
from orket.runtime.runtime_config_ownership_map import runtime_config_ownership_map_snapshot
from orket.runtime.runtime_invariant_registry import runtime_invariant_registry_snapshot
from orket.runtime.runtime_truth_contracts import (
    degradation_taxonomy_snapshot,
    fail_behavior_registry_snapshot,
    runtime_status_vocabulary_snapshot,
)
from orket.runtime.runtime_truth_drift_checker import runtime_truth_contract_drift_report
from orket.runtime.runtime_truth_trace_ids import runtime_truth_trace_ids_snapshot
from orket.runtime.sampling_discipline_guide import sampling_discipline_guide_snapshot
from orket.runtime.spec_debt_queue import spec_debt_queue_snapshot
from orket.runtime.state_transition_registry import state_transition_registry_snapshot
from orket.runtime.timeout_streaming_contracts import (
    streaming_semantics_snapshot,
    timeout_semantics_snapshot,
)
from orket.runtime.trust_language_review_policy import trust_language_review_policy_snapshot
from orket.runtime.unknown_input_policy import unknown_input_policy_snapshot
from orket.runtime.workspace_hygiene_rules import workspace_hygiene_rules_snapshot

ContractSnapshotFactory = Callable[[], dict[str, Any]]
ContractSnapshotDef = tuple[str, str, ContractSnapshotFactory, str]


def _ledger_event_schema_payload() -> dict[str, Any]:
    return {
        "ledger_schema_version": "1.0",
        "event_type": "tool_call|tool_result|run_started|run_finalized",
        "required_fields": [
            "ledger_schema_version",
            "event_type",
            "timestamp",
            "tool_name",
            "run_id",
            "sequence_number",
        ],
        "required_on_tool_result": [
            "call_sequence_number",
            "tool_call_hash",
        ],
        "required_on_artifact_reference": [
            "artifact_hash",
        ],
    }


def _capability_manifest_schema_payload() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "type": "object",
        "required": [
            "run_id",
            "capabilities_allowed",
            "capabilities_used",
            "run_determinism_class",
        ],
        "properties": {
            "run_id": {"type": "string", "min_length": 1},
            "capabilities_allowed": {"type": "array", "items": {"type": "string"}},
            "capabilities_used": {"type": "array", "items": {"type": "string"}},
            "run_determinism_class": {"type": "string", "enum": ["pure", "workspace", "external"]},
        },
    }


def _checked_runtime_truth_contract_drift_report() -> dict[str, Any]:
    report = runtime_truth_contract_drift_report()
    if not bool(report.get("ok")):
        raise ValueError("E_RUN_TRUTH_CONTRACT_DRIFT")
    return report


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
        "capability_fallback_hierarchy",
        "capability_fallback_hierarchy.json",
        capability_fallback_hierarchy_snapshot,
        "E_RUN_CAPABILITY_FALLBACK_HIERARCHY_IMMUTABLE",
    ),
    ("model_profile_bios", "model_profile_bios.json", model_profile_bios_snapshot, "E_RUN_MODEL_PROFILE_BIOS_IMMUTABLE"),
    (
        "interrupt_semantics_policy",
        "interrupt_semantics_policy.json",
        interrupt_semantics_policy_snapshot,
        "E_RUN_INTERRUPT_SEMANTICS_POLICY_IMMUTABLE",
    ),
    (
        "idempotency_discipline_policy",
        "idempotency_discipline_policy.json",
        idempotency_discipline_policy_snapshot,
        "E_RUN_IDEMPOTENCY_DISCIPLINE_POLICY_IMMUTABLE",
    ),
    (
        "artifact_provenance_block_policy",
        "artifact_provenance_block_policy.json",
        artifact_provenance_block_policy_snapshot,
        "E_RUN_ARTIFACT_PROVENANCE_BLOCK_POLICY_IMMUTABLE",
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
        workspace_hygiene_rules_snapshot,
        "E_RUN_WORKSPACE_HYGIENE_RULES_IMMUTABLE",
    ),
    (
        "canonical_examples_library",
        "canonical_examples_library.json",
        canonical_examples_library_snapshot,
        "E_RUN_CANONICAL_EXAMPLES_LIBRARY_IMMUTABLE",
    ),
    (
        "spec_debt_queue",
        "spec_debt_queue.json",
        spec_debt_queue_snapshot,
        "E_RUN_SPEC_DEBT_QUEUE_IMMUTABLE",
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
        "observability_redaction_test_contract",
        "observability_redaction_test_contract.json",
        observability_redaction_test_contract_snapshot,
        "E_RUN_OBSERVABILITY_REDACTION_TEST_CONTRACT_IMMUTABLE",
    ),
    (
        "trust_language_review_policy",
        "trust_language_review_policy.json",
        trust_language_review_policy_snapshot,
        "E_RUN_TRUST_LANGUAGE_REVIEW_POLICY_IMMUTABLE",
    ),
    (
        "local_remote_route_policy",
        "local_remote_route_policy.json",
        local_remote_route_policy_snapshot,
        "E_RUN_LOCAL_REMOTE_ROUTE_POLICY_IMMUTABLE",
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
