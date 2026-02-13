import json

import aiosqlite
import pytest

from orket.domain.bug_fix_phase import BugFixPhase, BugFixPhaseStatus
from orket.adapters.vcs.webhook_db import WebhookDatabase


@pytest.fixture
def webhook_db(tmp_path):
    return WebhookDatabase(db_path=tmp_path / "webhook_test.db")


@pytest.mark.asyncio
async def test_get_pr_cycle_count_defaults_zero(webhook_db):
    count = await webhook_db.get_pr_cycle_count("org/repo", 1)
    assert count == 0


@pytest.mark.asyncio
async def test_increment_pr_cycle_starts_at_one(webhook_db):
    count = await webhook_db.increment_pr_cycle("org/repo", 1)
    assert count == 1


@pytest.mark.asyncio
async def test_increment_pr_cycle_accumulates(webhook_db):
    await webhook_db.increment_pr_cycle("org/repo", 1)
    count = await webhook_db.increment_pr_cycle("org/repo", 1)
    assert count == 2


@pytest.mark.asyncio
async def test_increment_pr_cycle_isolated_per_pr(webhook_db):
    await webhook_db.increment_pr_cycle("org/repo", 1)
    await webhook_db.increment_pr_cycle("org/repo", 2)

    count1 = await webhook_db.get_pr_cycle_count("org/repo", 1)
    count2 = await webhook_db.get_pr_cycle_count("org/repo", 2)

    assert count1 == 1
    assert count2 == 1


@pytest.mark.asyncio
async def test_add_failure_reason_records_cycle_number(webhook_db):
    await webhook_db.increment_pr_cycle("org/repo", 7)
    await webhook_db.add_failure_reason("org/repo", 7, "bot", "first reason")

    reasons = await webhook_db.get_failure_reasons("org/repo", 7)

    assert len(reasons) == 1
    assert reasons[0]["cycle_number"] == 1
    assert reasons[0]["reviewer"] == "bot"
    assert reasons[0]["reason"] == "first reason"


@pytest.mark.asyncio
async def test_get_failure_reasons_ordered_by_cycle(webhook_db):
    await webhook_db.increment_pr_cycle("org/repo", 7)
    await webhook_db.add_failure_reason("org/repo", 7, "bot", "cycle1")
    await webhook_db.increment_pr_cycle("org/repo", 7)
    await webhook_db.add_failure_reason("org/repo", 7, "bot", "cycle2")

    reasons = await webhook_db.get_failure_reasons("org/repo", 7)

    assert [r["cycle_number"] for r in reasons] == [1, 2]
    assert [r["reason"] for r in reasons] == ["cycle1", "cycle2"]


@pytest.mark.asyncio
async def test_close_pr_cycle_updates_status(webhook_db):
    await webhook_db.increment_pr_cycle("org/repo", 9)
    await webhook_db.close_pr_cycle("org/repo", 9, status="rejected")

    async with aiosqlite.connect(webhook_db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        row = await (await conn.execute(
            "SELECT status FROM pr_review_cycles WHERE pr_key = ?",
            ("org/repo#9",),
        )).fetchone()

    assert row["status"] == "rejected"


@pytest.mark.asyncio
async def test_get_active_prs_returns_only_active(webhook_db):
    await webhook_db.increment_pr_cycle("org/repo", 1)
    await webhook_db.increment_pr_cycle("org/repo", 2)
    await webhook_db.close_pr_cycle("org/repo", 2, status="merged")

    active = await webhook_db.get_active_prs()

    assert len(active) == 1
    assert active[0]["pr_number"] == 1


@pytest.mark.asyncio
async def test_log_webhook_event_persists_row(webhook_db):
    await webhook_db.log_webhook_event("pull_request", "org/repo#1", "{\"k\":1}", "ok")

    async with aiosqlite.connect(webhook_db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        row = await (await conn.execute(
            "SELECT event_type, pr_key, payload, result FROM webhook_events"
        )).fetchone()

    assert row["event_type"] == "pull_request"
    assert row["pr_key"] == "org/repo#1"
    assert row["result"] == "ok"


@pytest.mark.asyncio
async def test_get_bug_fix_phase_missing_returns_none(webhook_db):
    phase = await webhook_db.get_bug_fix_phase("missing")
    assert phase is None


@pytest.mark.asyncio
async def test_save_and_get_bug_fix_phase_round_trip(webhook_db):
    phase = BugFixPhase(id="phase-1", rock_id="ROCK-1", status=BugFixPhaseStatus.ACTIVE)

    await webhook_db.save_bug_fix_phase(phase)
    loaded = await webhook_db.get_bug_fix_phase("ROCK-1")

    assert loaded is not None
    assert loaded.rock_id == "ROCK-1"
    assert loaded.status == BugFixPhaseStatus.ACTIVE


@pytest.mark.asyncio
async def test_save_bug_fix_phase_overwrites_existing(webhook_db):
    phase = BugFixPhase(id="phase-1", rock_id="ROCK-1", status=BugFixPhaseStatus.ACTIVE)
    await webhook_db.save_bug_fix_phase(phase)

    phase.status = BugFixPhaseStatus.EXTENDED
    await webhook_db.save_bug_fix_phase(phase)

    loaded = await webhook_db.get_bug_fix_phase("ROCK-1")
    assert loaded.status == BugFixPhaseStatus.EXTENDED


@pytest.mark.asyncio
async def test_get_active_prs_includes_cycle_count(webhook_db):
    await webhook_db.increment_pr_cycle("org/repo", 5)
    await webhook_db.increment_pr_cycle("org/repo", 5)

    active = await webhook_db.get_active_prs()

    assert len(active) == 1
    assert active[0]["cycle_count"] == 2


@pytest.mark.asyncio
async def test_increment_then_failure_reason_for_multiple_prs(webhook_db):
    await webhook_db.increment_pr_cycle("org/repo", 10)
    await webhook_db.add_failure_reason("org/repo", 10, "bot", "reason-a")

    await webhook_db.increment_pr_cycle("org/repo", 11)
    await webhook_db.add_failure_reason("org/repo", 11, "bot", "reason-b")

    reasons_10 = await webhook_db.get_failure_reasons("org/repo", 10)
    reasons_11 = await webhook_db.get_failure_reasons("org/repo", 11)

    assert reasons_10[0]["reason"] == "reason-a"
    assert reasons_11[0]["reason"] == "reason-b"


@pytest.mark.asyncio
async def test_close_pr_cycle_default_status_closed(webhook_db):
    await webhook_db.increment_pr_cycle("org/repo", 15)
    await webhook_db.close_pr_cycle("org/repo", 15)

    async with aiosqlite.connect(webhook_db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        row = await (await conn.execute(
            "SELECT status FROM pr_review_cycles WHERE pr_key = ?",
            ("org/repo#15",),
        )).fetchone()

    assert row["status"] == "closed"


@pytest.mark.asyncio
async def test_webhook_event_payload_kept_as_text(webhook_db):
    payload = json.dumps({"nested": {"value": 3}})
    await webhook_db.log_webhook_event("pull_request_review", None, payload, "processed")

    async with aiosqlite.connect(webhook_db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        row = await (await conn.execute(
            "SELECT payload, pr_key FROM webhook_events"
        )).fetchone()

    assert row["payload"] == payload
    assert row["pr_key"] is None

