from __future__ import annotations

from typing import Final


E_PARSE_JSON: Final[str] = "E_PARSE_JSON"
E_RESPONSE_BYTES: Final[str] = "E_RESPONSE_BYTES"
E_MARKDOWN_FENCE: Final[str] = "E_MARKDOWN_FENCE"
E_SCHEMA_ENVELOPE: Final[str] = "E_SCHEMA_ENVELOPE"
E_TOOL_MODE_CONTENT_NON_EMPTY: Final[str] = "E_TOOL_MODE_CONTENT_NON_EMPTY"
E_MISSING_TOOL_CALLS: Final[str] = "E_MISSING_TOOL_CALLS"
E_TOOL_SEQUENCE: Final[str] = "E_TOOL_SEQUENCE"
E_NON_ASCII_WHITESPACE: Final[str] = "E_NON_ASCII_WHITESPACE"

E_DUPLICATE_KEY_PREFIX: Final[str] = "E_DUPLICATE_KEY"
E_SCHEMA_TOOL_CALL_PREFIX: Final[str] = "E_SCHEMA_TOOL_CALL"
E_MAX_TOOL_CALLS_PREFIX: Final[str] = "E_MAX_TOOL_CALLS"
E_WORKSPACE_CONSTRAINT_PREFIX: Final[str] = "E_WORKSPACE_CONSTRAINT"
E_MISSING_REQUIRED_TOOL_PREFIX: Final[str] = "E_MISSING_REQUIRED_TOOL"
E_TOOL_CARDINALITY_PREFIX: Final[str] = "E_TOOL_CARDINALITY"
E_RING_POLICY_VIOLATION_PREFIX: Final[str] = "E_RING_POLICY_VIOLATION"
E_CAPABILITY_VIOLATION_PREFIX: Final[str] = "E_CAPABILITY_VIOLATION"
E_NAMESPACE_POLICY_VIOLATION_PREFIX: Final[str] = "E_NAMESPACE_POLICY_VIOLATION"
E_DETERMINISM_POLICY_VIOLATION_PREFIX: Final[str] = "E_DETERMINISM_POLICY_VIOLATION"
E_TOOL_INVOCATION_BOUNDARY_PREFIX: Final[str] = "E_TOOL_INVOCATION_BOUNDARY"
E_DETERMINISM_VIOLATION_PREFIX: Final[str] = "E_DETERMINISM_VIOLATION"
E_PROMPT_BUDGET_EXCEEDED_PREFIX: Final[str] = "E_PROMPT_BUDGET_EXCEEDED"
E_TOKENIZER_ACCOUNTING_PREFIX: Final[str] = "E_TOKENIZER_ACCOUNTING"
E_SCOREBOARD_INCOMPLETE_LEDGER_PREFIX: Final[str] = "E_SCOREBOARD_INCOMPLETE_LEDGER"
E_COMPAT_MAPPING_MISSING_PREFIX: Final[str] = "E_COMPAT_MAPPING_MISSING"
E_COMPAT_MAPPING_POLICY_VIOLATION_PREFIX: Final[str] = "E_COMPAT_MAPPING_POLICY_VIOLATION"
E_COMPAT_PARITY_VIOLATION_PREFIX: Final[str] = "E_COMPAT_PARITY_VIOLATION"

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
E_REPLAY_OPERATION_MISSING: Final[str] = "E_REPLAY_OPERATION_MISSING"
E_REPLAY_COMPATIBILITY_MISMATCH_PREFIX: Final[str] = "E_REPLAY_COMPATIBILITY_MISMATCH"
E_REPLAY_ARTIFACTS_MISSING_PREFIX: Final[str] = "E_REPLAY_ARTIFACTS_MISSING"
E_REPLAY_INCOMPLETE_PREFIX: Final[str] = "E_REPLAY_INCOMPLETE"


