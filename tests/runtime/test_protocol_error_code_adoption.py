from __future__ import annotations

from pathlib import Path

import pytest

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.adapters.storage.protocol_append_only_ledger import (
    AppendOnlyRunLedger,
    LedgerFramingError,
    decode_lpj_c32_stream,
    encode_lpj_c32_record,
)
from orket.application.workflows.turn_response_parser import ResponseParser
from orket.application.workflows.turn_tool_dispatcher_protocol import collect_protocol_preflight_violations
from orket.core.policies.tool_gate import ToolGate
from orket.domain.execution import ExecutionTurn, ToolCall
from orket.runtime import protocol_error_codes as codes
from orket.runtime.determinism_controls import resolve_network_mode


def _code_prefix(value: str) -> str:
    return str(value or "").split(":", 1)[0]


def test_network_mode_invalid_error_uses_registered_prefix() -> None:
    with pytest.raises(ValueError) as exc:
        resolve_network_mode("internet")
    emitted = str(exc.value)
    assert _code_prefix(emitted) == codes.E_NETWORK_MODE_INVALID_PREFIX
    assert codes.is_registered_protocol_error_code(emitted) is True


def test_ledger_corruption_uses_registered_error_code() -> None:
    payload = {"event_seq": 1, "kind": "run_started", "run_id": "r1"}
    frame = bytearray(encode_lpj_c32_record(payload))
    frame[6] = frame[6] ^ 0x01
    with pytest.raises(LedgerFramingError) as exc:
        decode_lpj_c32_stream(bytes(frame))
    assert exc.value.code == codes.E_LEDGER_CORRUPT
    assert codes.is_registered_protocol_error_code(exc.value.code) is True


def test_append_only_ledger_sequence_errors_use_registered_code(tmp_path: Path) -> None:
    path = tmp_path / "runs" / "r1" / "events.log"
    ledger = AppendOnlyRunLedger(path)
    _ = ledger.append_event({"event_seq": 1, "kind": "run_started"})
    with pytest.raises(LedgerFramingError) as exc:
        ledger.append_event({"event_seq": 3, "kind": "bad"})
    assert exc.value.code == codes.E_LEDGER_SEQ
    assert codes.is_registered_protocol_error_code(exc.value.code) is True


@pytest.mark.asyncio
async def test_async_protocol_run_ledger_receipt_errors_use_registered_prefixes(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    await repo.append_receipt(
        session_id="sess-1",
        receipt={
            "run_id": "sess-1",
            "step_id": "ISSUE-1:1",
            "operation_id": "op-1",
            "event_seq_range": [1, 1],
            "execution_result": {"ok": True},
            "receipt_seq": 1,
        },
    )
    with pytest.raises(ValueError) as exc:
        await repo.append_receipt(
            session_id="sess-1",
            receipt={
                "run_id": "sess-1",
                "step_id": "ISSUE-1:2",
                "operation_id": "op-2",
                "event_seq_range": [2, 2],
                "execution_result": {"ok": True},
                "receipt_seq": 1,
            },
        )
    emitted = str(exc.value)
    assert _code_prefix(emitted) == codes.E_RECEIPT_SEQ_NON_MONOTONIC_PREFIX
    assert codes.is_registered_protocol_error_code(emitted) is True


def test_response_parser_protocol_errors_emit_registered_codes(tmp_path: Path) -> None:
    parser = ResponseParser(tmp_path, lambda **_kwargs: None)  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError) as exc:
        parser.parse_response(
            response={
                "content": (
                    '{"content":"","tool_calls":['
                    '{"tool":"write_file","args":{}},'
                    '{"tool":"read_file","args":{}}]}'
                ),
                "raw": {},
            },
            issue_id="ISSUE-1",
            role_name="coder",
            context={
                "session_id": "s1",
                "turn_index": 1,
                "protocol_governed_enabled": True,
                "max_tool_calls": 1,
            },
        )
    emitted = str(exc.value)
    assert _code_prefix(emitted) == codes.E_MAX_TOOL_CALLS_PREFIX
    assert codes.is_registered_protocol_error_code(emitted) is True


def test_protocol_preflight_validator_errors_emit_registered_codes(tmp_path: Path) -> None:
    turn = ExecutionTurn(
        role="coder",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[ToolCall(tool="read_file", args={"path": "a.txt"})],
    )
    violations = collect_protocol_preflight_violations(
        turn=turn,
        context={
            "session_id": "s1",
            "turn_index": 1,
            "required_action_tools": ["write_file"],
        },
        roles=["coder"],
        approval_required_tools=set(),
        tool_gate=ToolGate(organization=None, workspace_root=tmp_path),
        workspace=tmp_path,
        resolve_skill_tool_binding=lambda _context, _tool_name: None,
        missing_required_permissions=lambda _binding, _context: [],
        runtime_limit_violations=lambda _binding, _context: [],
    )
    assert violations
    emitted = str(violations[0])
    assert _code_prefix(emitted) == codes.E_MISSING_REQUIRED_TOOL_PREFIX
    assert codes.is_registered_protocol_error_code(emitted) is True
