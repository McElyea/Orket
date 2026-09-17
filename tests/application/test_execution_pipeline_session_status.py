"""Real scheduler reservations survive explicit fresh-run requeue after publication."""
from __future__ import annotations

import asyncio
import json
import re
from contextlib import asynccontextmanager

import pytest

from orket.application.services.orchestrator_issue_control_plane_support import (
    lease_id_for_run as orchestrator_lease_id_for_run,
)
from orket.application.services.orchestrator_issue_control_plane_support import scheduler_holder_ref_for_issue
from orket.core.domain import LeaseStatus, ReservationStatus
from orket.runtime.execution_pipeline import ExecutionPipeline
from orket.schema import CardStatus

pytestmark = pytest.mark.integration


def _write_assets(root, epic_id):
    assets = {
        "teams/standard.json": {"name": "standard", "seats": {
            "lead_architect": {"name": "Lead", "roles": ["lead_architect"]}}},
        f"epics/{epic_id}.json": {
            "id": epic_id, "name": epic_id, "type": "epic", "team": "standard", "environment": "standard",
            "description": "Session status and scheduler requeue", "architecture_governance": {
                "idesign": False, "pattern": "Standard"},
            "issues": [{"id": "ISSUE-1", "summary": "Do work", "seat": "lead_architect",
                        "priority": "High", "depends_on": []}],
        },
    }
    for name, payload in assets.items():
        path = root / "model" / "core" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")


@asynccontextmanager
async def status_pipeline(root, workspace, db_path, epic_id):
    await asyncio.to_thread(_write_assets, root, epic_id)
    pipeline = await asyncio.to_thread(ExecutionPipeline, workspace=workspace, department="core",
                                       db_path=db_path, config_root=root)
    try:
        yield pipeline
    finally:
        await pipeline.close()


async def no_work(**_kwargs):
    return None


async def assert_scheduler_publication(pipeline, session_id):
    repository = pipeline.orchestrator.control_plane_repository
    reservation = await repository.get_latest_reservation_record_for_holder_ref(
        holder_ref=scheduler_holder_ref_for_issue(session_id=session_id, issue_id="ISSUE-1"))
    assert reservation is not None
    run_id = reservation.reservation_id.split("-reservation:", 1)[-1]
    run = await pipeline.orchestrator.control_plane_execution_repository.get_run_record(run_id=run_id)
    reservation_history = await repository.list_reservation_records(reservation_id=reservation.reservation_id)
    lease_history = await repository.list_lease_records(lease_id=orchestrator_lease_id_for_run(run_id=run_id))
    assert run is not None and run.final_truth_record_id is not None
    assert [record.status for record in reservation_history] == [ReservationStatus.ACTIVE, ReservationStatus.PROMOTED_TO_LEASE]
    assert [record.status for record in lease_history] == [LeaseStatus.ACTIVE, LeaseStatus.RELEASED]


@pytest.mark.asyncio
async def test_run_epic_marks_session_incomplete_when_backlog_not_terminal(test_root, workspace, db_path, monkeypatch):
    """Layer: integration. A returned workload without acceptance persists incomplete."""
    async with status_pipeline(test_root, workspace, db_path, "status_epic") as pipeline:
        monkeypatch.setattr(pipeline.orchestrator, "execute_epic", no_work)
        await pipeline.run_epic("status_epic", build_id="build", session_id="session")
        runs = await pipeline.sessions.get_recent_runs(limit=1)
        assert runs[0]["id"] == "session" and runs[0]["status"] == "incomplete"
        issues = await pipeline.async_cards.get_by_build("build")
        assert issues[0].status == CardStatus.READY


@pytest.mark.asyncio
async def test_run_epic_marks_terminal_failure_when_backlog_blocked(test_root, workspace, db_path, monkeypatch):
    """Layer: integration. Blocked work persists a terminal failure through publication."""
    async with status_pipeline(test_root, workspace, db_path, "status_epic_blocked") as pipeline:
        async def block_work(**_kwargs):
            await pipeline.async_cards.update_status("ISSUE-1", CardStatus.BLOCKED)

        monkeypatch.setattr(pipeline.orchestrator, "execute_epic", block_work)
        await pipeline.run_epic("status_epic_blocked", build_id="build", session_id="session")
        run = await pipeline.sessions.get_session("session")
        assert run is not None and run["status"] == "terminal_failure"


@pytest.mark.asyncio
# Layer: integration
async def test_run_epic_resume_requeue_publishes_scheduler_reservation_and_lease_truth(test_root, workspace, db_path, monkeypatch):
    """Layer: integration. Fresh execution requeues stalled work without rewriting a prior invocation."""
    async with status_pipeline(test_root, workspace, db_path, "resume_requeue_epic") as pipeline:
        monkeypatch.setattr(pipeline.orchestrator, "execute_epic", no_work)
        await pipeline.run_epic("resume_requeue_epic", build_id="build", session_id="original")
        original = await pipeline.run_ledger.get_run("original")
        await pipeline.async_cards.update_status("ISSUE-1", CardStatus.IN_PROGRESS, reason="seed_stalled_issue")
        observed = await pipeline.run_epic('resume_requeue_epic', build_id='build', session_id='original')
        assert observed.observation == "unresolved" and not observed.succeeded
        assert re.search('E_EPIC_PUBLICATION_ACCEPTANCE_CHANGED', observed.reason or "")
        assert (await pipeline.async_cards.get_by_id("ISSUE-1")).status == CardStatus.IN_PROGRESS
        await pipeline.run_epic("resume_requeue_epic", build_id="build", session_id="fresh")
        await assert_scheduler_publication(pipeline, "fresh")
        assert (await pipeline.async_cards.get_by_id("ISSUE-1")).status == CardStatus.READY
        assert await pipeline.run_ledger.get_run("original") == original
        assert (await pipeline.run_ledger.get_run("fresh"))["status"] == "incomplete"


@pytest.mark.asyncio
async def test_run_epic_target_issue_resume_publishes_scheduler_reservation_and_lease_truth(test_root, workspace, db_path, monkeypatch):
    """Layer: integration. A changed target needs a fresh invocation and retains scheduler ownership."""
    async with status_pipeline(test_root, workspace, db_path, "resume_target_epic") as pipeline:
        monkeypatch.setattr(pipeline.orchestrator, "execute_epic", no_work)
        await pipeline.run_epic("resume_target_epic", build_id="build", session_id="original")
        original = await pipeline.run_ledger.get_run("original")
        await pipeline.async_cards.update_status("ISSUE-1", CardStatus.BLOCKED, reason="seed_blocked_issue")
        with pytest.raises(ValueError, match="E_EPIC_PREPARATION_REQUEST_CONFLICT"):
            await pipeline.run_epic("resume_target_epic", build_id="build", session_id="original", target_issue_id="ISSUE-1")
        assert (await pipeline.async_cards.get_by_id("ISSUE-1")).status == CardStatus.BLOCKED
        await pipeline.run_epic("resume_target_epic", build_id="build", session_id="fresh", target_issue_id="ISSUE-1")
        await assert_scheduler_publication(pipeline, "fresh")
        assert (await pipeline.async_cards.get_by_id("ISSUE-1")).status == CardStatus.READY
        assert await pipeline.run_ledger.get_run("original") == original
        assert (await pipeline.run_ledger.get_run("fresh"))["status"] == "incomplete"
