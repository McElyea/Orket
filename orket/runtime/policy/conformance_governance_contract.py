from __future__ import annotations

from typing import Any

CONFORMANCE_GOVERNANCE_CONTRACT_SCHEMA_VERSION = "1.0"

_EXPECTED_SECTION_IDS = {
    "behavioral_contract_suite",
    "false_green_hunt_process",
    "golden_transcript_diff_policy",
    "operator_signoff_bundle",
    "repo_introspection_report",
    "cross_spec_consistency_checker",
}
_EXPECTED_BEHAVIORAL_STRUCTURAL_TARGETS = {
    "tests/runtime/test_run_start_artifacts.py",
    "tests/scripts/test_run_runtime_truth_acceptance_gate.py",
}
_EXPECTED_BLOCKING_CLAIMS = {
    "saved",
    "synced",
    "used memory",
    "searched",
    "verified",
}
_EXPECTED_FALSE_GREEN_CHECKLIST_ITEMS = {
    "runtime_claim_after_verify",
    "mock_only_proof_not_presented_as_live",
    "stale_phase_authority_removed_on_closeout",
}
_EXPECTED_GOLDEN_ARTIFACT_TYPES = {
    "route_decision_artifact",
    "repair_ledger",
    "degradation_labeling",
    "operator_override_log",
}
_EXPECTED_GOLDEN_BLOCKERS = {
    "missing_canonical_example",
    "unexpected_artifact_type",
    "unreviewed_behavioral_delta",
}
_EXPECTED_OPERATOR_SECTIONS = {
    "gate_summary",
    "release_confidence_scorecard",
    "promotion_rollback_criteria",
    "artifact_inventory",
    "decision_record",
}
_EXPECTED_OPERATOR_DECISION_FIELDS = {
    "promotion_recommendation",
    "required_operator_action",
}
_EXPECTED_REPO_SOURCE_ARTIFACTS = {
    "workspace_state_snapshot",
    "capability_manifest",
}
_EXPECTED_REPO_REQUIRED_FIELDS = {
    "workspace_path",
    "workspace_type",
    "workspace_hash",
    "file_count",
    "capabilities_allowed",
    "capabilities_used",
    "run_determinism_class",
}
_EXPECTED_CROSS_SPEC_CHECKS = {
    "runtime_truth_contract_drift_report",
    "docs_project_hygiene",
}


def conformance_governance_contract_snapshot() -> dict[str, Any]:
    return {
        "schema_version": CONFORMANCE_GOVERNANCE_CONTRACT_SCHEMA_VERSION,
        "sections": [
            {
                "section_id": "behavioral_contract_suite",
                "structural_targets": [
                    "tests/runtime/test_run_start_artifacts.py",
                    "tests/scripts/test_run_runtime_truth_acceptance_gate.py",
                ],
                "live_target": "tests/live/test_truthful_runtime_phase_e_completion_live.py",
                "blocking_claims": [
                    "saved",
                    "synced",
                    "used memory",
                    "searched",
                    "verified",
                ],
            },
            {
                "section_id": "false_green_hunt_process",
                "cadence": "recurring_maintenance",
                "authorities": [
                    "docs/specs/ORKET_OPERATING_PRINCIPLES.md",
                    "docs/projects/techdebt/Recurring-Maintenance-Checklist.md",
                ],
                "checklist_items": [
                    "runtime_claim_after_verify",
                    "mock_only_proof_not_presented_as_live",
                    "stale_phase_authority_removed_on_closeout",
                ],
            },
            {
                "section_id": "golden_transcript_diff_policy",
                "baseline_artifact_library": "canonical_examples_library",
                "baseline_artifact_types": [
                    "route_decision_artifact",
                    "repair_ledger",
                    "degradation_labeling",
                    "operator_override_log",
                ],
                "diff_mode": "controlled",
                "block_on": [
                    "missing_canonical_example",
                    "unexpected_artifact_type",
                    "unreviewed_behavioral_delta",
                ],
            },
            {
                "section_id": "operator_signoff_bundle",
                "required_sections": [
                    "gate_summary",
                    "release_confidence_scorecard",
                    "promotion_rollback_criteria",
                    "artifact_inventory",
                    "decision_record",
                ],
                "required_decision_fields": [
                    "promotion_recommendation",
                    "required_operator_action",
                ],
                "required_operator_action_when_eligible": "operator_signoff_required",
            },
            {
                "section_id": "repo_introspection_report",
                "source_artifacts": [
                    "workspace_state_snapshot",
                    "capability_manifest",
                ],
                "required_fields": [
                    "workspace_path",
                    "workspace_type",
                    "workspace_hash",
                    "file_count",
                    "capabilities_allowed",
                    "capabilities_used",
                    "run_determinism_class",
                ],
                "output_dir": "observability/<run_id>/runtime_contracts",
            },
            {
                "section_id": "cross_spec_consistency_checker",
                "required_checks": [
                    "runtime_truth_contract_drift_report",
                    "docs_project_hygiene",
                ],
                "failure_policy": "block_closeout",
                "docs_hygiene_command": "python scripts/governance/check_docs_project_hygiene.py",
            },
        ],
    }


