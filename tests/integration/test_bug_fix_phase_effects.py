"""Real bug-fix persistence, adverse SQL effects and owned event publication."""
import asyncio
import json
import threading
from datetime import UTC, datetime, timedelta
from time import perf_counter

import aiosqlite
import pytest

import orket.application.services.bug_fix_phase_manager as phases
from orket.adapters.vcs.webhook_db import WebhookDatabase

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
START = datetime(2041, 1, 2, tzinfo=UTC)
RESPONSIVENESS_LIMIT_SECONDS = 0.5


def manager(tmp_path, *, now=START):
    return phases.BugFixPhaseManager(
        db=WebhookDatabase(db_path=tmp_path / "phases.sqlite3"), workspace=tmp_path / "workspace",
        now_utc=lambda: now,
    )


async def log_records(owner):
    content = await asyncio.to_thread((owner.workspace / "orket.log").read_text, encoding="utf-8")
    return [json.loads(line) for line in content.splitlines()]


async def install_trigger(owner, sql):
    async with aiosqlite.connect(owner.db.db_path) as connection:
        await connection.execute(sql)
        await connection.commit()


# Layer: integration
async def test_phase_lifecycle_reopens_explicit_values_and_emits_after_persistence(tmp_path):
    owner = manager(tmp_path)
    phase = await owner.start_phase("rock")
    phase.metrics.critical_bugs = 999  # Returned values cannot mutate this owner's accepted state.
    assert owner.active_phases["rock"].metrics.critical_bugs == 0
    reopened = manager(tmp_path, now=START + timedelta(days=2))
    await reopened.update_metrics("rock", ["a", "b", "c", "d"], ["a", "b", "c", "d"])
    assert reopened.active_phases["rock"].metrics.discovery_rate == 2
    assert await reopened.check_and_extend("rock")
    saved = await owner.db.get_bug_fix_phase("rock")
    assert saved.extensions[0]["date"] == "2041-01-04T00:00:00+00:00"
    assert saved.scheduled_end == "2041-01-16T00:00:00+00:00"
    assert await reopened.end_phase("rock") == "rock-phase2"
    completed = await owner.db.get_bug_fix_phase("rock")
    assert completed.actual_end == "2041-01-04T00:00:00+00:00" and completed.status.value == "completed"
    assert "rock" not in reopened.active_phases
    events = [row for row in await log_records(owner) if row["event"].startswith("bug_fix_phase_")]
    assert [row["event"] for row in events] == [
        "bug_fix_phase_started", "bug_fix_phase_extended", "bug_fix_phase_completed",
    ]
    assert events[0]["data"]["ends_at"] == "2041-01-09T00:00:00+00:00"
    assert events[1]["data"]["new_end"] == saved.scheduled_end
    assert events[2]["data"]["phase2_rock"] == completed.phase2_rock_id


# Layer: integration
@pytest.mark.parametrize("operation", ["metrics", "extend", "end"])
async def test_refused_sql_transition_does_not_change_cache_or_emit_success(tmp_path, operation):
    owner = manager(tmp_path)
    await owner.start_phase("rock")
    await owner.update_metrics("rock", ["a"], ["a", "b", "c", "d"])
    before = owner.active_phases["rock"].model_dump()
    events = await log_records(owner)
    await install_trigger(owner, "CREATE TRIGGER refuse BEFORE INSERT ON bug_fix_phases "
                                "BEGIN SELECT RAISE(ABORT, 'fixture refusal'); END")
    with pytest.raises(aiosqlite.IntegrityError, match="fixture refusal"):
        if operation == "metrics":
            await owner.update_metrics("rock", ["changed"], [])
        elif operation == "extend":
            await owner.check_and_extend("rock")
        else:
            await owner.end_phase("rock")
    assert owner.active_phases["rock"].model_dump() == before
    assert (await manager(tmp_path).db.get_bug_fix_phase("rock")).model_dump() == before
    assert await log_records(owner) == events


# Layer: integration
async def test_acknowledged_but_missing_sql_effect_cannot_publish_a_started_event(tmp_path):
    owner = manager(tmp_path)
    assert await owner.db.get_bug_fix_phase("rock") is None
    await install_trigger(owner, "CREATE TRIGGER erase AFTER INSERT ON bug_fix_phases "
                                "BEGIN DELETE FROM bug_fix_phases WHERE rock_id = NEW.rock_id; END")
    with pytest.raises(phases.BugFixPhasePersistenceError, match="did not round-trip"):
        await owner.start_phase("rock")
    assert not owner.active_phases and await owner.db.get_bug_fix_phase("rock") is None
    assert not await asyncio.to_thread((owner.workspace / "orket.log").exists)


# Layer: integration
@pytest.mark.parametrize("interruption", ["cancel", "timeout"])
async def test_cancelled_publication_drains_real_event_and_keeps_loop_responsive(tmp_path, monkeypatch, interruption):
    owner = manager(tmp_path)
    started, release = threading.Event(), threading.Event()
    original = phases.log_event

    def held_event(*args):
        started.set()
        if not release.wait(4):
            raise TimeoutError("fixture publication was not released")
        original(*args)

    async def dispatch():
        async with asyncio.timeout(0.1 if interruption == "timeout" else 5):
            return await owner.start_phase("rock")

    monkeypatch.setattr(phases, "log_event", held_event)
    task = asyncio.create_task(dispatch())
    waiting = None
    try:
        assert await asyncio.wait_for(asyncio.to_thread(started.wait, 3), 3.5)
        waiting = asyncio.create_task(owner.start_phase("not-admitted"))
        began = perf_counter()
        assert (await owner.db.get_bug_fix_phase("rock")).started_at == START.isoformat()
        await asyncio.sleep(0)
        assert perf_counter() - began < RESPONSIVENESS_LIMIT_SECONDS
        if interruption == "cancel":
            task.cancel()
        await asyncio.sleep(0.15)
        if interruption == "cancel":
            task.cancel()
        assert not task.done() and not waiting.done()
    finally:
        if waiting is not None:
            waiting.cancel()
        release.set()
        result, = await asyncio.gather(task, return_exceptions=True)
        if waiting is not None:
            await asyncio.gather(waiting, return_exceptions=True)
    assert isinstance(result, TimeoutError if interruption == "timeout" else asyncio.CancelledError)
    assert (await log_records(owner))[-1]["event"] == "bug_fix_phase_started"
    assert await owner.db.get_bug_fix_phase("not-admitted") is None
