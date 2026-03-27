import json
from pathlib import Path

import pytest

from orket.application.services.orchestrator_issue_control_plane_support import (
    lease_id_for_run as orchestrator_lease_id_for_run,
    scheduler_holder_ref_for_issue,
)
from orket.core.domain import LeaseStatus, ReservationStatus
from orket.runtime.execution_pipeline import ExecutionPipeline
from orket.schema import CardStatus


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.asyncio
async def test_run_epic_marks_session_incomplete_when_backlog_not_terminal(
    test_root,
    workspace,
    db_path,
    monkeypatch,
):
    _write_json(
        test_root / "model" / "core" / "teams" / "standard.json",
        {
            "name": "standard",
            "seats": {
                "lead_architect": {
                    "name": "Lead",
                    "roles": ["lead_architect"],
                }
            },
        },
    )
    _write_json(
        test_root / "model" / "core" / "epics" / "status_epic.json",
        {
            "id": "status_epic",
            "name": "status_epic",
            "type": "epic",
            "team": "standard",
            "environment": "standard",
            "description": "Session status check",
            "architecture_governance": {"idesign": False, "pattern": "Standard"},
            "issues": [
                {
                    "id": "ISSUE-1",
                    "summary": "Do work",
                    "seat": "lead_architect",
                    "priority": "High",
                    "depends_on": [],
                }
            ],
        },
    )

    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
    )

    async def _no_op_execute_epic(**_kwargs):
        return None

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _no_op_execute_epic)

    await pipeline.run_epic("status_epic", build_id="build-status-epic", session_id="sess-status-epic")

    runs = await pipeline.sessions.get_recent_runs(limit=1)
    assert runs[0]["id"] == "sess-status-epic"
    assert runs[0]["status"] == "incomplete"

    issues = await pipeline.async_cards.get_by_build("build-status-epic")
    assert issues[0].status == CardStatus.READY


@pytest.mark.asyncio
async def test_run_epic_marks_terminal_failure_when_backlog_blocked(
    test_root,
    workspace,
    db_path,
    monkeypatch,
):
    _write_json(
        test_root / "model" / "core" / "teams" / "standard.json",
        {
            "name": "standard",
            "seats": {
                "lead_architect": {
                    "name": "Lead",
                    "roles": ["lead_architect"],
                }
            },
        },
    )
    _write_json(
        test_root / "model" / "core" / "epics" / "status_epic_blocked.json",
        {
            "id": "status_epic_blocked",
            "name": "status_epic_blocked",
            "type": "epic",
            "team": "standard",
            "environment": "standard",
            "description": "Session terminal non-success check",
            "architecture_governance": {"idesign": False, "pattern": "Standard"},
            "issues": [
                {
                    "id": "ISSUE-1",
                    "summary": "Do work",
                    "seat": "lead_architect",
                    "priority": "High",
                    "depends_on": [],
                }
            ],
        },
    )

    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
    )

    async def _blocked_execute_epic(**_kwargs):
        await pipeline.async_cards.update_status("ISSUE-1", CardStatus.BLOCKED)
        return None

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _blocked_execute_epic)

    await pipeline.run_epic(
        "status_epic_blocked",
        build_id="build-status-epic-blocked",
        session_id="sess-status-epic-blocked",
    )

    runs = await pipeline.sessions.get_recent_runs(limit=5)
    run = next((r for r in runs if r["id"] == "sess-status-epic-blocked"), None)
    assert run is not None
    assert run["status"] == "terminal_failure"


