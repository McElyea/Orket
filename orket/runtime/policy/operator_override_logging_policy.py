from __future__ import annotations

from typing import Any

OPERATOR_OVERRIDE_LOGGING_POLICY_SCHEMA_VERSION = "1.0"

_EXPECTED_OVERRIDE_TYPES = {
    "route_override",
    "prompt_profile_override",
    "strictness_override",
    "provider_quarantine_override",
}
_REQUIRED_FIELDS = {
    "run_id",
    "override_type",
    "override_value",
    "operator_id",
    "reason",
    "timestamp",
}


def operator_override_logging_policy_snapshot() -> dict[str, Any]:
    return {
        "schema_version": OPERATOR_OVERRIDE_LOGGING_POLICY_SCHEMA_VERSION,
        "required_fields": sorted(_REQUIRED_FIELDS),
        "override_types": sorted(_EXPECTED_OVERRIDE_TYPES),
        "persistence": {
            "store": "run_ledger",
            "emit_warning_event": True,
            "redaction_profile": "operator_override_v1",
        },
    }


def validate_operator_override_logging_policy(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    policy = dict(payload or operator_override_logging_policy_snapshot())

    required_fields = [str(token or "").strip() for token in policy.get("required_fields", [])]
    if not required_fields or any(not token for token in required_fields):
        raise ValueError("E_OPERATOR_OVERRIDE_LOGGING_REQUIRED_FIELDS_EMPTY")
    if {field for field in required_fields if field} != _REQUIRED_FIELDS:
        raise ValueError("E_OPERATOR_OVERRIDE_LOGGING_REQUIRED_FIELDS_MISMATCH")

    override_types = [str(token or "").strip() for token in policy.get("override_types", [])]
    if not override_types or any(not token for token in override_types):
        raise ValueError("E_OPERATOR_OVERRIDE_LOGGING_TYPES_EMPTY")
    observed_types = {token for token in override_types if token}
    if observed_types != _EXPECTED_OVERRIDE_TYPES:
        raise ValueError("E_OPERATOR_OVERRIDE_LOGGING_TYPES_MISMATCH")

    persistence = policy.get("persistence")
    if not isinstance(persistence, dict):
        raise ValueError("E_OPERATOR_OVERRIDE_LOGGING_PERSISTENCE_SCHEMA")
    if str(persistence.get("store") or "").strip() != "run_ledger":
        raise ValueError("E_OPERATOR_OVERRIDE_LOGGING_STORE_INVALID")
    if not isinstance(persistence.get("emit_warning_event"), bool):
        raise ValueError("E_OPERATOR_OVERRIDE_LOGGING_EMIT_WARNING_INVALID")
    if not str(persistence.get("redaction_profile") or "").strip():
        raise ValueError("E_OPERATOR_OVERRIDE_LOGGING_REDACTION_REQUIRED")

    return tuple(sorted(observed_types))
