from __future__ import annotations

from orket.runtime import protocol_error_codes as codes


def test_all_protocol_error_codes_are_unique() -> None:
    values = list(codes.all_protocol_error_codes())
    assert len(values) == len(set(values))


def test_is_registered_protocol_error_code_accepts_exact_codes() -> None:
    assert codes.is_registered_protocol_error_code(codes.E_PARSE_JSON) is True
    assert codes.is_registered_protocol_error_code(codes.E_LEDGER_CORRUPT) is True
    assert codes.is_registered_protocol_error_code(codes.E_DUPLICATE_OPERATION) is True


def test_is_registered_protocol_error_code_accepts_registered_prefixes() -> None:
    assert codes.is_registered_protocol_error_code("E_WORKSPACE_CONSTRAINT:path_traversal") is True
    assert codes.is_registered_protocol_error_code("E_RECEIPT_LOG_PARSE:line=4") is True
    assert codes.is_registered_protocol_error_code("E_NETWORK_MODE_INVALID:internet") is True


def test_is_registered_protocol_error_code_rejects_unknown_values() -> None:
    assert codes.is_registered_protocol_error_code("") is False
    assert codes.is_registered_protocol_error_code("E_UNKNOWN_CODE") is False
    assert codes.is_registered_protocol_error_code("X_CUSTOM:detail") is False


def test_error_description_returns_specific_messages() -> None:
    assert "strict JSON" in codes.error_description(codes.E_PARSE_JSON)
    assert "checksum mismatch" in codes.error_description(codes.E_LEDGER_CORRUPT)
    assert "Workspace path safety" in codes.error_description("E_WORKSPACE_CONSTRAINT:path")
    assert "Unsupported protocol network mode." == codes.error_description("E_NETWORK_MODE_INVALID:internet")


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
