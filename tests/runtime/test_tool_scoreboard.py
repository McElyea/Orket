from __future__ import annotations

import pytest

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.runtime.tool_scoreboard import build_tool_scoreboard, evaluate_promotion_gate


def _manifest(run_id: str, tool_name: str) -> dict[str, str]:
    return {
        "manifest_version": "1.0",
        "run_id": run_id,
        "tool_name": tool_name,
        "ring": "core",
        "schema_version": "1.0.0",
        "determinism_class": "workspace",
        "capability_profile": "workspace",
        "tool_contract_version": "1.0.0",
    }


# Layer: contract
def test_build_tool_scoreboard_is_reproducible_from_same_ledger_events() -> None:
    events = [
        {"event_seq": 1, "kind": "tool_call", "tool_name": "write_file"},
        {
            "event_seq": 2,
            "kind": "tool_result",
            "call_sequence_number": 1,
            "tool_name": "write_file",
            "result": {"ok": True},
        },
    ]

    first = build_tool_scoreboard(events)
    second = build_tool_scoreboard(events)

    assert first == second
    assert first["tools"][0]["tool"] == "write_file"
    assert first["tools"][0]["success_rate"] == 1.0


# Layer: contract
def test_build_tool_scoreboard_fails_closed_on_incomplete_ledger_coverage() -> None:
    events = [
        {"event_seq": 1, "kind": "tool_call", "tool_name": "write_file"},
    ]

    with pytest.raises(ValueError, match="E_SCOREBOARD_INCOMPLETE_LEDGER"):
        _ = build_tool_scoreboard(events)


# Layer: integration
@pytest.mark.asyncio
async def test_build_tool_scoreboard_from_protocol_ledger_events(tmp_path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    run_id = "sess-scoreboard"
    await repo.start_run(
        session_id=run_id,
        run_type="epic",
        run_name="scoreboard",
        department="core",
        build_id="b1",
    )
    call = await repo.append_event(
        session_id=run_id,
        kind="tool_call",
        payload={
            "operation_id": "op-1",
            "tool_name": "write_file",
            "tool_args": {"path": "a.txt", "content": "x"},
            "tool_invocation_manifest": _manifest(run_id, "write_file"),
        },
    )
    call_seq = int(call.get("event_seq") or 0)
    await repo.append_event(
        session_id=run_id,
        kind="operation_result",
        payload={
            "operation_id": "op-1",
            "tool_name": "write_file",
            "result": {"ok": True},
            "call_sequence_number": call_seq,
            "tool_call_hash": str(call.get("tool_call_hash") or ""),
            "tool_invocation_manifest": _manifest(run_id, "write_file"),
        },
    )
    events = await repo.list_events(run_id)
    scoreboard = build_tool_scoreboard(events)

    assert scoreboard["scoreboard_schema_version"] == "1.0"
    assert scoreboard["tools"][0]["tool"] == "write_file"
    assert scoreboard["tools"][0]["invocations"] == 1


# Layer: integration
def test_evaluate_promotion_gate_pass_and_fail_paths() -> None:
    passing = evaluate_promotion_gate(
        tool_score={"tool": "write_file", "invocations": 10, "success_rate": 0.97},
        reliability_threshold=0.95,
        required_replay_runs=3,
        replay_pass_count=3,
        unresolved_drift_count=0,
    )
    failing = evaluate_promotion_gate(
        tool_score={"tool": "write_file", "invocations": 10, "success_rate": 0.80},
        reliability_threshold=0.95,
        required_replay_runs=3,
        replay_pass_count=1,
        unresolved_drift_count=2,
    )

    assert passing["eligible"] is True
    assert failing["eligible"] is False
    assert "reliability_threshold_not_met" in failing["reasons"]
    assert "replay_parity_not_met" in failing["reasons"]
    assert "unresolved_drift_present" in failing["reasons"]
