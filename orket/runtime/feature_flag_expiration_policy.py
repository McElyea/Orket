from __future__ import annotations

from typing import Any


FEATURE_FLAG_EXPIRATION_POLICY_SCHEMA_VERSION = "1.0"

_ALLOWED_ENFORCEMENT = {"block_on_expired"}
_REQUIRED_FIELDS = {"flag_name", "owner", "created_at", "expires_at", "removal_issue"}


def feature_flag_expiration_policy_snapshot() -> dict[str, Any]:
    return {
        "schema_version": FEATURE_FLAG_EXPIRATION_POLICY_SCHEMA_VERSION,
        "enforcement_mode": "block_on_expired",
        "required_fields": sorted(_REQUIRED_FIELDS),
        "max_default_ttl_days": 90,
    }


def validate_feature_flag_expiration_policy(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    policy = dict(payload or feature_flag_expiration_policy_snapshot())

    enforcement_mode = str(policy.get("enforcement_mode") or "").strip().lower()
    if enforcement_mode not in _ALLOWED_ENFORCEMENT:
        raise ValueError("E_FEATURE_FLAG_EXPIRATION_ENFORCEMENT_INVALID")

    required_fields = [str(token or "").strip() for token in policy.get("required_fields", [])]
    if not required_fields or any(not token for token in required_fields):
        raise ValueError("E_FEATURE_FLAG_EXPIRATION_REQUIRED_FIELDS_EMPTY")
    observed = {field for field in required_fields if field}
    if observed != _REQUIRED_FIELDS:
        raise ValueError("E_FEATURE_FLAG_EXPIRATION_REQUIRED_FIELDS_MISMATCH")

    max_default_ttl_days = policy.get("max_default_ttl_days")
    if not isinstance(max_default_ttl_days, int):
        raise ValueError("E_FEATURE_FLAG_EXPIRATION_TTL_SCHEMA")
    if max_default_ttl_days <= 0:
        raise ValueError("E_FEATURE_FLAG_EXPIRATION_TTL_RANGE")

    return tuple(sorted(observed))
