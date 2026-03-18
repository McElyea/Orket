from __future__ import annotations

from typing import Any


EVIDENCE_PACKAGE_GENERATOR_CONTRACT_SCHEMA_VERSION = "1.0"

_EXPECTED_REQUIRED_SECTIONS = {
    "gate_summary",
    "drift_report",
    "release_confidence_scorecard",
    "non_fatal_error_budget",
    "interface_freeze_windows",
    "promotion_rollback_criteria",
    "artifact_inventory",
    "decision_record",
}
_EXPECTED_METADATA_FIELDS = {
    "package_id",
    "generated_at",
    "workspace_root",
    "run_id",
    "generator_version",
}
_EXPECTED_DECISION_FIELDS = {
    "promotion_recommendation",
    "required_operator_action",
}
_ALLOWED_PROMOTION_RECOMMENDATIONS = {
    "eligible",
    "blocked",
    "manual_review",
}


def evidence_package_generator_contract_snapshot() -> dict[str, Any]:
    return {
        "schema_version": EVIDENCE_PACKAGE_GENERATOR_CONTRACT_SCHEMA_VERSION,
        "output_schema_version": "runtime_truth_evidence_package.v1",
        "required_metadata_fields": [
            "package_id",
            "generated_at",
            "workspace_root",
            "run_id",
            "generator_version",
        ],
        "required_sections": [
            "gate_summary",
            "drift_report",
            "release_confidence_scorecard",
            "non_fatal_error_budget",
            "interface_freeze_windows",
            "promotion_rollback_criteria",
            "artifact_inventory",
            "decision_record",
        ],
        "required_gate_inputs": [
            "runtime_truth_acceptance_gate",
            "runtime_truth_contract_drift_report",
            "release_confidence_scorecard",
            "non_fatal_error_budget",
            "interface_freeze_windows",
            "promotion_rollback_criteria",
        ],
        "decision_record_contract": {
            "required_fields": [
                "promotion_recommendation",
                "required_operator_action",
            ],
            "allowed_recommendations": [
                "eligible",
                "blocked",
                "manual_review",
            ],
        },
    }


def validate_evidence_package_generator_contract(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    contract = dict(payload or evidence_package_generator_contract_snapshot())
    output_schema_version = str(contract.get("output_schema_version") or "").strip()
    if output_schema_version != "runtime_truth_evidence_package.v1":
        raise ValueError("E_EVIDENCE_PACKAGE_GENERATOR_CONTRACT_OUTPUT_SCHEMA_VERSION_INVALID")

    metadata_fields = {
        str(token).strip() for token in contract.get("required_metadata_fields", []) if str(token).strip()
    }
    if metadata_fields != _EXPECTED_METADATA_FIELDS:
        raise ValueError("E_EVIDENCE_PACKAGE_GENERATOR_CONTRACT_METADATA_FIELDS_MISMATCH")

    required_sections = {str(token).strip() for token in contract.get("required_sections", []) if str(token).strip()}
    if required_sections != _EXPECTED_REQUIRED_SECTIONS:
        raise ValueError("E_EVIDENCE_PACKAGE_GENERATOR_CONTRACT_REQUIRED_SECTIONS_MISMATCH")

    decision_record_contract = contract.get("decision_record_contract")
    if not isinstance(decision_record_contract, dict):
        raise ValueError("E_EVIDENCE_PACKAGE_GENERATOR_CONTRACT_DECISION_RECORD_SCHEMA")
    decision_fields = {
        str(token).strip() for token in decision_record_contract.get("required_fields", []) if str(token).strip()
    }
    if decision_fields != _EXPECTED_DECISION_FIELDS:
        raise ValueError("E_EVIDENCE_PACKAGE_GENERATOR_CONTRACT_DECISION_FIELDS_MISMATCH")
    allowed_recommendations = {
        str(token).strip()
        for token in decision_record_contract.get("allowed_recommendations", [])
        if str(token).strip()
    }
    if allowed_recommendations != _ALLOWED_PROMOTION_RECOMMENDATIONS:
        raise ValueError("E_EVIDENCE_PACKAGE_GENERATOR_CONTRACT_DECISION_RECOMMENDATIONS_MISMATCH")
    return tuple(sorted(required_sections))
