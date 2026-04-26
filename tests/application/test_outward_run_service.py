from __future__ import annotations

import pytest

from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.application.services.outward_run_service import (
    OutwardRunConflictError,
    OutwardRunService,
    OutwardRunValidationError,
)


def _service(db_path) -> OutwardRunService:
    return OutwardRunService(
        run_store=OutwardRunStore(db_path),
        event_store=OutwardRunEventStore(db_path),
        run_id_factory=lambda: "generated",
        utc_now=lambda: "2026-04-25T12:00:00+00:00",
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_outward_run_submit_is_idempotent_and_writes_initial_event(tmp_path) -> None:
    """Layer: integration. Verifies Phase 1 submission persistence plus initial run_events row."""
    db_path = tmp_path / "phase1.sqlite3"
    service = _service(db_path)

    payload = {
        "run_id": "run-phase1",
        "task": {"description": "Demo", "instruction": "Do the work"},
        "policy_overrides": {"max_turns": 5, "approval_required_tools": ["write_file"]},
    }

    first = await service.submit(payload)
    second = await service.submit({**payload, "task": {"description": "Changed", "instruction": "Still valid"}})

    assert second == first
    assert first.to_status_payload() == {
        "run_id": "run-phase1",
        "status": "queued",
        "namespace": "issue:run-phase1",
        "submitted_at": "2026-04-25T12:00:00+00:00",
        "started_at": None,
        "completed_at": None,
        "stop_reason": None,
        "current_turn": 0,
        "max_turns": 5,
        "pending_proposals": [],
    }

    events = await OutwardRunEventStore(db_path).list_for_run("run-phase1")
    assert [event.event_type for event in events] == ["run_submitted"]
    assert events[0].payload["task_description"] == "Demo"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_outward_run_submit_rejects_missing_instruction(tmp_path) -> None:
    """Layer: unit. Verifies invalid submission is rejected before execution state is created."""
    with pytest.raises(OutwardRunValidationError, match="task.instruction is required"):
        await _service(tmp_path / "phase1.sqlite3").submit({"task": {"description": "Demo"}})


@pytest.mark.integration
@pytest.mark.asyncio
async def test_outward_run_submit_rejects_active_namespace_conflict(tmp_path) -> None:
    """Layer: integration. Verifies active namespace conflicts fail closed."""
    service = _service(tmp_path / "phase1.sqlite3")
    await service.submit(
        {
            "run_id": "run-a",
            "namespace": "issue:shared",
            "task": {"description": "A", "instruction": "Do A"},
        }
    )

    with pytest.raises(OutwardRunConflictError, match="namespace already has an active run"):
        await service.submit(
            {
                "run_id": "run-b",
                "namespace": "issue:shared",
                "task": {"description": "B", "instruction": "Do B"},
            }
        )
