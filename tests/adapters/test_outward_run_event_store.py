from __future__ import annotations

import asyncio

import pytest

from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.sqlite_connection import current_journal_mode
from orket.core.domain.outward_run_events import LedgerEvent


def _event(index: int) -> LedgerEvent:
    return LedgerEvent(
        event_id=f"evt-{index:03d}",
        event_type="synthetic_phase0",
        run_id="run-phase0",
        turn=index,
        agent_id="agent:test",
        at=f"2026-04-25T12:00:{index:02d}Z",
        payload={"index": index, "status": "ok"},
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_outward_run_event_store_writes_and_reads_synthetic_event(tmp_path) -> None:
    """Layer: integration. Verifies Phase 0 run_events persistence without implying run submission exists."""
    db_path = tmp_path / "outward-run-events.db"
    store = OutwardRunEventStore(db_path)

    written = await store.append(_event(1))
    loaded = await store.get(written.event_id)

    assert loaded == written
    assert await current_journal_mode(db_path) == "wal"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_outward_run_event_store_handles_concurrent_writes_without_database_locked(tmp_path) -> None:
    """Layer: integration. Verifies real SQLite WAL path accepts concurrent synthetic event writes."""
    db_path = tmp_path / "outward-run-events-concurrent.db"
    await OutwardRunEventStore(db_path).ensure_initialized()

    async def _append(index: int) -> None:
        await OutwardRunEventStore(db_path).append(_event(index))

    await asyncio.gather(*(_append(index) for index in range(20)))

    events = await OutwardRunEventStore(db_path).list_for_run("run-phase0")
    assert [event.event_id for event in events] == [f"evt-{index:03d}" for index in range(20)]
