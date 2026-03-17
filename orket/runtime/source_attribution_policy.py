from __future__ import annotations

from typing import Any


SOURCE_ATTRIBUTION_POLICY_SCHEMA_VERSION = "1.0"

_EXPECTED_MODES = {
    "optional",
    "required",
}
_EXPECTED_REQUIRED_CLAIM_FIELDS = (
    "claim_id",
    "claim",
    "source_ids",
)
_EXPECTED_REQUIRED_SOURCE_FIELDS = (
    "source_id",
    "title",
    "uri",
    "kind",
)
_EXPECTED_FAILURE_REASONS = {
    "source_attribution_claim_source_missing",
    "source_attribution_claims_missing",
    "source_attribution_receipt_invalid_json",
    "source_attribution_receipt_missing",
    "source_attribution_source_fields_missing",
    "source_attribution_sources_missing",
}
_MODE_ROWS: tuple[dict[str, Any], ...] = (
    {
        "mode": "optional",
        "gate_on_missing_receipt": False,
        "high_stakes": False,
    },
    {
        "mode": "required",
        "gate_on_missing_receipt": True,
        "high_stakes": True,
    },
)


def source_attribution_policy_snapshot() -> dict[str, Any]:
    return {
        "schema_version": SOURCE_ATTRIBUTION_POLICY_SCHEMA_VERSION,
        "modes": [dict(row) for row in _MODE_ROWS],
        "required_claim_fields": list(_EXPECTED_REQUIRED_CLAIM_FIELDS),
        "required_source_fields": list(_EXPECTED_REQUIRED_SOURCE_FIELDS),
        "failure_reasons": sorted(_EXPECTED_FAILURE_REASONS),
    }


def validate_source_attribution_policy(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    policy = dict(payload or source_attribution_policy_snapshot())
    rows = list(policy.get("modes") or [])
    if not rows:
        raise ValueError("E_SOURCE_ATTRIBUTION_POLICY_EMPTY")

    observed_modes: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("E_SOURCE_ATTRIBUTION_POLICY_ROW_SCHEMA")
        mode = str(row.get("mode") or "").strip().lower()
        gate_on_missing_receipt = row.get("gate_on_missing_receipt")
        high_stakes = row.get("high_stakes")
        if not mode:
            raise ValueError("E_SOURCE_ATTRIBUTION_POLICY_MODE_REQUIRED")
        if not isinstance(gate_on_missing_receipt, bool):
            raise ValueError(f"E_SOURCE_ATTRIBUTION_POLICY_GATE_SCHEMA:{mode}")
        if not isinstance(high_stakes, bool):
            raise ValueError(f"E_SOURCE_ATTRIBUTION_POLICY_HIGH_STAKES_SCHEMA:{mode}")
        observed_modes.append(mode)

    if len(set(observed_modes)) != len(observed_modes):
        raise ValueError("E_SOURCE_ATTRIBUTION_POLICY_DUPLICATE_MODE")
    if set(observed_modes) != _EXPECTED_MODES:
        raise ValueError("E_SOURCE_ATTRIBUTION_POLICY_MODE_SET_MISMATCH")

    required_claim_fields = tuple(
        str(token).strip()
        for token in policy.get("required_claim_fields", [])
        if str(token).strip()
    )
    if required_claim_fields != _EXPECTED_REQUIRED_CLAIM_FIELDS:
        raise ValueError("E_SOURCE_ATTRIBUTION_POLICY_REQUIRED_CLAIM_FIELDS_MISMATCH")

    required_source_fields = tuple(
        str(token).strip()
        for token in policy.get("required_source_fields", [])
        if str(token).strip()
    )
    if required_source_fields != _EXPECTED_REQUIRED_SOURCE_FIELDS:
        raise ValueError("E_SOURCE_ATTRIBUTION_POLICY_REQUIRED_SOURCE_FIELDS_MISMATCH")

    failure_reasons = {
        str(token).strip().lower()
        for token in policy.get("failure_reasons", [])
        if str(token).strip()
    }
    if failure_reasons != _EXPECTED_FAILURE_REASONS:
        raise ValueError("E_SOURCE_ATTRIBUTION_POLICY_FAILURE_REASON_SET_MISMATCH")

    return tuple(sorted(observed_modes))
