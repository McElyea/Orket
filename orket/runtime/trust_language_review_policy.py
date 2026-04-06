from __future__ import annotations

from typing import Any

from orket.runtime.contract_schema import ContractRegistry

TRUST_LANGUAGE_REVIEW_POLICY_SCHEMA_VERSION = "1.0"

_EXPECTED_CLAIMS = {
    "saved",
    "synced",
    "used_memory",
    "searched",
    "verified",
}
_EXPECTED_DISALLOWED_UNQUALIFIED_PHRASES = {
    "saved",
    "synced",
    "used memory",
    "searched",
    "verified",
}


def trust_language_review_policy_snapshot() -> dict[str, Any]:
    return {
        "schema_version": TRUST_LANGUAGE_REVIEW_POLICY_SCHEMA_VERSION,
        "claims": [
            {
                "claim": "saved",
                "required_artifacts": ["memory_write_receipt"],
                "required_qualifier_tokens": ["durable", "receipt"],
                "approved_phrase_examples": ["saved with durable receipt"],
            },
            {
                "claim": "synced",
                "required_artifacts": ["sync_receipt"],
                "required_qualifier_tokens": ["target", "receipt"],
                "approved_phrase_examples": ["synced to target with receipt"],
            },
            {
                "claim": "used_memory",
                "required_artifacts": ["memory_read_receipt"],
                "required_qualifier_tokens": ["source", "timestamp"],
                "approved_phrase_examples": ["used memory from source at timestamp"],
            },
            {
                "claim": "searched",
                "required_artifacts": ["search_query_receipt"],
                "required_qualifier_tokens": ["query", "source"],
                "approved_phrase_examples": ["searched query against source index"],
            },
            {
                "claim": "verified",
                "required_artifacts": ["source_attribution_receipt"],
                "required_qualifier_tokens": ["cited", "source"],
                "approved_phrase_examples": ["verified with cited sources"],
            },
        ],
        "disallowed_unqualified_phrases": [
            "saved",
            "synced",
            "used memory",
            "searched",
            "verified",
        ],
        "violation_policy": {
            "warning_code": "W_TRUST_LANGUAGE_UNQUALIFIED",
            "on_violation": "emit_warning",
        },
    }


def validate_trust_language_review_policy(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    policy = dict(payload or trust_language_review_policy_snapshot())
    rows = list(policy.get("claims") or [])
    registry = ContractRegistry(
        schema_version=TRUST_LANGUAGE_REVIEW_POLICY_SCHEMA_VERSION,
        rows=[dict(row) for row in rows if isinstance(row, dict)],
        collection_key="claims",
        row_id_field="claim",
        empty_error="E_TRUST_LANGUAGE_REVIEW_POLICY_EMPTY",
        row_schema_error="E_TRUST_LANGUAGE_REVIEW_POLICY_ROW_SCHEMA",
        row_id_required_error="E_TRUST_LANGUAGE_REVIEW_POLICY_CLAIM_REQUIRED",
        duplicate_error="E_TRUST_LANGUAGE_REVIEW_POLICY_DUPLICATE_CLAIM",
        required_ids=_EXPECTED_CLAIMS,
        required_set_error="E_TRUST_LANGUAGE_REVIEW_POLICY_CLAIM_SET_MISMATCH",
    )
    observed_claims = list(registry.validate(policy))

    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("E_TRUST_LANGUAGE_REVIEW_POLICY_ROW_SCHEMA")
        claim = str(row.get("claim") or "").strip()
        required_artifacts = [str(token).strip() for token in row.get("required_artifacts", []) if str(token).strip()]
        required_qualifier_tokens = [
            str(token).strip() for token in row.get("required_qualifier_tokens", []) if str(token).strip()
        ]
        approved_phrase_examples = [
            str(token).strip() for token in row.get("approved_phrase_examples", []) if str(token).strip()
        ]
        if not claim:
            raise ValueError("E_TRUST_LANGUAGE_REVIEW_POLICY_CLAIM_REQUIRED")
        if not required_artifacts:
            raise ValueError(f"E_TRUST_LANGUAGE_REVIEW_POLICY_ARTIFACTS_REQUIRED:{claim}")
        if not required_qualifier_tokens:
            raise ValueError(f"E_TRUST_LANGUAGE_REVIEW_POLICY_QUALIFIERS_REQUIRED:{claim}")
        if not approved_phrase_examples:
            raise ValueError(f"E_TRUST_LANGUAGE_REVIEW_POLICY_EXAMPLES_REQUIRED:{claim}")

    disallowed_phrases = {
        _normalize_phrase(token) for token in policy.get("disallowed_unqualified_phrases", []) if str(token).strip()
    }
    if disallowed_phrases != _EXPECTED_DISALLOWED_UNQUALIFIED_PHRASES:
        raise ValueError("E_TRUST_LANGUAGE_REVIEW_POLICY_DISALLOWED_SET_MISMATCH")

    violation_policy = policy.get("violation_policy")
    if not isinstance(violation_policy, dict):
        raise ValueError("E_TRUST_LANGUAGE_REVIEW_POLICY_VIOLATION_POLICY_SCHEMA")
    if str(violation_policy.get("warning_code") or "").strip() != "W_TRUST_LANGUAGE_UNQUALIFIED":
        raise ValueError("E_TRUST_LANGUAGE_REVIEW_POLICY_WARNING_CODE_INVALID")
    if str(violation_policy.get("on_violation") or "").strip() != "emit_warning":
        raise ValueError("E_TRUST_LANGUAGE_REVIEW_POLICY_ON_VIOLATION_INVALID")

    return tuple(sorted(observed_claims))


def classify_trust_language_phrase(phrase: str, *, policy: dict[str, Any] | None = None) -> str:
    resolved_policy = dict(policy or trust_language_review_policy_snapshot())
    normalized_phrase = _normalize_phrase(phrase)
    if not normalized_phrase:
        return "unknown"

    disallowed = {
        _normalize_phrase(token)
        for token in resolved_policy.get("disallowed_unqualified_phrases", [])
        if str(token).strip()
    }
    if normalized_phrase in disallowed:
        return "unqualified"

    for row in resolved_policy.get("claims", []):
        if not isinstance(row, dict):
            continue
        claim = _normalize_phrase(str(row.get("claim") or "").replace("_", " "))
        qualifiers = [
            _normalize_phrase(token) for token in row.get("required_qualifier_tokens", []) if str(token).strip()
        ]
        if claim and claim in normalized_phrase:
            if qualifiers and all(token in normalized_phrase for token in qualifiers):
                return "qualified"
            return "unqualified"

    return "unknown"


def _normalize_phrase(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())
