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