def validate_conformance_governance_contract(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    contract = dict(payload or conformance_governance_contract_snapshot())
    rows = list(contract.get("sections") or [])
    if not rows:
        raise ValueError("E_CONFORMANCE_GOVERNANCE_CONTRACT_EMPTY")

    observed_ids: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("E_CONFORMANCE_GOVERNANCE_CONTRACT_ROW_SCHEMA")
        section_id = str(row.get("section_id") or "").strip()
        if not section_id:
            raise ValueError("E_CONFORMANCE_GOVERNANCE_CONTRACT_SECTION_ID_REQUIRED")

        if section_id == "behavioral_contract_suite":
            _validate_behavioral_contract_suite(row)
        elif section_id == "false_green_hunt_process":
            _validate_false_green_hunt_process(row)
        elif section_id == "golden_transcript_diff_policy":
            _validate_golden_transcript_diff_policy(row)
        elif section_id == "operator_signoff_bundle":
            _validate_operator_signoff_bundle(row)
        elif section_id == "repo_introspection_report":
            _validate_repo_introspection_report(row)
        elif section_id == "cross_spec_consistency_checker":
            _validate_cross_spec_consistency_checker(row)
        else:
            raise ValueError(f"E_CONFORMANCE_GOVERNANCE_CONTRACT_SECTION_UNKNOWN:{section_id}")
        observed_ids.append(section_id)

    if len(set(observed_ids)) != len(observed_ids):
        raise ValueError("E_CONFORMANCE_GOVERNANCE_CONTRACT_DUPLICATE_SECTION")
    if set(observed_ids) != _EXPECTED_SECTION_IDS:
        raise ValueError("E_CONFORMANCE_GOVERNANCE_CONTRACT_SECTION_SET_MISMATCH")
    return tuple(sorted(observed_ids))


def _validate_behavioral_contract_suite(row: dict[str, Any]) -> None:
    structural_targets = {str(token).strip() for token in row.get("structural_targets", []) if str(token).strip()}
    if structural_targets != _EXPECTED_BEHAVIORAL_STRUCTURAL_TARGETS:
        raise ValueError("E_CONFORMANCE_GOVERNANCE_CONTRACT_BEHAVIORAL_TARGETS_MISMATCH")
    live_target = str(row.get("live_target") or "").strip()
    if live_target != "tests/live/test_truthful_runtime_phase_e_completion_live.py":
        raise ValueError("E_CONFORMANCE_GOVERNANCE_CONTRACT_BEHAVIORAL_LIVE_TARGET_INVALID")
    blocking_claims = {str(token).strip() for token in row.get("blocking_claims", []) if str(token).strip()}
    if blocking_claims != _EXPECTED_BLOCKING_CLAIMS:
        raise ValueError("E_CONFORMANCE_GOVERNANCE_CONTRACT_BLOCKING_CLAIMS_MISMATCH")


def _validate_false_green_hunt_process(row: dict[str, Any]) -> None:
    cadence = str(row.get("cadence") or "").strip()
    if cadence != "recurring_maintenance":
        raise ValueError("E_CONFORMANCE_GOVERNANCE_CONTRACT_FALSE_GREEN_CADENCE_INVALID")
    authorities = {str(token).strip() for token in row.get("authorities", []) if str(token).strip()}
    if authorities != {
        "docs/specs/ORKET_OPERATING_PRINCIPLES.md",
        "docs/projects/techdebt/Recurring-Maintenance-Checklist.md",
    }:
        raise ValueError("E_CONFORMANCE_GOVERNANCE_CONTRACT_FALSE_GREEN_AUTHORITIES_MISMATCH")
    checklist_items = {str(token).strip() for token in row.get("checklist_items", []) if str(token).strip()}
    if checklist_items != _EXPECTED_FALSE_GREEN_CHECKLIST_ITEMS:
        raise ValueError("E_CONFORMANCE_GOVERNANCE_CONTRACT_FALSE_GREEN_CHECKLIST_MISMATCH")


def _validate_golden_transcript_diff_policy(row: dict[str, Any]) -> None:
    baseline_artifact_library = str(row.get("baseline_artifact_library") or "").strip()
    if baseline_artifact_library != "canonical_examples_library":
        raise ValueError("E_CONFORMANCE_GOVERNANCE_CONTRACT_GOLDEN_LIBRARY_INVALID")
    artifact_types = {str(token).strip() for token in row.get("baseline_artifact_types", []) if str(token).strip()}
    if artifact_types != _EXPECTED_GOLDEN_ARTIFACT_TYPES:
        raise ValueError("E_CONFORMANCE_GOVERNANCE_CONTRACT_GOLDEN_TYPES_MISMATCH")
    diff_mode = str(row.get("diff_mode") or "").strip()
    if diff_mode != "controlled":
        raise ValueError("E_CONFORMANCE_GOVERNANCE_CONTRACT_GOLDEN_DIFF_MODE_INVALID")
    blockers = {str(token).strip() for token in row.get("block_on", []) if str(token).strip()}
    if blockers != _EXPECTED_GOLDEN_BLOCKERS:
        raise ValueError("E_CONFORMANCE_GOVERNANCE_CONTRACT_GOLDEN_BLOCKERS_MISMATCH")


def _validate_operator_signoff_bundle(row: dict[str, Any]) -> None:
    required_sections = {str(token).strip() for token in row.get("required_sections", []) if str(token).strip()}
    if required_sections != _EXPECTED_OPERATOR_SECTIONS:
        raise ValueError("E_CONFORMANCE_GOVERNANCE_CONTRACT_SIGNOFF_SECTIONS_MISMATCH")
    required_decision_fields = {
        str(token).strip() for token in row.get("required_decision_fields", []) if str(token).strip()
    }
    if required_decision_fields != _EXPECTED_OPERATOR_DECISION_FIELDS:
        raise ValueError("E_CONFORMANCE_GOVERNANCE_CONTRACT_SIGNOFF_DECISION_FIELDS_MISMATCH")
    operator_action = str(row.get("required_operator_action_when_eligible") or "").strip()
    if operator_action != "operator_signoff_required":
        raise ValueError("E_CONFORMANCE_GOVERNANCE_CONTRACT_SIGNOFF_ACTION_INVALID")


def _validate_repo_introspection_report(row: dict[str, Any]) -> None:
    source_artifacts = {str(token).strip() for token in row.get("source_artifacts", []) if str(token).strip()}
    if source_artifacts != _EXPECTED_REPO_SOURCE_ARTIFACTS:
        raise ValueError("E_CONFORMANCE_GOVERNANCE_CONTRACT_REPO_SOURCES_MISMATCH")
    required_fields = {str(token).strip() for token in row.get("required_fields", []) if str(token).strip()}
    if required_fields != _EXPECTED_REPO_REQUIRED_FIELDS:
        raise ValueError("E_CONFORMANCE_GOVERNANCE_CONTRACT_REPO_FIELDS_MISMATCH")
    output_dir = str(row.get("output_dir") or "").strip()
    if output_dir != "observability/<run_id>/runtime_contracts":
        raise ValueError("E_CONFORMANCE_GOVERNANCE_CONTRACT_REPO_OUTPUT_DIR_INVALID")


def _validate_cross_spec_consistency_checker(row: dict[str, Any]) -> None:
    required_checks = {str(token).strip() for token in row.get("required_checks", []) if str(token).strip()}
    if required_checks != _EXPECTED_CROSS_SPEC_CHECKS:
        raise ValueError("E_CONFORMANCE_GOVERNANCE_CONTRACT_CROSS_SPEC_CHECKS_MISMATCH")
    failure_policy = str(row.get("failure_policy") or "").strip()
    if failure_policy != "block_closeout":
        raise ValueError("E_CONFORMANCE_GOVERNANCE_CONTRACT_CROSS_SPEC_FAILURE_POLICY_INVALID")
    docs_hygiene_command = str(row.get("docs_hygiene_command") or "").strip()
    if docs_hygiene_command != "python scripts/governance/check_docs_project_hygiene.py":
        raise ValueError("E_CONFORMANCE_GOVERNANCE_CONTRACT_CROSS_SPEC_COMMAND_INVALID")
