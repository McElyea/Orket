from __future__ import annotations

from typing import Any

DECISION_RECORD_OPERATING_PRINCIPLES_CONTRACT_SCHEMA_VERSION = "1.0"

_EXPECTED_CHECK_IDS = {
    "decision_log_template_sections_present",
    "operating_principles_sections_present",
}


def decision_record_operating_principles_contract_snapshot() -> dict[str, Any]:
    return {
        "schema_version": DECISION_RECORD_OPERATING_PRINCIPLES_CONTRACT_SCHEMA_VERSION,
        "checks": [
            {
                "check_id": "decision_log_template_sections_present",
                "relative_path": "docs/process/decision-log-template.md",
                "required_headings": [
                    "## Decision Record",
                    "## Context",
                    "## Options Considered",
                    "## Decision",
                    "## Contracts Affected",
                    "## Test and Validation Plan",
                    "## Migration and Rollback",
                ],
            },
            {
                "check_id": "operating_principles_sections_present",
                "relative_path": "docs/specs/ORKET_OPERATING_PRINCIPLES.md",
                "required_headings": [
                    "## Purpose",
                    "## Principles",
                    "Truthful behavior before convenience.",
                    "Truthful verification before green theater.",
                    "## Enforcement Signals",
                ],
            },
        ],
    }


def validate_decision_record_operating_principles_contract(
    payload: dict[str, Any] | None = None,
) -> tuple[str, ...]:
    contract = dict(payload or decision_record_operating_principles_contract_snapshot())
    checks = list(contract.get("checks") or [])
    if not checks:
        raise ValueError("E_DECISION_RECORD_OPERATING_PRINCIPLES_CONTRACT_EMPTY")

    observed_check_ids: list[str] = []
    for row in checks:
        if not isinstance(row, dict):
            raise ValueError("E_DECISION_RECORD_OPERATING_PRINCIPLES_CONTRACT_ROW_SCHEMA")
        check_id = str(row.get("check_id") or "").strip()
        relative_path = str(row.get("relative_path") or "").strip()
        headings = [str(token).strip() for token in row.get("required_headings", []) if str(token).strip()]
        if not check_id:
            raise ValueError("E_DECISION_RECORD_OPERATING_PRINCIPLES_CONTRACT_CHECK_ID_REQUIRED")
        if not relative_path:
            raise ValueError(f"E_DECISION_RECORD_OPERATING_PRINCIPLES_CONTRACT_PATH_REQUIRED:{check_id}")
        if not headings:
            raise ValueError(f"E_DECISION_RECORD_OPERATING_PRINCIPLES_CONTRACT_HEADINGS_REQUIRED:{check_id}")
        observed_check_ids.append(check_id)

    if len(set(observed_check_ids)) != len(observed_check_ids):
        raise ValueError("E_DECISION_RECORD_OPERATING_PRINCIPLES_CONTRACT_DUPLICATE_CHECK_ID")
    if set(observed_check_ids) != _EXPECTED_CHECK_IDS:
        raise ValueError("E_DECISION_RECORD_OPERATING_PRINCIPLES_CONTRACT_CHECK_ID_SET_MISMATCH")
    return tuple(sorted(observed_check_ids))
