"""Legacy terminal adoption preserves history and requires retained evidence."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.outward_ledger_snapshot_store import OutwardLedgerSnapshotStore
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.application.services.control_plane_snapshot_publication import snapshot_digest
from orket.application.services.outward_control_plane_service import authority_adoption_event_id
from orket.application.services.outward_run_lifecycle import run_event, terminal_transition
from orket.core.domain import AttemptState, ResultClass, RunState
from tests.integration.test_governed_agent_terminal_history import logical_state
from tests.integration.test_outward_authority_migration import legacy_queued

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
OUTCOMES = ["policy_rejected", "handoff_rejected"]
HISTORICAL_AT = "2026-09-11T12:01:00+00:00"


async def retained_terminal(tmp_path, outcome, *, damage=None):
    db, queued, service = await legacy_queued(tmp_path)
    event_type = "proposal_policy_rejected" if outcome == "policy_rejected" else "trust_handoff_rejected"
    cause = run_event(queued, event_id=f"run:{queued.run_id}:retained-refusal", event_type=event_type,
        at=HISTORICAL_AT, payload={"run_id": queued.run_id, "reason": "retained refusal"})
    terminal, event = terminal_transition(queued, at=HISTORICAL_AT, status="completed",
                                        reason="retained refusal", outcome=outcome)
    if damage == "status-conflict":
        terminal = replace(terminal, status="failed")
    if damage == "completion-missing":
        terminal = replace(terminal, completed_at=None)
    if damage == "outcome-conflict":
        event = replace(event, payload={**event.payload, "outcome": "denied"})
    if damage == "unsupported-success":
        event = replace(event, payload={**event.payload, "outcome": "success"})
    events = OutwardRunEventStore(db)
    if damage != "cause-missing":
        await events.append(cause)
    await events.append(event)
    if damage == "two-terminal-events":
        await events.append(replace(event, event_id=f"{event.event_id}:duplicate"))
    await OutwardRunStore(db).update(terminal)
    service.inputs.now = datetime.fromisoformat("2026-09-11T12:02:00+00:00")
    # Establish normal schema before the logical no-mutation baseline.
    async with service.unit.transaction() as transaction:
        assert await transaction.control_plane.execution.get_run_record(run_id=terminal.run_id) is None
        assert await transaction.control_plane.records.get_final_truth(run_id=terminal.run_id) is None
    return db, terminal, cause, service


@pytest.mark.parametrize("outcome", OUTCOMES)
# Layer: integration
async def test_terminal_adoption_preserves_history_and_publishes_linked_blocked_truth(tmp_path, outcome):
    db, run, cause, service = await retained_terminal(tmp_path, outcome)
    before = await OutwardLedgerSnapshotStore(db).read(run.run_id)
    inspection = await service.inspect(run.run_id)
    arguments = dict(expected_run_digest=inspection["expected_run_digest"], actor_ref="reviewed-local-owner", owners_stopped=True)
    result = await service.migrate(run.run_id, **arguments)
    assert result["authority_state"] == "shared" and result["status"] == "completed"
    assert result["final_truth"]["result_class"] == "blocked"
    after = await OutwardLedgerSnapshotStore(db).read(run.run_id)
    assert after.run == before.run == run and after.events[:-2] == before.events
    after.compare_anchor(before.anchor.to_dict())
    adoption, publication = after.events[-2:]
    assert adoption.event_id == authority_adoption_event_id(run.run_id)
    assert adoption.payload["input_basis"] == "reviewed_current_state"
    assert publication.event_type == "outward_final_truth_adopted"
    assert publication.payload["historical_completed_at"] == HISTORICAL_AT
    execution = AsyncControlPlaneExecutionRepository(db)
    records = AsyncControlPlaneRecordRepository(db)
    shared = await execution.get_run_record(run_id=run.run_id)
    attempts = await execution.list_attempt_records(run_id=run.run_id)
    truth = await records.get_final_truth(run_id=run.run_id)
    assert len(attempts) == 1 and attempts[0].attempt_state is AttemptState.FAILED
    assert attempts[0].end_timestamp == HISTORICAL_AT
    assert shared.lifecycle_state is RunState.FAILED_TERMINAL
    assert shared.final_truth_record_id == truth.final_truth_record_id
    assert truth.result_class is ResultClass.BLOCKED
    steps = await execution.list_step_records(attempt_id=attempts[0].attempt_id)
    assert len(steps) == 1 and steps[0].receipt_refs == [cause.event_id]
    assert truth.authoritative_result_ref == steps[0].step_id
    assert steps[0].output_ref == publication.event_id
    assert publication.payload["final_truth_digest"] == snapshot_digest(truth.model_dump(mode="json"))
    assert await records.list_effect_journal_entries(run_id=run.run_id) == []
    committed = await logical_state(db)
    assert await service.migrate(run.run_id, **arguments) == result
    assert await logical_state(db) == committed


REFUSALS = {
    "cause-missing": "E_OUTWARD_MIGRATION_TERMINAL_EVIDENCE_MISSING",
    "outcome-conflict": "E_OUTWARD_MIGRATION_TERMINAL_CONFLICT",
    "status-conflict": "E_OUTWARD_MIGRATION_TERMINAL_CONFLICT",
    "completion-missing": "E_OUTWARD_MIGRATION_TERMINAL_CONFLICT",
    "two-terminal-events": "E_OUTWARD_MIGRATION_TERMINAL_CONFLICT",
    "unsupported-success": "E_OUTWARD_TERMINAL_SEQUENCE_INCOMPLETE",
}


@pytest.mark.parametrize("damage", REFUSALS)
# Layer: integration
async def test_terminal_adoption_refuses_unsupported_history_without_new_authority(tmp_path, damage):
    db, run, _, service = await retained_terminal(tmp_path, "policy_rejected", damage=damage)
    inspection = await service.inspect(run.run_id)
    before = await logical_state(db)
    with pytest.raises(RuntimeError, match=REFUSALS[damage]):
        await service.migrate(run.run_id, expected_run_digest=inspection["expected_run_digest"],
                              actor_ref="reviewed-local-owner", owners_stopped=True)
    assert await logical_state(db) == before
    assert await AsyncControlPlaneExecutionRepository(db).get_run_record(run_id=run.run_id) is None
    assert await AsyncControlPlaneExecutionRepository(db).list_attempt_records(run_id=run.run_id) == []
    records = AsyncControlPlaneRecordRepository(db)
    assert await records.get_final_truth(run_id=run.run_id) is None
    assert await records.list_effect_journal_entries(run_id=run.run_id) == []
    assert await OutwardRunEventStore(db).get(authority_adoption_event_id(run.run_id)) is None
