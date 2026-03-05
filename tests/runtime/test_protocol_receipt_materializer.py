from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.runtime.protocol_receipt_materializer import materialize_protocol_receipts


def _write_turn_receipts(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_materialize_protocol_receipts_writes_run_level_receipts_and_events(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _write_turn_receipts(
        workspace / "observability" / "sess-1" / "ISSUE-1" / "001_architect" / "protocol_receipts.log",
        [
            {
                "run_id": "sess-1",
                "step_id": "ISSUE-1:1",
                "operation_id": "op-1",
                "tool": "write_file",
                "tool_index": 0,
                "execution_result": {"ok": True},
            },
            {
                "run_id": "sess-1",
                "step_id": "ISSUE-1:2",
                "operation_id": "op-2",
                "tool": "write_file",
                "tool_index": 0,
                "execution_result": {"ok": True},
            },
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
    assert [row["operation_id"] for row in events] == ["op-1", "op-2"]
    assert [row["receipt_seq"] for row in events] == [1, 2]

    receipts = await repo.list_receipts("sess-1")
    assert [row["receipt_seq"] for row in receipts] == [1, 2]
    assert receipts[0]["event_seq_range"] == [1, 1]
    assert receipts[1]["event_seq_range"] == [2, 2]
    assert all(len(str(row["receipt_digest"])) == 64 for row in receipts)


@pytest.mark.asyncio
async def test_materialize_protocol_receipts_is_idempotent_on_repeated_runs(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _write_turn_receipts(
        workspace / "observability" / "sess-2" / "ISSUE-1" / "001_architect" / "protocol_receipts.log",
        [
            {
                "run_id": "sess-2",
                "step_id": "ISSUE-1:1",
                "operation_id": "op-1",
                "tool": "write_file",
                "tool_index": 0,
                "execution_result": {"ok": True},
            }
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
    receipts = await repo.list_receipts("sess-2")
    assert len(receipts) == 1
