from __future__ import annotations

from typing import Any


ARTIFACT_PROVENANCE_BLOCK_POLICY_SCHEMA_VERSION = "1.0"

_REQUIRED_PROVENANCE_FIELDS = {
    "run_id",
    "artifact_type",
    "generator",
    "generator_version",
    "source_hash",
    "produced_at",
    "truth_classification",
}
_ALLOWED_ENFORCEMENT_MODES = {"strict_block"}


def artifact_provenance_block_policy_snapshot() -> dict[str, Any]:
    return {
        "schema_version": ARTIFACT_PROVENANCE_BLOCK_POLICY_SCHEMA_VERSION,
        "enforcement_mode": "strict_block",
        "required_provenance_fields": sorted(_REQUIRED_PROVENANCE_FIELDS),
        "blocked_artifact_types_when_missing": [
            "report",
            "summary",
            "scorecard",
            "promotion_evidence",
        ],
        "exemptions": [],
    }


def validate_artifact_provenance_block_policy(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    policy = dict(payload or artifact_provenance_block_policy_snapshot())
    enforcement_mode = str(policy.get("enforcement_mode") or "").strip().lower()
    if enforcement_mode not in _ALLOWED_ENFORCEMENT_MODES:
        raise ValueError("E_ARTIFACT_PROVENANCE_BLOCK_MODE_INVALID")

    required_fields = [str(token or "").strip() for token in policy.get("required_provenance_fields", [])]
    if not required_fields or any(not token for token in required_fields):
        raise ValueError("E_ARTIFACT_PROVENANCE_BLOCK_REQUIRED_FIELDS_EMPTY")
    observed_fields = {field for field in required_fields if field}
    if observed_fields != _REQUIRED_PROVENANCE_FIELDS:
        raise ValueError("E_ARTIFACT_PROVENANCE_BLOCK_REQUIRED_FIELDS_MISMATCH")

    blocked_types = [str(token or "").strip() for token in policy.get("blocked_artifact_types_when_missing", [])]
    if not blocked_types or any(not token for token in blocked_types):
        raise ValueError("E_ARTIFACT_PROVENANCE_BLOCK_TYPES_EMPTY")
    if len(set(blocked_types)) != len(blocked_types):
        raise ValueError("E_ARTIFACT_PROVENANCE_BLOCK_TYPES_DUPLICATE")

    exemptions = policy.get("exemptions")
    if not isinstance(exemptions, list):
        raise ValueError("E_ARTIFACT_PROVENANCE_BLOCK_EXEMPTIONS_SCHEMA")

    return tuple(sorted(observed_fields))
