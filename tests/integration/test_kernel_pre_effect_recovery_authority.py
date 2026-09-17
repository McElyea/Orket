"""SQLite kernel abandonment and read-only recovery projection contracts."""
import json

import aiosqlite
import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.kernel_action_control_plane_failure import (
    failure_projection_for_commit_status,
    pre_effect_recovery_decision_id,
)
from orket.application.services.kernel_action_control_plane_service import KernelActionControlPlaneService
from orket.application.services.kernel_action_control_plane_view_service import KernelActionControlPlaneViewService
from orket.core.domain import AttemptState, RunState

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def close_pre_effect(path, status):
    execution = AsyncControlPlaneExecutionRepository(path)
    records = AsyncControlPlaneRecordRepository(path)
    service = KernelActionControlPlaneService(
        execution_repository=execution, publication=ControlPlanePublicationService(repository=records)
    )
    request = dict(contract_version="kernel_api/v1", session_id="session", trace_id="trace",
                   proposal_digest="a1" * 32, admission_decision_digest="b1" * 32)
    response = dict(status=status, commit_event_digest="c1" * 32)
    ledger = [dict(event_type="admission.decided", created_at="2026-09-14T00:00:00+00:00", event_digest="d1" * 32),
              dict(event_type="commit.recorded", created_at="2026-09-14T00:00:01+00:00", event_digest="c1" * 32)]
    result = await service.record_commit(request=request, response=response, ledger_items=ledger)
    return result, execution, records


async def dump(path):
    async with aiosqlite.connect(path) as connection:
        return [line async for line in connection.iterdump()]


@pytest.mark.parametrize("status", ["REJECTED_POLICY", "ERROR"])
# Layer: integration
async def test_sqlite_kernel_abandonment_retains_decision_and_projects_without_mutation(tmp_path, status):
    path = tmp_path / "control.sqlite3"
    (run, attempt, truth, effect), _, _ = await close_pre_effect(path, status)
    # Reopen both ports; no in-memory authority carries over to the reader.
    execution = AsyncControlPlaneExecutionRepository(path)
    records = AsyncControlPlaneRecordRepository(path)
    assert await execution.get_run_record(run_id=run.run_id) == run
    assert await execution.get_attempt_record(attempt_id=attempt.attempt_id) == attempt
    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert run.final_truth_record_id == truth.final_truth_record_id
    assert attempt.attempt_state is AttemptState.ABANDONED and attempt.end_timestamp
    assert attempt.recovery_decision_id is attempt.side_effect_boundary_class is None
    assert attempt.failure_class is attempt.failure_plane is attempt.failure_classification is None
    assert effect is None and await records.list_effect_journal_entries(run_id=run.run_id) == []
    assert await execution.list_step_records(attempt_id=attempt.attempt_id) == []
    view = KernelActionControlPlaneViewService(record_repository=records, execution_repository=execution)
    before = await dump(path)
    summary = await view.build_summary(session_id="session", trace_id="trace")
    assert await view.build_summary(session_id="session", trace_id="trace") == summary
    assert await dump(path) == before
    decision = await records.get_recovery_decision(decision_id=summary["current_recovery_decision_id"])
    assert decision.run_id == run.run_id and decision.failed_attempt_id == attempt.attempt_id
    basis, plane, classification = failure_projection_for_commit_status(status=status)
    assert summary["current_attempt_failure_class"] is None
    assert summary["current_recovery_failure_class"] == basis
    assert summary["current_recovery_failure_plane"] == plane.value
    assert summary["current_recovery_failure_classification"] == classification.value
    assert summary["current_recovery_side_effect_boundary_class"] == "pre_effect_failure"
    assert summary["current_recovery_action"] == "terminate_run"
    assert summary["latest_reservation"]["status"] == "reservation_released"
    assert summary["latest_lease"] is summary["latest_resource"] is None


@pytest.mark.parametrize("damage", ["decision_id", "run_id", "failed_attempt_id", "recovery_policy_ref", "competing"])
# Layer: integration
async def test_kernel_recovery_view_refuses_conflicting_authority_without_repair(tmp_path, damage):
    path = tmp_path / "control.sqlite3"
    (run, _, _, _), execution, records = await close_pre_effect(path, "ERROR")
    decision_id = pre_effect_recovery_decision_id(run_id=run.run_id, status="ERROR")
    decision = await records.get_recovery_decision(decision_id=decision_id)
    if damage == "competing":
        basis, plane, classification = failure_projection_for_commit_status(status="REJECTED_POLICY")
        await records.save_recovery_decision(decision=decision.model_copy(update={
            "decision_id": pre_effect_recovery_decision_id(run_id=run.run_id, status="REJECTED_POLICY"),
            "failure_classification_basis": basis, "failure_plane": plane, "failure_classification": classification,
        }))
    else:
        damaged = decision.model_dump(mode="json")
        damaged[damage] = "conflicting-authority"
        async with aiosqlite.connect(path) as connection:
            await connection.execute("UPDATE recovery_decision_records SET payload_json=? WHERE decision_id=?",
                                     (json.dumps(damaged), decision_id))
            await connection.commit()
    before = await dump(path)
    view = KernelActionControlPlaneViewService(record_repository=records, execution_repository=execution)
    with pytest.raises(ValueError, match="E_KERNEL_RECOVERY_AUTHORITY_CONFLICT"):
        await view.build_summary(session_id="session", trace_id="trace")
    assert await dump(path) == before
