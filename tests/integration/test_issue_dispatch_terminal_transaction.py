"""Issue-dispatch closeout commits terminal and resource truth together."""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import timedelta

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.control_plane_transaction import SQLiteControlPlaneTransactions
from orket.application.services import orchestrator_issue_control_plane_service as issue_owner
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.orchestrator_issue_control_plane_support import lease_id_for_run, run_id_for_dispatch
from orket.core.domain import LeaseStatus, RunState
from orket.core.domain.control_plane_leases import ControlPlaneLeaseError
from tests.helpers.protocol_ledger_clock import ProtocolLedgerClock

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def service_for(path, now_utc=None):
    return issue_owner.OrchestratorIssueControlPlaneService(
        execution_repository=AsyncControlPlaneExecutionRepository(path),
        publication=ControlPlanePublicationService(repository=AsyncControlPlaneRecordRepository(path)),
        transactions=SQLiteControlPlaneTransactions(path),
        now_utc=now_utc if now_utc is not None else ProtocolLedgerClock().utc_now_iso,
    )


async def dispatch_state(service, run_id):
    run = await service.execution_repository.get_run_record(run_id=run_id)
    attempt = await service.execution_repository.get_attempt_record(attempt_id=run.current_attempt_id)
    steps = await service.execution_repository.list_step_records(attempt_id=attempt.attempt_id)
    records = service.publication.repository
    truth = await records.get_final_truth(run_id=run_id)
    lease = await records.get_latest_lease_record(lease_id=lease_id_for_run(run_id=run_id))
    resource = await records.get_latest_resource_record(resource_id=lease.resource_id)
    effects = await records.list_effect_journal_entries(run_id=run_id)
    return [
        item.model_dump(mode="json") if item is not None else None
        for item in [run, attempt, truth, lease, resource, *steps, *effects]
    ]


@pytest.mark.parametrize("failure", ["lease-write", "resource-write", "cancelled-write", "reversed-time"])
# Layer: integration
async def test_issue_closeout_refusal_rolls_back_terminal_and_resource_records(tmp_path, monkeypatch, failure):
    clock = ProtocolLedgerClock()
    service = service_for(tmp_path / "control-plane.sqlite3", clock.utc_now_iso)
    await service.publish_issue_transition(
        session_id="session",
        issue_id="issue",
        current_status="ready",
        target_status="in_progress",
        reason="turn_dispatch",
        assignee="coder",
        turn_index=1,
    )
    run_id = run_id_for_dispatch(session_id="session", issue_id="issue", seat_name="coder", turn_index=1)
    before = await dispatch_state(service, run_id)
    expected_error = ControlPlaneLeaseError if failure == "reversed-time" else RuntimeError
    if failure == "cancelled-write":
        expected_error = asyncio.CancelledError
    with monkeypatch.context() as fault:
        if failure == "reversed-time":
            fault.setattr(service, "now_utc", lambda: (clock.current - timedelta(days=1)).isoformat())
        else:
            method = "append_lease_record" if failure == "lease-write" else "save_resource_record"
            original = getattr(AsyncControlPlaneRecordRepository, method)

            async def write_then_interrupt(repository, **kwargs):
                await original(repository, **kwargs)
                raise expected_error("injected closeout interruption")

            fault.setattr(AsyncControlPlaneRecordRepository, method, write_then_interrupt)
        with pytest.raises(expected_error):
            await service.close_from_observed_status(session_id="session", issue_id="issue", observed_status="done")
    assert await dispatch_state(service_for(tmp_path / "control-plane.sqlite3"), run_id) == before
    await service.close_from_observed_status(session_id="session", issue_id="issue", observed_status="done")
    after = await dispatch_state(service, run_id)
    assert after[0]["lifecycle_state"] == RunState.COMPLETED.value
    assert after[2]["result_class"] == "success" and after[3]["status"] == LeaseStatus.RELEASED.value
    await service.close_from_observed_status(session_id="session", issue_id="issue", observed_status="done")
    assert await dispatch_state(service, run_id) == after


# Layer: integration
async def test_competing_issue_closeouts_publish_one_terminal_record_set(tmp_path):
    clock = ProtocolLedgerClock()
    first, second = [service_for(tmp_path / "control-plane.sqlite3", clock.utc_now_iso) for _ in range(2)]
    await first.publish_issue_transition(
        session_id="session",
        issue_id="issue",
        current_status="ready",
        target_status="in_progress",
        reason="turn_dispatch",
        assignee="coder",
        turn_index=1,
    )
    await asyncio.gather(
        *[
            owner.close_from_observed_status(session_id="session", issue_id="issue", observed_status="done")
            for owner in (first, second)
        ]
    )
    run_id = run_id_for_dispatch(session_id="session", issue_id="issue", seat_name="coder", turn_index=1)
    state = await dispatch_state(first, run_id)
    assert state[0]["lifecycle_state"] == "completed" and state[2]["result_class"] == "success"
    assert state[3]["status"] == "lease_released"
    steps = await first.execution_repository.list_step_records(attempt_id=state[1]["attempt_id"])
    assert [step.step_id for step in steps].count(run_id + ":step:closeout") == 1
    assert len(await first.publication.repository.list_lease_records(lease_id=lease_id_for_run(run_id=run_id))) == 2


@pytest.mark.parametrize("missing", ["released-lease", "final-truth"])
# Layer: integration
async def test_closed_issue_dispatch_refuses_inconsistent_retained_authority(tmp_path, missing):
    clock = ProtocolLedgerClock()
    path = tmp_path / "control-plane.sqlite3"
    service = service_for(path, clock.utc_now_iso)
    await service.publish_issue_transition(
        session_id="session",
        issue_id="issue",
        current_status="ready",
        target_status="in_progress",
        reason="turn_dispatch",
        assignee="coder",
        turn_index=1,
    )
    await service.close_from_observed_status(session_id="session", issue_id="issue", observed_status="done")

    def remove_retained_authority():
        with sqlite3.connect(path) as connection:
            if missing == "released-lease":
                connection.execute("DELETE FROM lease_records WHERE status = 'lease_released'")
            else:
                connection.execute("DELETE FROM final_truth_records")

    await asyncio.to_thread(remove_retained_authority)
    run_id = run_id_for_dispatch(session_id="session", issue_id="issue", seat_name="coder", turn_index=1)
    before = await dispatch_state(service, run_id)
    with pytest.raises(ValueError, match="lease|TERMINAL_AUTHORITY_CONFLICT"):
        await service_for(path).close_from_observed_status(
            session_id="session", issue_id="issue", observed_status="done"
        )
    assert await dispatch_state(service, run_id) == before