@pytest.mark.asyncio
async def test_run_epic_resume_requeue_publishes_scheduler_reservation_and_lease_truth(
    test_root,
    workspace,
    db_path,
    monkeypatch,
):
    _write_json(
        test_root / "model" / "core" / "teams" / "standard.json",
        {
            "name": "standard",
            "seats": {
                "lead_architect": {
                    "name": "Lead",
                    "roles": ["lead_architect"],
                }
            },
        },
    )
    _write_json(
        test_root / "model" / "core" / "epics" / "resume_requeue_epic.json",
        {
            "id": "resume_requeue_epic",
            "name": "resume_requeue_epic",
            "type": "epic",
            "team": "standard",
            "environment": "standard",
            "description": "Resume requeue control-plane proof",
            "architecture_governance": {"idesign": False, "pattern": "Standard"},
            "issues": [
                {
                    "id": "ISSUE-1",
                    "summary": "Do work",
                    "seat": "lead_architect",
                    "priority": "High",
                    "depends_on": [],
                }
            ],
        },
    )

    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
    )

    async def _no_op_execute_epic(**_kwargs):
        return None

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _no_op_execute_epic)

    await pipeline.run_epic(
        "resume_requeue_epic",
        build_id="build-resume-requeue",
        session_id="sess-resume-requeue",
    )
    await pipeline.async_cards.update_status("ISSUE-1", CardStatus.IN_PROGRESS, reason="seed_stalled_issue")

    await pipeline.run_epic(
        "resume_requeue_epic",
        build_id="build-resume-requeue",
        session_id="sess-resume-requeue",
    )

    latest_reservation = await pipeline.orchestrator.control_plane_repository.get_latest_reservation_record_for_holder_ref(
        holder_ref=scheduler_holder_ref_for_issue(session_id="sess-resume-requeue", issue_id="ISSUE-1")
    )
    assert latest_reservation is not None
    run_id = latest_reservation.reservation_id.split("-reservation:", 1)[-1]
    run = await pipeline.orchestrator.control_plane_execution_repository.get_run_record(run_id=run_id)
    reservation_history = await pipeline.orchestrator.control_plane_repository.list_reservation_records(
        reservation_id=latest_reservation.reservation_id
    )
    lease_history = await pipeline.orchestrator.control_plane_repository.list_lease_records(
        lease_id=orchestrator_lease_id_for_run(run_id=run_id)
    )

    assert run is not None
    assert run.final_truth_record_id is not None
    assert [record.status for record in reservation_history] == [
        ReservationStatus.ACTIVE,
        ReservationStatus.PROMOTED_TO_LEASE,
    ]
    assert [record.status for record in lease_history] == [
        LeaseStatus.ACTIVE,
        LeaseStatus.RELEASED,
    ]


@pytest.mark.asyncio
async def test_run_epic_target_issue_resume_publishes_scheduler_reservation_and_lease_truth(
    test_root,
    workspace,
    db_path,
    monkeypatch,
):
    _write_json(
        test_root / "model" / "core" / "teams" / "standard.json",
        {
            "name": "standard",
            "seats": {
                "lead_architect": {
                    "name": "Lead",
                    "roles": ["lead_architect"],
                }
            },
        },
    )
    _write_json(
        test_root / "model" / "core" / "epics" / "resume_target_epic.json",
        {
            "id": "resume_target_epic",
            "name": "resume_target_epic",
            "type": "epic",
            "team": "standard",
            "environment": "standard",
            "description": "Resume target control-plane proof",
            "architecture_governance": {"idesign": False, "pattern": "Standard"},
            "issues": [
                {
                    "id": "ISSUE-1",
                    "summary": "Do work",
                    "seat": "lead_architect",
                    "priority": "High",
                    "depends_on": [],
                }
            ],
        },
    )

    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
    )

    async def _no_op_execute_epic(**_kwargs):
        return None

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _no_op_execute_epic)

    await pipeline.run_epic(
        "resume_target_epic",
        build_id="build-resume-target",
        session_id="sess-resume-target",
    )
    await pipeline.async_cards.update_status("ISSUE-1", CardStatus.BLOCKED, reason="seed_blocked_issue")

    await pipeline.run_epic(
        "resume_target_epic",
        build_id="build-resume-target",
        session_id="sess-resume-target",
        target_issue_id="ISSUE-1",
    )

    latest_reservation = await pipeline.orchestrator.control_plane_repository.get_latest_reservation_record_for_holder_ref(
        holder_ref=scheduler_holder_ref_for_issue(session_id="sess-resume-target", issue_id="ISSUE-1")
    )
    assert latest_reservation is not None
    run_id = latest_reservation.reservation_id.split("-reservation:", 1)[-1]
    run = await pipeline.orchestrator.control_plane_execution_repository.get_run_record(run_id=run_id)
    reservation_history = await pipeline.orchestrator.control_plane_repository.list_reservation_records(
        reservation_id=latest_reservation.reservation_id
    )
    lease_history = await pipeline.orchestrator.control_plane_repository.list_lease_records(
        lease_id=orchestrator_lease_id_for_run(run_id=run_id)
    )
    issues = await pipeline.async_cards.get_by_build("build-resume-target")
    issue = next((entry for entry in issues if entry.id == "ISSUE-1"), None)

    assert run is not None
    assert run.final_truth_record_id is not None
    assert issue is not None
    assert issue.status is CardStatus.READY
    assert [record.status for record in reservation_history] == [
        ReservationStatus.ACTIVE,
        ReservationStatus.PROMOTED_TO_LEASE,
    ]
    assert [record.status for record in lease_history] == [
        LeaseStatus.ACTIVE,
        LeaseStatus.RELEASED,
    ]
