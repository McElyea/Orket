# Layer: integration

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from orket.adapters.storage.async_governed_agent_schedule_repository import (
    AsyncGovernedAgentScheduleRepository,
)
from orket.adapters.storage.async_governed_agent_wake_repository import (
    AsyncGovernedAgentWakeRepository,
)
from orket.application.services.governed_agent_scheduled_wake_service import (
    GovernedAgentScheduledWakeService,
)
from tests.runtime.governed_agent_test_support import agent_request

pytestmark = pytest.mark.integration


def _dispatch() -> dict:
    return {
        "schema_version": "governed_agent_wake_dispatch.v1",
        "request": agent_request(),
        "creation_timestamp_utc": "2026-09-07T18:00:00Z",
        "decision_timestamps_utc": [
            "2026-09-07T18:00:01Z",
            "2026-09-07T18:00:02Z",
        ],
        "next_lease_expiries_utc": ["2026-09-07T18:05:00Z"],
    }


def _occurrence(local_time: str, *, fold: int = 0) -> dict:
    return {
        "scheduled_for_local": local_time,
        "fold": fold,
        "target_kind": "new_run",
        "workload_id": "governed-agent-loop",
        "dispatch": _dispatch(),
    }


def _evaluation_payload(
    *,
    evaluation_id: str = "schedule-evaluation:1",
    observed_at_utc: str = "2026-09-07T18:00:00Z",
    missed_policy: str = "fire_once",
    occurrences: list[dict] | None = None,
) -> dict:
    return {
        "evaluation_id": evaluation_id,
        "timezone": "America/Denver",
        "observed_at_utc": observed_at_utc,
        "misfire_grace_seconds": 0,
        "missed_policy": missed_policy,
        "coalescing_policy": "latest",
        "occurrences": occurrences
        or [
            _occurrence("2026-09-07T11:00:00"),
            _occurrence("2026-09-07T12:00:00"),
        ],
    }


@pytest.mark.asyncio
async def test_schedule_evaluation_atomically_coalesces_and_survives_restart(tmp_path: Path) -> None:
    """Layer: integration. Stable schedule evaluation and selected wake persist atomically."""
    db_path = tmp_path / "agent.sqlite3"
    service = GovernedAgentScheduledWakeService(
        repository=AsyncGovernedAgentScheduleRepository(db_path)
    )
    payload = _evaluation_payload()

    admitted = await service.evaluate(schedule_id="daily-report", payload=payload)
    replayed = await service.evaluate(schedule_id="daily-report", payload=payload)
    contradicted = await service.evaluate(
        schedule_id="daily-report",
        payload={**payload, "misfire_grace_seconds": 1},
    )

    assert admitted.status == "enqueued" and admitted.wake is not None
    assert replayed.status == "idempotent" and replayed.wake == admitted.wake
    assert contradicted.status == "conflict" and contradicted.evaluation == admitted.evaluation
    assert admitted.wake.source == "scheduled"
    trigger = admitted.wake.payload["trigger"]
    assert trigger["schema_version"] == "governed_agent_schedule_trigger.v1"
    assert trigger["timezone"] == "America/Denver"
    assert trigger["scheduled_for_utc"] == "2026-09-07T18:00:00.000000Z"
    assert trigger["missed"] is False
    assert trigger["coalesced_occurrence_ids"] == [
        admitted.evaluation.coalesced_occurrence_ids[0]
    ]

    restarted = GovernedAgentScheduledWakeService(
        repository=AsyncGovernedAgentScheduleRepository(db_path)
    )
    evaluations = await restarted.list_evaluations(schedule_id="daily-report")
    wakes = await AsyncGovernedAgentWakeRepository(db_path).list_wakes()
    assert evaluations == (admitted.evaluation,)
    assert wakes == (admitted.wake,)


@pytest.mark.asyncio
async def test_missed_skip_is_durable_without_enqueuing_a_wake(tmp_path: Path) -> None:
    """Layer: integration. Missed skip records durable truth and admits no dispatch work."""
    db_path = tmp_path / "agent.sqlite3"
    service = GovernedAgentScheduledWakeService(
        repository=AsyncGovernedAgentScheduleRepository(db_path)
    )
    payload = _evaluation_payload(
        observed_at_utc="2026-09-07T18:10:00Z",
        missed_policy="skip",
        occurrences=[_occurrence("2026-09-07T12:00:00")],
    )

    skipped = await service.evaluate(schedule_id="daily-report", payload=payload)

    assert skipped.status == "skipped" and skipped.wake is None
    assert skipped.evaluation.selected_occurrence_id is None
    assert len(skipped.evaluation.skipped_occurrence_ids) == 1
    assert await AsyncGovernedAgentWakeRepository(db_path).list_wakes() == ()
    assert await service.list_evaluations(schedule_id="daily-report") == (skipped.evaluation,)


@pytest.mark.asyncio
async def test_schedule_receipt_failure_rolls_back_selected_wake(tmp_path: Path) -> None:
    """Layer: integration. A failed evaluation receipt cannot leave an authority-free scheduled wake."""
    db_path = tmp_path / "agent.sqlite3"
    service = GovernedAgentScheduledWakeService(
        repository=AsyncGovernedAgentScheduleRepository(db_path)
    )
    await service.list_evaluations(schedule_id="daily-report")
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            """
            CREATE TRIGGER reject_schedule_evaluation
            BEFORE INSERT ON governed_agent_schedule_evaluations
            BEGIN SELECT RAISE(ABORT, 'forced schedule receipt failure'); END
            """
        )
        await conn.commit()

    with pytest.raises(aiosqlite.IntegrityError, match="forced schedule receipt failure"):
        await service.evaluate(
            schedule_id="daily-report",
            payload=_evaluation_payload(evaluation_id="schedule-evaluation:rollback"),
        )

    assert await AsyncGovernedAgentWakeRepository(db_path).list_wakes() == ()


@pytest.mark.asyncio
async def test_schedule_timezone_rejects_nonexistent_time_and_disambiguates_fold(tmp_path: Path) -> None:
    """Layer: integration. IANA conversion fails closed at gaps and preserves both DST folds."""
    service = GovernedAgentScheduledWakeService(
        repository=AsyncGovernedAgentScheduleRepository(tmp_path / "agent.sqlite3")
    )
    nonexistent = _evaluation_payload(
        observed_at_utc="2026-03-08T10:00:00Z",
        occurrences=[_occurrence("2026-03-08T02:30:00")],
    )
    with pytest.raises(ValueError, match="E_AGENT_SCHEDULE_LOCAL_TIME_NONEXISTENT"):
        await service.evaluate(schedule_id="dst-report", payload=nonexistent)

    ambiguous = _evaluation_payload(
        evaluation_id="schedule-evaluation:dst-fold",
        observed_at_utc="2026-11-01T08:30:00Z",
        occurrences=[
            _occurrence("2026-11-01T01:30:00", fold=0),
            _occurrence("2026-11-01T01:30:00", fold=1),
        ],
    )
    admitted = await service.evaluate(schedule_id="dst-report", payload=ambiguous)

    assert admitted.status == "enqueued" and admitted.wake is not None
    assert admitted.wake.payload["trigger"]["fold"] == 1
    assert admitted.wake.payload["trigger"]["scheduled_for_utc"] == "2026-11-01T08:30:00.000000Z"
    assert len(admitted.evaluation.coalesced_occurrence_ids) == 1
