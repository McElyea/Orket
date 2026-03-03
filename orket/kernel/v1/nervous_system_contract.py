from __future__ import annotations

from typing import Iterable

from .canonical import digest_of

GENESIS_STATE_DIGEST = "0" * 64
NERVOUS_SYSTEM_PURPOSE_ACTION_PATH = "action_path"

ADMISSION_DECISIONS_V1 = (
    "ACCEPT_TO_UNIFY",
    "REJECT",
    "NEEDS_APPROVAL",
    "QUARANTINE",
)

COMMIT_STATUSES_V1 = (
    "COMMITTED",
    "REJECTED_PRECONDITION",
    "REJECTED_POLICY",
    "REJECTED_APPROVAL_MISSING",
    "ERROR",
)

REASON_CODES_V1_ORDER = (
    "SCHEMA_INVALID",
    "POLICY_FORBIDDEN",
    "LEAK_DETECTED",
    "SCOPE_VIOLATION",
    "UNKNOWN_TOOL_PROFILE",
    "APPROVAL_REQUIRED_DESTRUCTIVE",
    "APPROVAL_REQUIRED_EXFIL",
    "APPROVAL_REQUIRED_CREDENTIALED",
    "TOKEN_INVALID",
    "TOKEN_EXPIRED",
    "TOKEN_REPLAY",
    "RESULT_SCHEMA_INVALID",
    "RESULT_LEAK_DETECTED",
)

_KNOWN_REASON_CODE_INDEX = {code: index for index, code in enumerate(REASON_CODES_V1_ORDER)}


def ordered_reason_codes_v1(reason_codes: Iterable[str]) -> list[str]:
    """
    Normalize reason codes to deterministic v1 ordering.

    Known reason codes are returned in locked order. Unknown reason codes are
    appended in sorted lexical order for deterministic forward compatibility.
    Duplicate input values are removed.
    """
    seen: set[str] = set()
    known: list[str] = []
    unknown: list[str] = []

    for item in reason_codes:
        code = str(item).strip()
        if not code or code in seen:
            continue
        seen.add(code)
        if code in _KNOWN_REASON_CODE_INDEX:
            known.append(code)
        else:
            unknown.append(code)

    known.sort(key=_KNOWN_REASON_CODE_INDEX.__getitem__)
    unknown.sort()
    return known + unknown


def canonical_scope_digest(scope_json: object) -> str:
    """Digest for token scope binding based on canonical JSON."""
    return digest_of(scope_json)


def tool_profile_digest(tool_profile_definition: object) -> str:
    """Digest for policy-resolved tool profile definition."""
    return digest_of(tool_profile_definition)


def is_genesis_state_digest(value: str) -> bool:
    return str(value).strip().lower() == GENESIS_STATE_DIGEST


__all__ = [
    "ADMISSION_DECISIONS_V1",
    "COMMIT_STATUSES_V1",
    "GENESIS_STATE_DIGEST",
    "NERVOUS_SYSTEM_PURPOSE_ACTION_PATH",
    "REASON_CODES_V1_ORDER",
    "canonical_scope_digest",
    "is_genesis_state_digest",
    "ordered_reason_codes_v1",
    "tool_profile_digest",
]
