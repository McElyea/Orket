from __future__ import annotations

from pathlib import Path

import pytest

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository


@pytest.mark.asyncio
async def test_async_protocol_run_ledger_start_and_finalize(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    await repo.start_run(
        session_id="sess-1",
        run_type="epic",
        run_name="Epic One",
        department="core",
        build_id="build-1",
        summary={"session_status": "running"},
        artifacts={"workspace": "workspace/path"},
    )
    await repo.finalize_run(
        session_id="sess-1",
        status="incomplete",
        summary={"session_status": "incomplete"},
        artifacts={"gitea_export": {"provider": "gitea"}},
    )

    run = await repo.get_run("sess-1")
    assert run is not None
    assert run["session_id"] == "sess-1"
    assert run["run_type"] == "epic"
    assert run["run_name"] == "Epic One"
    assert run["status"] == "incomplete"
    assert run["summary_json"]["session_status"] == "incomplete"
    assert run["artifact_json"]["workspace"] == "workspace/path"
    assert run["artifact_json"]["gitea_export"]["provider"] == "gitea"
    assert run["started_event_seq"] == 1
    assert run["ended_event_seq"] == 2


@pytest.mark.asyncio
async def test_async_protocol_run_ledger_append_event_is_monotonic(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    first = await repo.append_event(session_id="sess-2", kind="event_a", payload={"x": 1})
    second = await repo.append_event(session_id="sess-2", kind="event_b", payload={"x": 2})
    events = await repo.list_events("sess-2")
    assert first["event_seq"] == 1
    assert second["event_seq"] == 2
    assert [row["event_seq"] for row in events] == [1, 2]
    assert [row["kind"] for row in events] == ["event_a", "event_b"]


@pytest.mark.asyncio
async def test_async_protocol_run_ledger_returns_none_for_missing_run(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    run = await repo.get_run("missing")
    assert run is None


@pytest.mark.asyncio
async def test_async_protocol_run_ledger_isolated_by_session(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    await repo.start_run(
        session_id="sess-a",
        run_type="epic",
        run_name="A",
        department="core",
        build_id="build-a",
    )
    await repo.start_run(
        session_id="sess-b",
        run_type="epic",
        run_name="B",
        department="core",
        build_id="build-b",
    )
    events_a = await repo.list_events("sess-a")
    events_b = await repo.list_events("sess-b")
    assert len(events_a) == 1
    assert len(events_b) == 1
    assert events_a[0]["session_id"] == "sess-a"
    assert events_b[0]["session_id"] == "sess-b"


@pytest.mark.asyncio
async def test_async_protocol_run_ledger_operation_commit_is_first_wins(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    first = await repo.append_event(
        session_id="sess-op",
        kind="operation_result",
        payload={
            "operation_id": "op-1",
            "tool": "write_file",
            "result": {"ok": True, "value": 1},
        },
    )
    second = await repo.append_event(
        session_id="sess-op",
        kind="operation_result",
        payload={
            "operation_id": "op-1",
            "tool": "write_file",
            "result": {"ok": True, "value": 2},
        },
    )
    assert first["event_seq"] == 1
    assert second["kind"] == "operation_rejected"
    assert second["error_code"] == "E_DUPLICATE_OPERATION"
    assert second["winner_event_seq"] == 1
    assert second["idempotent_reuse"] is False


@pytest.mark.asyncio
async def test_async_protocol_run_ledger_duplicate_same_payload_marks_idempotent_reuse(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    first_payload = {
        "operation_id": "op-1",
        "tool": "write_file",
        "result": {"ok": True, "value": 1},
    }
    _ = await repo.append_event(session_id="sess-op-idem", kind="operation_result", payload=first_payload)
    second = await repo.append_event(session_id="sess-op-idem", kind="operation_result", payload=first_payload)
    assert second["kind"] == "operation_rejected"
    assert second["error_code"] == "E_DUPLICATE_OPERATION"
    assert second["idempotent_reuse"] is True


@pytest.mark.asyncio
async def test_async_protocol_run_ledger_append_event_flattens_payload_fields(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    appended = await repo.append_event(
        session_id="sess-flat",
        kind="operation_result",
        payload={
            "operation_id": "op-flat",
            "tool": "write_file",
            "result": {"ok": True, "value": 9},
            "step_id": "ISSUE-1:1",
        },
    )
    assert appended["kind"] == "operation_result"
    assert appended["operation_id"] == "op-flat"
    assert appended["tool"] == "write_file"
    assert appended["result"]["ok"] is True
    events = await repo.list_events("sess-flat")
    assert events[0]["operation_id"] == "op-flat"
    assert events[0]["step_id"] == "ISSUE-1:1"


@pytest.mark.asyncio
async def test_async_protocol_run_ledger_append_receipt_assigns_seq_and_digest(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    first = await repo.append_receipt(
        session_id="sess-receipt",
        receipt={
            "run_id": "sess-receipt",
            "step_id": "ISSUE-1:1",
            "operation_id": "op-1",
            "event_seq_range": [1, 1],
            "execution_result": {"ok": True},
        },
    )
    second = await repo.append_receipt(
        session_id="sess-receipt",
        receipt={
            "run_id": "sess-receipt",
            "step_id": "ISSUE-1:2",
            "operation_id": "op-2",
            "event_seq_range": [2, 2],
            "execution_result": {"ok": True},
        },
    )
    assert first["receipt_seq"] == 1
    assert second["receipt_seq"] == 2
    assert len(str(first["receipt_digest"])) == 64
    assert len(str(second["receipt_digest"])) == 64
    rows = await repo.list_receipts("sess-receipt")
    assert [row["receipt_seq"] for row in rows] == [1, 2]


@pytest.mark.asyncio
async def test_async_protocol_run_ledger_append_receipt_dedupes_existing_digest(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    payload = {
        "run_id": "sess-receipt-idem",
        "step_id": "ISSUE-1:1",
        "operation_id": "op-1",
        "event_seq_range": [1, 1],
        "execution_result": {"ok": True},
    }
    first = await repo.append_receipt(session_id="sess-receipt-idem", receipt=payload)
    second = await repo.append_receipt(session_id="sess-receipt-idem", receipt=payload)
    assert first["receipt_seq"] == 1
    assert second["receipt_seq"] == 1
    rows = await repo.list_receipts("sess-receipt-idem")
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_async_protocol_run_ledger_append_receipt_rejects_non_monotonic_seq(tmp_path: Path) -> None:
    repo = AsyncProtocolRunLedgerRepository(tmp_path)
    await repo.append_receipt(
        session_id="sess-receipt-seq",
        receipt={
            "run_id": "sess-receipt-seq",
            "step_id": "ISSUE-1:1",
            "operation_id": "op-1",
            "event_seq_range": [1, 1],
            "execution_result": {"ok": True},
            "receipt_seq": 1,
        },
    )
    with pytest.raises(ValueError, match="E_RECEIPT_SEQ_NON_MONOTONIC"):
        await repo.append_receipt(
            session_id="sess-receipt-seq",
            receipt={
                "run_id": "sess-receipt-seq",
                "step_id": "ISSUE-1:2",
                "operation_id": "op-2",
                "event_seq_range": [2, 2],
                "execution_result": {"ok": True},
                "receipt_seq": 1,
            },
        )
