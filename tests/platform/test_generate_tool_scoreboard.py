from __future__ import annotations

import asyncio
import json

import pytest

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository


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


# Layer: integration
@pytest.mark.asyncio
async def test_generate_tool_scoreboard_script_emits_scoreboard(tmp_path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    run_id = "sess-scoreboard-script-ok"
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
    await repo.append_event(
        session_id=run_id,
        kind="operation_result",
        payload={
            "operation_id": "op-1",
            "tool_name": "write_file",
            "result": {"ok": True},
            "call_sequence_number": int(call.get("event_seq") or 0),
            "tool_call_hash": str(call.get("tool_call_hash") or ""),
            "tool_invocation_manifest": _manifest(run_id, "write_file"),
        },
    )

    out_path = tmp_path / "tool_scoreboard.json"
    result = await asyncio.create_subprocess_exec(
        "python",
        "scripts/governance/generate_tool_scoreboard.py",
        "--root",
        str(tmp_path),
        "--session-id",
        run_id,
        "--out",
        str(out_path),
        "--replay-pass-count",
        "3",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await result.communicate()
    assert result.returncode == 0, stdout.decode("utf-8") + "\n" + stderr.decode("utf-8")
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["scoreboard"]["tools"][0]["tool"] == "write_file"
    assert payload["promotion_gates"][0]["eligible"] is True


# Layer: integration
@pytest.mark.asyncio
async def test_generate_tool_scoreboard_script_fails_closed_on_incomplete_ledger(tmp_path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    run_id = "sess-scoreboard-script-fail"
    await repo.start_run(
        session_id=run_id,
        run_type="epic",
        run_name="scoreboard",
        department="core",
        build_id="b1",
    )
    _ = await repo.append_event(
        session_id=run_id,
        kind="tool_call",
        payload={
            "operation_id": "op-1",
            "tool_name": "write_file",
            "tool_args": {"path": "a.txt", "content": "x"},
            "tool_invocation_manifest": _manifest(run_id, "write_file"),
        },
    )

    out_path = tmp_path / "tool_scoreboard.json"
    result = await asyncio.create_subprocess_exec(
        "python",
        "scripts/governance/generate_tool_scoreboard.py",
        "--root",
        str(tmp_path),
        "--session-id",
        run_id,
        "--out",
        str(out_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await result.communicate()
    assert result.returncode != 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert "E_SCOREBOARD_INCOMPLETE_LEDGER" in str(payload.get("error", ""))