_EXACT_CODES: Final[dict[str, str]] = {
    E_PARSE_JSON: "Response parser failed strict JSON boundary validation.",
    E_RESPONSE_BYTES: "Response payload exceeded configured byte limits.",
    E_MARKDOWN_FENCE: "Response payload contained markdown code fences.",
    E_SCHEMA_ENVELOPE: "Response envelope failed strict schema validation.",
    E_TOOL_MODE_CONTENT_NON_EMPTY: "Tool mode response content was not empty.",
    E_MISSING_TOOL_CALLS: "Tool mode response omitted required tool calls.",
    E_TOOL_SEQUENCE: "Observed tool calls violated required deterministic sequence.",
    E_NON_ASCII_WHITESPACE: "Non-ASCII leading/trailing whitespace was detected.",
    E_LEDGER_RECORD_TOO_LARGE: "Ledger record payload exceeded LPJ-C32 cap.",
    E_LEDGER_CORRUPT: "Ledger checksum mismatch on a complete record.",
    E_LEDGER_SEQ: "Ledger event sequence is missing, duplicate, or non-monotonic.",
    E_LEDGER_PARSE: "Ledger payload bytes were not a valid JSON object.",
    E_LEASE_EXPIRED: "Worker lease expired or failed CAS renewal.",
    E_DUPLICATE_OPERATION: "Later operation commit lost first-commit-wins race.",
    E_REPLAY_OPERATION_MISSING: "Replay mode could not find a recorded operation result.",
}

_PREFIX_CODES: Final[dict[str, str]] = {
    E_DUPLICATE_KEY_PREFIX: "JSON payload contained duplicate object keys.",
    E_SCHEMA_TOOL_CALL_PREFIX: "Tool-call object failed strict schema validation.",
    E_MAX_TOOL_CALLS_PREFIX: "Tool-call count exceeded deterministic cap.",
    E_WORKSPACE_CONSTRAINT_PREFIX: "Workspace path safety constraint violation.",
    E_MISSING_REQUIRED_TOOL_PREFIX: "A required tool call was not present in the proposal.",
    E_TOOL_CARDINALITY_PREFIX: "Required tool count violated deterministic cardinality rules.",
    E_RING_POLICY_VIOLATION_PREFIX: "Tool call violated active ring policy.",
    E_CAPABILITY_VIOLATION_PREFIX: "Tool capability profile is not allowed for this run.",
    E_NAMESPACE_POLICY_VIOLATION_PREFIX: "Tool namespace targeting exceeded the active run scope policy.",
    E_DETERMINISM_POLICY_VIOLATION_PREFIX: "Tool determinism class exceeds active run determinism policy.",
    E_TOOL_INVOCATION_BOUNDARY_PREFIX: "Direct tool-to-tool invocation is not allowed.",
    E_DETERMINISM_VIOLATION_PREFIX: "Observed tool side effects conflict with declared determinism.",
    E_PROMPT_BUDGET_EXCEEDED_PREFIX: "Prompt token budget exceeded configured stage limits.",
    E_TOKENIZER_ACCOUNTING_PREFIX: "Prompt token accounting could not use required tokenizer path.",
    E_SCOREBOARD_INCOMPLETE_LEDGER_PREFIX: "Scoreboard generation found incomplete ledger tool call/result coverage.",
    E_COMPAT_MAPPING_MISSING_PREFIX: "Compatibility mapping for the requested tool was not found.",
    E_COMPAT_MAPPING_POLICY_VIOLATION_PREFIX: "Compatibility mapping violated governance constraints.",
    E_COMPAT_PARITY_VIOLATION_PREFIX: "Compatibility mapping execution failed parity expectations.",
    E_RECEIPT_SEQ_INVALID_PREFIX: "Receipt sequence value is invalid.",
    E_RECEIPT_SEQ_NON_MONOTONIC_PREFIX: "Receipt sequence is not strictly increasing.",
    E_RECEIPT_LOG_PARSE_PREFIX: "Receipt log line failed JSON parsing.",
    E_RECEIPT_LOG_SCHEMA_PREFIX: "Receipt log line is not a JSON object.",
    E_NETWORK_MODE_INVALID_PREFIX: "Unsupported protocol network mode.",
    E_REPLAY_COMPATIBILITY_MISMATCH_PREFIX: "Replay compatibility contract mismatch.",
    E_REPLAY_ARTIFACTS_MISSING_PREFIX: "Replay required artifact metadata is missing.",
    E_REPLAY_INCOMPLETE_PREFIX: "Replay required lifecycle events are incomplete.",
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


def error_family(value: str) -> str:
    code = str(value or "").strip()
    if code in _EXACT_CODES:
        return code
    prefix = code.split(":", 1)[0]
    if prefix in _PREFIX_CODES:
        return prefix
    return ""


def format_protocol_error(code: str, detail: str | None = None) -> str:
    normalized_code = str(code or "").strip()
    if not normalized_code:
        raise ValueError("protocol error code is required")
    detail_text = str(detail or "").strip()
    if not detail_text:
        return normalized_code
    return f"{normalized_code}:{detail_text}"
