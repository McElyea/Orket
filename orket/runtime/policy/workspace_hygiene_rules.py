from __future__ import annotations

from typing import Any

from orket.runtime.contract_schema import ContractRegistry

WORKSPACE_HYGIENE_RULES_SCHEMA_VERSION = "1.0"

_EXPECTED_RULE_IDS = {
    "WSH-001",
    "WSH-002",
    "WSH-003",
    "WSH-004",
}
_ALLOWED_SEVERITY = {"blocker", "advisory"}


def workspace_hygiene_rules_snapshot() -> dict[str, Any]:
    return {
        "schema_version": WORKSPACE_HYGIENE_RULES_SCHEMA_VERSION,
        "rules": [
            {
                "rule_id": "WSH-001",
                "description": "runtime artifacts must stay under observability/<run_id>/runtime_contracts",
                "severity": "blocker",
            },
            {
                "rule_id": "WSH-002",
                "description": "temporary benchmark scratch paths must not be canonical artifact sources",
                "severity": "advisory",
            },
            {
                "rule_id": "WSH-003",
                "description": "generated governance outputs must use stable canonical output paths",
                "severity": "blocker",
            },
            {
                "rule_id": "WSH-004",
                "description": "cleanup scripts must not remove active non-archive docs projects",
                "severity": "blocker",
            },
        ],
    }


def validate_workspace_hygiene_rules(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    ruleset = dict(payload or workspace_hygiene_rules_snapshot())
    registry = ContractRegistry(
        schema_version=WORKSPACE_HYGIENE_RULES_SCHEMA_VERSION,
        rows=[dict(row) for row in list(ruleset.get("rules") or []) if isinstance(row, dict)],
        collection_key="rules",
        row_id_field="rule_id",
        empty_error="E_WORKSPACE_HYGIENE_RULES_EMPTY",
        row_schema_error="E_WORKSPACE_HYGIENE_RULES_ROW_SCHEMA",
        row_id_required_error="E_WORKSPACE_HYGIENE_RULES_RULE_ID_REQUIRED",
        duplicate_error="E_WORKSPACE_HYGIENE_RULES_DUPLICATE_RULE_ID",
        required_ids=_EXPECTED_RULE_IDS,
        required_set_error="E_WORKSPACE_HYGIENE_RULES_RULE_ID_SET_MISMATCH",
        required_row_fields=("description", "severity"),
        field_required_errors={"description": "E_WORKSPACE_HYGIENE_RULES_DESCRIPTION_REQUIRED"},
        allowed_row_values={"severity": _ALLOWED_SEVERITY},
        field_allowed_errors={"severity": "E_WORKSPACE_HYGIENE_RULES_SEVERITY_INVALID"},
    )
    return registry.validate(ruleset)
