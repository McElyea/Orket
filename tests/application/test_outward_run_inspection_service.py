from __future__ import annotations

from dataclasses import replace

import pytest

from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.application.services.outward_run_inspection_service import OutwardRunInspectionService
from orket.application.services.outward_run_service import OutwardRunService
from orket.core.domain.outward_run_events import LedgerEvent


@pytest.mark.integration
@pytest.mark.asyncio
async def test_outward_run_inspection_filters_summary_and_is_read_only(tmp_path) -> None:
    """Layer: integration. Verifies event filtering and summary derivation do not mutate run state."""
    db_path = tmp_path / "phase3-inspection.sqlite3"
    run_store = OutwardRunStore(db_path)
    event_store = OutwardRunEventStore(db_path)
    run = await OutwardRunService(
        run_store=run_store,
        event_store=event_store,
        run_id_factory=lambda: "generated",
        utc_now=lambda: "2026-04-25T12:00:00+00:00",
    ).submit({"run_id": "run-inspect", "task": {"description": "Inspect", "instruction": "Do work"}})
    await run_store.update(replace(run, status="completed", current_turn=1, completed_at="2026-04-25T12:01:00+00:00"))
    await event_store.append(
        LedgerEvent(
            event_id="run:run-inspect:tool",
            event_type="tool_invoked",
            run_id="run-inspect",
            turn=1,
            agent_id="outward-agent",
            at="2026-04-25T12:00:30+00:00",
            payload={"connector_name": "write_file", "outcome": "success"},
        )
    )
    service = OutwardRunInspectionService(run_store=OutwardRunStore(db_path), event_store=OutwardRunEventStore(db_path))

    before_events = await event_store.list_for_run("run-inspect")
    filtered = await service.events("run-inspect", from_turn=1, types=("tool_invoked",), agent_id="outward-agent")
    summary = await service.summary("run-inspect")
    after_events = await event_store.list_for_run("run-inspect")
    after_run = await run_store.get("run-inspect")

    assert [event["event_type"] for event in filtered["events"]] == ["tool_invoked"]
    assert summary["event_count"] == 2
    assert summary["event_counts"] == {"run_submitted": 1, "tool_invoked": 1}
    assert summary["terminal"] is True
    assert len(after_events) == len(before_events)
    assert after_run is not None
    assert after_run.status == "completed"
