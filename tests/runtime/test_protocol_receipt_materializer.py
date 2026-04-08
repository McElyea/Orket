from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.runtime.registry.tool_invocation_contracts import (
    build_tool_invocation_manifest,
    compute_tool_call_hash,
)
from orket.runtime.protocol_receipt_materializer import materialize_protocol_receipts


def _write_turn_receipts(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def _receipt_row(*, run_id: str, step_id: str, operation_id: str, tool_index: int = 0) -> dict:
    manifest = build_tool_invocation_manifest(
        run_id=run_id,
        tool_name="write_file",
        control_plane_run_id=f"turn-tool-run:{run_id}:ISSUE-1:architect:0001",
        control_plane_attempt_id=f"turn-tool-run:{run_id}:ISSUE-1:architect:0001:attempt:0001",
        control_plane_step_id=operation_id,
        control_plane_reservation_id=f"turn-tool-reservation:turn-tool-run:{run_id}:ISSUE-1:architect:0001",
        control_plane_lease_id=f"turn-tool-lease:turn-tool-run:{run_id}:ISSUE-1:architect:0001",
        control_plane_resource_id="namespace:issue:ISSUE-1",
    )
    tool_args = {"path": f"agent_output/{operation_id}.txt", "content": "ok"}
    return {
        "run_id": run_id,
        "step_id": step_id,
        "operation_id": operation_id,
        "tool": "write_file",
        "tool_index": int(tool_index),
        "tool_args": tool_args,
        "execution_result": {"ok": True},
        "tool_invocation_manifest": manifest,
        "tool_call_hash": compute_tool_call_hash(
            tool_name="write_file",
            tool_args=tool_args,
            tool_contract_version=str(manifest["tool_contract_version"]),
            capability_profile=str(manifest["capability_profile"]),
        ),
    }


@pytest.mark.asyncio
async def test_materialize_protocol_receipts_writes_run_level_receipts_and_events(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _write_turn_receipts(
        workspace / "observability" / "sess-1" / "ISSUE-1" / "001_architect" / "protocol_receipts.log",
        [
            _receipt_row(run_id="sess-1", step_id="ISSUE-1:1", operation_id="op-1"),
            _receipt_row(run_id="sess-1", step_id="ISSUE-1:2", operation_id="op-2"),
        ],
    )

    repo = AsyncProtocolRunLedgerRepository(workspace)
    summary = await materialize_protocol_receipts(
        workspace=workspace,
        session_id="sess-1",
        run_ledger=repo,
    )
    assert summary["status"] == "ok"
    assert summary["source_receipts"] == 2
    assert summary["materialized_receipts"] == 2
    assert summary["reused_receipts"] == 0

    events = await repo.list_events("sess-1")
    assert [row["kind"] for row in events] == ["tool_call", "operation_result", "tool_call", "operation_result"]
    assert [row["operation_id"] for row in events] == ["op-1", "op-1", "op-2", "op-2"]
    assert [row["receipt_seq"] for row in events] == [1, 1, 2, 2]
    assert [row["call_sequence_number"] for row in events if row["kind"] == "operation_result"] == [1, 3]
    assert events[0]["projection_source"] == "observability.protocol_receipts.log"
    assert events[0]["projection_only"] is True
    assert events[0]["tool_invocation_manifest"]["control_plane_resource_id"] == "namespace:issue:ISSUE-1"
    assert events[0]["tool_invocation_manifest"]["control_plane_step_id"] == "op-1"
    assert (
        events[0]["tool_invocation_manifest"]["control_plane_reservation_id"]
        == "turn-tool-reservation:turn-tool-run:sess-1:ISSUE-1:architect:0001"
    )
    assert events[1]["control_plane_effect_projection"] == {
        "projection_only": True,
        "authority_surface": "control_plane_effect_journal",
        "run_id": "turn-tool-run:sess-1:ISSUE-1:architect:0001",
        "attempt_id": "turn-tool-run:sess-1:ISSUE-1:architect:0001:attempt:0001",
        "effect_id": "turn-tool-effect:op-1",
    }

    receipts = await repo.list_receipts("sess-1")
    assert [row["receipt_seq"] for row in receipts] == [1, 2]
    assert receipts[0]["event_seq_range"] == [1, 2]
    assert receipts[1]["event_seq_range"] == [3, 4]
    assert all(len(str(row["receipt_digest"])) == 64 for row in receipts)


@pytest.mark.asyncio
async def test_materialize_protocol_receipts_is_idempotent_on_repeated_runs(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _write_turn_receipts(
        workspace / "observability" / "sess-2" / "ISSUE-1" / "001_architect" / "protocol_receipts.log",
        [
            _receipt_row(run_id="sess-2", step_id="ISSUE-1:1", operation_id="op-1")
        ],
    )
    repo = AsyncProtocolRunLedgerRepository(workspace)

    first = await materialize_protocol_receipts(
        workspace=workspace,
        session_id="sess-2",
        run_ledger=repo,
    )
    second = await materialize_protocol_receipts(
        workspace=workspace,
        session_id="sess-2",
        run_ledger=repo,
    )
    assert first["materialized_receipts"] == 1
    assert second["materialized_receipts"] == 0
    assert second["reused_receipts"] == 1
    events = await repo.list_events("sess-2")
    assert events[0]["projection_only"] is True
    assert events[1]["control_plane_effect_projection"]["effect_id"] == "turn-tool-effect:op-1"
    receipts = await repo.list_receipts("sess-2")
    assert len(receipts) == 1


@pytest.mark.asyncio
async def test_materialize_protocol_receipts_completes_under_asyncio_wait_for(tmp_path: Path) -> None:
    """Layer: integration. Verifies receipt materialization remains awaitable under a bounded event-loop deadline."""
    workspace = tmp_path / "workspace"
    _write_turn_receipts(
        workspace / "observability" / "sess-3" / "ISSUE-1" / "001_architect" / "protocol_receipts.log",
        [_receipt_row(run_id="sess-3", step_id="ISSUE-1:1", operation_id="op-1")],
    )
    repo = AsyncProtocolRunLedgerRepository(workspace)

    summary = await asyncio.wait_for(
        materialize_protocol_receipts(workspace=workspace, session_id="sess-3", run_ledger=repo),
        timeout=1.0,
    )

    assert summary["status"] == "ok"
