from __future__ import annotations

from typing import Any


NAMING_DISCIPLINE_POLICY_SCHEMA_VERSION = "1.0"

_EXPECTED_CONVENTIONS = {
    "artifact_keys_snake_case",
    "artifact_filenames_match_keys",
    "governance_checker_scripts_snake_case",
}


def naming_discipline_policy_snapshot() -> dict[str, Any]:
    return {
        "schema_version": NAMING_DISCIPLINE_POLICY_SCHEMA_VERSION,
        "conventions": [
            {
                "convention_id": "artifact_keys_snake_case",
                "scope": "runtime_contract_artifact_keys",
                "rule": "artifact keys must be lowercase snake_case",
            },
            {
                "convention_id": "artifact_filenames_match_keys",
                "scope": "runtime_contract_artifact_files",
                "rule": "artifact filename must equal <artifact_key>.json",
            },
            {
                "convention_id": "governance_checker_scripts_snake_case",
                "scope": "scripts/governance/check_*.py",
                "rule": "governance checker scripts must be lowercase snake_case",
            },
        ],
    }


def validate_naming_discipline_policy(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    policy = dict(payload or naming_discipline_policy_snapshot())
    rows = list(policy.get("conventions") or [])
    if not rows:
        raise ValueError("E_NAMING_DISCIPLINE_POLICY_EMPTY")

    observed_ids: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("E_NAMING_DISCIPLINE_POLICY_ROW_SCHEMA")
        convention_id = str(row.get("convention_id") or "").strip()
        scope = str(row.get("scope") or "").strip()
        rule = str(row.get("rule") or "").strip()
        if not convention_id:
            raise ValueError("E_NAMING_DISCIPLINE_POLICY_CONVENTION_ID_REQUIRED")
        if not scope:
            raise ValueError(f"E_NAMING_DISCIPLINE_POLICY_SCOPE_REQUIRED:{convention_id}")
        if not rule:
            raise ValueError(f"E_NAMING_DISCIPLINE_POLICY_RULE_REQUIRED:{convention_id}")
        observed_ids.append(convention_id)

    if len(set(observed_ids)) != len(observed_ids):
        raise ValueError("E_NAMING_DISCIPLINE_POLICY_DUPLICATE_CONVENTION_ID")
    if set(observed_ids) != _EXPECTED_CONVENTIONS:
        raise ValueError("E_NAMING_DISCIPLINE_POLICY_CONVENTION_SET_MISMATCH")
    return tuple(sorted(observed_ids))
