from __future__ import annotations

from typing import Any


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
    rows = list(ruleset.get("rules") or [])
    if not rows:
        raise ValueError("E_WORKSPACE_HYGIENE_RULES_EMPTY")

    observed_ids: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("E_WORKSPACE_HYGIENE_RULES_ROW_SCHEMA")
        rule_id = str(row.get("rule_id") or "").strip()
        description = str(row.get("description") or "").strip()
        severity = str(row.get("severity") or "").strip().lower()
        if not rule_id:
            raise ValueError("E_WORKSPACE_HYGIENE_RULES_RULE_ID_REQUIRED")
        if not description:
            raise ValueError(f"E_WORKSPACE_HYGIENE_RULES_DESCRIPTION_REQUIRED:{rule_id}")
        if severity not in _ALLOWED_SEVERITY:
            raise ValueError(f"E_WORKSPACE_HYGIENE_RULES_SEVERITY_INVALID:{rule_id}")
        observed_ids.append(rule_id)

    if len(set(observed_ids)) != len(observed_ids):
        raise ValueError("E_WORKSPACE_HYGIENE_RULES_DUPLICATE_RULE_ID")
    if {token for token in observed_ids} != _EXPECTED_RULE_IDS:
        raise ValueError("E_WORKSPACE_HYGIENE_RULES_RULE_ID_SET_MISMATCH")

    return tuple(sorted(observed_ids))
