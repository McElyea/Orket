from __future__ import annotations

from typing import Final


E_PARSE_JSON: Final[str] = "E_PARSE_JSON"
E_WORKSPACE_CONSTRAINT_PREFIX: Final[str] = "E_WORKSPACE_CONSTRAINT"

E_LEDGER_RECORD_TOO_LARGE: Final[str] = "E_LEDGER_RECORD_TOO_LARGE"
E_LEDGER_CORRUPT: Final[str] = "E_LEDGER_CORRUPT"
E_LEDGER_SEQ: Final[str] = "E_LEDGER_SEQ"
E_LEDGER_PARSE: Final[str] = "E_LEDGER_PARSE"

E_RECEIPT_SEQ_INVALID_PREFIX: Final[str] = "E_RECEIPT_SEQ_INVALID"
E_RECEIPT_SEQ_NON_MONOTONIC_PREFIX: Final[str] = "E_RECEIPT_SEQ_NON_MONOTONIC"
E_RECEIPT_LOG_PARSE_PREFIX: Final[str] = "E_RECEIPT_LOG_PARSE"
E_RECEIPT_LOG_SCHEMA_PREFIX: Final[str] = "E_RECEIPT_LOG_SCHEMA"

E_NETWORK_MODE_INVALID_PREFIX: Final[str] = "E_NETWORK_MODE_INVALID"
E_LEASE_EXPIRED: Final[str] = "E_LEASE_EXPIRED"
E_DUPLICATE_OPERATION: Final[str] = "E_DUPLICATE_OPERATION"


_EXACT_CODES: Final[dict[str, str]] = {
    E_PARSE_JSON: "Response parser failed strict JSON boundary validation.",
    E_LEDGER_RECORD_TOO_LARGE: "Ledger record payload exceeded LPJ-C32 cap.",
    E_LEDGER_CORRUPT: "Ledger checksum mismatch on a complete record.",
    E_LEDGER_SEQ: "Ledger event sequence is missing, duplicate, or non-monotonic.",
    E_LEDGER_PARSE: "Ledger payload bytes were not a valid JSON object.",
    E_LEASE_EXPIRED: "Worker lease expired or failed CAS renewal.",
    E_DUPLICATE_OPERATION: "Later operation commit lost first-commit-wins race.",
}

_PREFIX_CODES: Final[dict[str, str]] = {
    E_WORKSPACE_CONSTRAINT_PREFIX: "Workspace path safety constraint violation.",
    E_RECEIPT_SEQ_INVALID_PREFIX: "Receipt sequence value is invalid.",
    E_RECEIPT_SEQ_NON_MONOTONIC_PREFIX: "Receipt sequence is not strictly increasing.",
    E_RECEIPT_LOG_PARSE_PREFIX: "Receipt log line failed JSON parsing.",
    E_RECEIPT_LOG_SCHEMA_PREFIX: "Receipt log line is not a JSON object.",
    E_NETWORK_MODE_INVALID_PREFIX: "Unsupported protocol network mode.",
}


def all_protocol_error_codes() -> tuple[str, ...]:
    codes = sorted(list(_EXACT_CODES.keys()) + [f"{prefix}:<detail>" for prefix in _PREFIX_CODES])
    return tuple(codes)


def is_registered_protocol_error_code(value: str) -> bool:
    code = str(value or "").strip()
    if not code:
        return False
    if code in _EXACT_CODES:
        return True
    prefix = code.split(":", 1)[0]
    return prefix in _PREFIX_CODES


def error_description(value: str) -> str:
    code = str(value or "").strip()
    if code in _EXACT_CODES:
        return _EXACT_CODES[code]
    prefix = code.split(":", 1)[0]
    return _PREFIX_CODES.get(prefix, "Unregistered protocol error code.")


def format_protocol_error(code: str, detail: str | None = None) -> str:
    normalized_code = str(code or "").strip()
    if not normalized_code:
        raise ValueError("protocol error code is required")
    detail_text = str(detail or "").strip()
    if not detail_text:
        return normalized_code
    return f"{normalized_code}:{detail_text}"
