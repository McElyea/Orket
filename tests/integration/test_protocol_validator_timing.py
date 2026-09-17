"""Layer: integration. Real tool dispatch, receipt persistence and artifact replay."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.application.middleware import TurnLifecycleInterceptors
from orket.application.services.tool_gate_service import ToolGate
from orket.application.workflows.turn_artifact_writer import TurnArtifactWriter
from orket.application.workflows.turn_tool_dispatcher import ToolDispatcher
from orket.core.contracts.protocol_hashing import hash_canonical_json
from orket.core.domain.execution import ExecutionTurn, ToolCall
from orket.runtime.evidence.protocol_receipt_materializer import materialize_protocol_receipts
from orket.tools import ToolBox
from tests.helpers.protocol_ledger_clock import ProtocolLedgerClock

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _runtime(workspace: Path):
    writer = TurnArtifactWriter(workspace)
    gate = ToolGate(organization=None, workspace_root=workspace)
    dispatcher = ToolDispatcher(
        tool_gate=gate, middleware=TurnLifecycleInterceptors([]), workspace=workspace,
        append_memory_event=writer.append_memory_event, hash_payload=writer.hash_payload,
        load_replay_tool_result=writer.load_replay_tool_result,
        persist_tool_result=writer.persist_tool_result,
        load_operation_result=writer.load_operation_result,
        persist_operation_result=writer.persist_operation_result,
        append_protocol_receipt=writer.append_protocol_receipt,
    )
    toolbox = ToolBox(policy=None, workspace_root=str(workspace), references=[],
                      db_path=str(workspace / "cards.db"), tool_gate=gate)
    return dispatcher, toolbox


async def _dispatch(dispatcher, toolbox, timing_context=None, *, replay=False):
    turn = ExecutionTurn(role="coder", issue_id="TIMING-1", content="", tool_calls=[
        ToolCall(tool="read_file", args={"path": "input.txt"}),
    ])
    await dispatcher.execute_tools(turn=turn, toolbox=toolbox, context={
        "roles": ["coder"], "session_id": "timing", "turn_index": 1,
        "protocol_governed_enabled": True, "protocol_replay_mode": replay,
        **(timing_context or {}),
    })
    return turn.tool_calls[0].result


def _receipt_path(workspace):
    return workspace / "observability/timing/timing-1/001_coder/protocol_receipts.log"


@pytest.mark.parametrize("value,expected,reason", [
    (None, None, "missing"), (False, None, "invalid"), (True, None, "invalid"),
    (-1, None, "invalid"), ("12", None, "invalid"), (float("nan"), None, "invalid"),
    (float("inf"), None, "invalid"), (10**400, None, "invalid"),
    (0, 0.0, None), (0.25, 0.25, None), (17, 17.0, None),
], ids=["missing", "false", "true", "negative", "text", "nan", "infinity", "overflow",
        "supplied-zero", "fractional", "integer"])
# Layer: integration
async def test_dispatcher_retains_truthful_validator_timing(tmp_path, value, expected, reason):
    """Layer: integration. File reads and retained receipts preserve timing provenance."""
    await asyncio.to_thread((tmp_path / "input.txt").write_text, "actual file", encoding="utf-8")
    dispatcher, toolbox = _runtime(tmp_path)
    result = await _dispatch(dispatcher, toolbox, {"validator_duration_ms": value})
    assert result["ok"] is True
    assert "actual file" in str(result)
    receipt = json.loads(await asyncio.to_thread(_receipt_path(tmp_path).read_text, encoding="utf-8"))
    digest = receipt.pop("receipt_digest")
    assert digest == hash_canonical_json(receipt)
    assert receipt["validator_duration_ms"] == expected
    assert receipt["schema_version"] == "protocol_receipt.v2"
    assert receipt["validator_timing"] == {
        "status": "reported" if expected is not None else "unavailable",
        "source": "runtime_context" if expected is not None else None,
        "reason": reason,
    }
    retained = {**receipt, "receipt_digest": digest}
    ledger = AsyncProtocolRunLedgerRepository(tmp_path / "durable")
    assert await ledger.append_receipt(session_id="timing", receipt=retained) == retained
    assert await ledger.append_receipt(session_id="timing", receipt=retained) == retained
    assert await ledger.list_receipts("timing") == [retained]


@pytest.mark.parametrize("legacy", [False, True])
# Layer: integration
async def test_replay_preserves_receipt_bytes_and_original_file_result(tmp_path, legacy):
    """Layer: integration. Replay and materialization retain historical timing."""
    source = tmp_path / "input.txt"
    await asyncio.to_thread(source.write_text, "original file", encoding="utf-8")
    dispatcher, toolbox = _runtime(tmp_path)
    original_result = await _dispatch(dispatcher, toolbox)
    receipt_path = _receipt_path(tmp_path)
    receipt = json.loads(await asyncio.to_thread(receipt_path.read_text, encoding="utf-8"))
    if legacy:
        receipt.pop("receipt_digest")
        receipt.pop("validator_timing", None)
        receipt.update(schema_version="protocol_receipt.v1", validator_duration_ms=0)
        receipt["receipt_digest"] = hash_canonical_json(receipt)
        await asyncio.to_thread(receipt_path.write_text, json.dumps(receipt) + "\n", encoding="utf-8")
    before = await asyncio.to_thread(receipt_path.read_bytes)
    await asyncio.to_thread(source.write_text, "later file", encoding="utf-8")
    replayed = await _dispatch(dispatcher, toolbox, {"validator_duration_ms": 987}, replay=True)
    assert replayed == original_result
    assert "original file" in str(replayed)
    assert await asyncio.to_thread(receipt_path.read_bytes) == before
    ledger = AsyncProtocolRunLedgerRepository(
        tmp_path / "projected", timestamp_factory=ProtocolLedgerClock().utc_now_iso,
    )
    materialized = await materialize_protocol_receipts(workspace=tmp_path, session_id="timing", run_ledger=ledger)
    assert materialized["materialized_receipts"] == 1
    projected = (await ledger.list_receipts("timing"))[0]
    expected = {**receipt, "event_seq_range": [1, 2]}
    expected.pop("receipt_digest")
    expected["receipt_digest"] = hash_canonical_json(expected)
    assert projected == expected
    reused = await materialize_protocol_receipts(workspace=tmp_path, session_id="timing", run_ledger=ledger)
    assert reused["reused_receipts"] == 1
    assert await ledger.list_receipts("timing") == [projected]
    assert await asyncio.to_thread(receipt_path.read_bytes) == before
