from __future__ import annotations

from orket.runtime import protocol_error_codes as codes


def test_all_protocol_error_codes_are_unique() -> None:
    values = list(codes.all_protocol_error_codes())
    assert len(values) == len(set(values))


def test_is_registered_protocol_error_code_accepts_exact_codes() -> None:
    assert codes.is_registered_protocol_error_code(codes.E_PARSE_JSON) is True
    assert codes.is_registered_protocol_error_code(codes.E_RESPONSE_BYTES) is True
    assert codes.is_registered_protocol_error_code(codes.E_SCHEMA_ENVELOPE) is True
    assert codes.is_registered_protocol_error_code(codes.E_TOOL_SEQUENCE) is True
    assert codes.is_registered_protocol_error_code(codes.E_LEDGER_CORRUPT) is True
    assert codes.is_registered_protocol_error_code(codes.E_DUPLICATE_OPERATION) is True


def test_is_registered_protocol_error_code_accepts_registered_prefixes() -> None:
    assert codes.is_registered_protocol_error_code("E_DUPLICATE_KEY:tool_calls") is True
    assert codes.is_registered_protocol_error_code("E_SCHEMA_TOOL_CALL:0:args") is True
    assert codes.is_registered_protocol_error_code("E_MAX_TOOL_CALLS:9>8") is True
    assert codes.is_registered_protocol_error_code("E_WORKSPACE_CONSTRAINT:path_traversal") is True
    assert codes.is_registered_protocol_error_code("E_MISSING_REQUIRED_TOOL:write_file") is True
    assert codes.is_registered_protocol_error_code("E_TOOL_CARDINALITY:write_file:2") is True
    assert codes.is_registered_protocol_error_code("E_RECEIPT_LOG_PARSE:line=4") is True
    assert codes.is_registered_protocol_error_code("E_NETWORK_MODE_INVALID:internet") is True
    assert codes.is_registered_protocol_error_code("E_RING_POLICY_VIOLATION:write_file") is True
    assert codes.is_registered_protocol_error_code("E_CAPABILITY_VIOLATION:write_file") is True
    assert codes.is_registered_protocol_error_code("E_DETERMINISM_POLICY_VIOLATION:write_file") is True
    assert codes.is_registered_protocol_error_code("E_TOOL_INVOCATION_BOUNDARY:write_file") is True
    assert codes.is_registered_protocol_error_code("E_DETERMINISM_VIOLATION:write_file") is True


def test_is_registered_protocol_error_code_rejects_unknown_values() -> None:
    assert codes.is_registered_protocol_error_code("") is False
    assert codes.is_registered_protocol_error_code("E_UNKNOWN_CODE") is False
    assert codes.is_registered_protocol_error_code("X_CUSTOM:detail") is False


def test_error_description_returns_specific_messages() -> None:
    assert "strict JSON" in codes.error_description(codes.E_PARSE_JSON)
    assert "byte limits" in codes.error_description(codes.E_RESPONSE_BYTES)
    assert "strict schema" in codes.error_description(codes.E_SCHEMA_ENVELOPE)
    assert "required deterministic sequence" in codes.error_description(codes.E_TOOL_SEQUENCE)
    assert "checksum mismatch" in codes.error_description(codes.E_LEDGER_CORRUPT)
    assert "duplicate object keys" in codes.error_description("E_DUPLICATE_KEY:content")
    assert "cardinality" in codes.error_description("E_TOOL_CARDINALITY:write_file:2")
    assert "Workspace path safety" in codes.error_description("E_WORKSPACE_CONSTRAINT:path")
    assert "Unsupported protocol network mode." == codes.error_description("E_NETWORK_MODE_INVALID:internet")
    assert "ring policy" in codes.error_description("E_RING_POLICY_VIOLATION:tool")
    assert "capability profile" in codes.error_description("E_CAPABILITY_VIOLATION:tool")
    assert "determinism class" in codes.error_description("E_DETERMINISM_POLICY_VIOLATION:tool")
    assert "tool-to-tool invocation" in codes.error_description("E_TOOL_INVOCATION_BOUNDARY:tool")
    assert "declared determinism" in codes.error_description("E_DETERMINISM_VIOLATION:tool")


def test_format_protocol_error_requires_code() -> None:
    try:
        codes.format_protocol_error("", "detail")
    except ValueError as exc:
        assert "required" in str(exc)
    else:
        raise AssertionError("expected ValueError for missing code")


def test_format_protocol_error_with_and_without_detail() -> None:
    assert codes.format_protocol_error(codes.E_LEDGER_SEQ, None) == codes.E_LEDGER_SEQ
    assert (
        codes.format_protocol_error(codes.E_WORKSPACE_CONSTRAINT_PREFIX, "path_traversal")
        == "E_WORKSPACE_CONSTRAINT:path_traversal"
    )


def test_error_family_returns_exact_or_prefix_for_registered_codes() -> None:
    assert codes.error_family(codes.E_PARSE_JSON) == codes.E_PARSE_JSON
    assert codes.error_family("E_WORKSPACE_CONSTRAINT:path_traversal") == codes.E_WORKSPACE_CONSTRAINT_PREFIX
    assert codes.error_family("E_MISSING_REQUIRED_TOOL:write_file") == codes.E_MISSING_REQUIRED_TOOL_PREFIX
    assert codes.error_family("X_CUSTOM:detail") == ""


# Layer: unit
def test_is_registered_protocol_error_code_accepts_replay_codes() -> None:
    assert codes.is_registered_protocol_error_code(codes.E_REPLAY_OPERATION_MISSING) is True
    assert codes.is_registered_protocol_error_code("E_REPLAY_COMPATIBILITY_MISMATCH:tool_registry_version") is True
    assert codes.is_registered_protocol_error_code("E_REPLAY_ARTIFACTS_MISSING:tool_registry_version") is True
    assert codes.is_registered_protocol_error_code("E_REPLAY_INCOMPLETE:run_finalized") is True


# Layer: unit
def test_error_description_returns_replay_code_messages() -> None:
    assert "recorded operation result" in codes.error_description(codes.E_REPLAY_OPERATION_MISSING)
    assert "contract mismatch" in codes.error_description("E_REPLAY_COMPATIBILITY_MISMATCH:field")
    assert "artifact metadata is missing" in codes.error_description("E_REPLAY_ARTIFACTS_MISSING:field")
    assert "lifecycle events are incomplete" in codes.error_description("E_REPLAY_INCOMPLETE:run_finalized")
