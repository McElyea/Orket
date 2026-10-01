"""Retained checkpoint authority must bind the requested continuation."""
from __future__ import annotations

import aiosqlite
import pytest

from orket.application.services.turn_tool_checkpoint_authority import TurnToolCheckpointRecoveryError
from orket.application.services.turn_tool_control_plane_recovery import load_checkpoint_resume_lineage
from orket.application.services.turn_tool_control_plane_service import build_turn_tool_control_plane_service
from orket.core.contracts import CheckpointRecord
from orket.core.domain import (
    AttemptState,
    CheckpointReobservationClass,
    CheckpointResumabilityClass,
    RecoveryActionClass,
    RunState,
)
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock
from tests.integration.test_governed_agent_terminal_history import logical_state
from tests.integration.test_turn_recovery_transaction import INPUTS

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("deterministic_turn_clock")]
MODES = [CheckpointResumabilityClass.RESUME_SAME_ATTEMPT,
         CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT]


async def admitted_lineage(tmp_path, mode):
    """Use public admission/publication; this fixture does not claim snapshot replay."""
    db = tmp_path / "lineage.sqlite3"
    control = build_turn_tool_control_plane_service(db)
    run, original = await control.begin_execution(**INPUTS)
    checkpoint = CheckpointRecord(
        checkpoint_id=f"checkpoint:{original.attempt_id}", parent_ref=original.attempt_id,
        creation_timestamp=original.start_timestamp, state_snapshot_ref="retained-state:pre-effect",
        resumability_class=mode, policy_digest=run.policy_digest,
        integrity_verification_ref="fixture:metadata-authority-only",
    )
    acceptance = await control.publication.accept_checkpoint(
        acceptance_id=f"acceptance:{original.attempt_id}", checkpoint=checkpoint,
        supervisor_authority_ref=f"turn-tool-supervisor:{run.run_id}",
        decision_timestamp=original.start_timestamp,
        required_reobservation_class=CheckpointReobservationClass.FULL,
        integrity_verification_ref=checkpoint.integrity_verification_ref,
    )
    resumed_run, resumed = await control.begin_execution(**INPUTS, resume_mode=True)
    decision, actual_checkpoint, actual_acceptance = await load_checkpoint_resume_lineage(
        execution_repository=control.execution_repository, publication=control.publication,
        run_id=run.run_id, resumed_attempt=resumed,
    )
    assert (actual_checkpoint, actual_acceptance) == (checkpoint, acceptance)
    return db, control, resumed_run, original, resumed, decision, checkpoint, acceptance


async def overwrite_record(db, table, key, identifier, record):
    """Model-valid retained damage, deliberately outside append-only publication."""
    # Identifiers are a closed test-owned mapping, never inputs to the product.
    allowed = {("recovery_decision_records", "decision_id"),
               ("checkpoint_records", "checkpoint_id"),
               ("checkpoint_acceptance_records", "acceptance_id"),
               ("control_plane_attempts", "attempt_id")}
    assert (table, key) in allowed
    async with aiosqlite.connect(db) as connection:
        if record is None:
            await connection.execute(f"DELETE FROM {table} WHERE {key} = ?", (identifier,))
        else:
            # Keep indexed identity columns consistent with the damaged model payload.
            indexed = {"recovery_decision_records": ("run_id",), "checkpoint_records": ("parent_ref",),
                       "control_plane_attempts": ("run_id", "attempt_ordinal")}.get(table, ())
            assignments = ", ".join(["payload_json = ?", *(f"{column} = ?" for column in indexed)])
            values = (record.model_dump_json(), *(getattr(record, column) for column in indexed), identifier)
            await connection.execute(f"UPDATE {table} SET {assignments} WHERE {key} = ?", values)
        await connection.commit()


async def change_lineage(db, control, original, resumed, decision, checkpoint, acceptance, damage):
    if damage == "prior-link-missing":
        prior = await control.execution_repository.get_attempt_record(attempt_id=original.attempt_id)
        prior = type(prior).model_validate({**prior.model_dump(), "recovery_decision_id": None})
        await control.execution_repository.save_attempt_record(record=prior)
        return resumed
    if damage == "snapshot-mismatch":
        changed = type(resumed).model_validate({**resumed.model_dump(), "starting_state_snapshot_ref": "other-state"})
        await overwrite_record(db, "control_plane_attempts", "attempt_id", resumed.attempt_id, changed)
        retained = await control.execution_repository.get_attempt_record(attempt_id=resumed.attempt_id)
        assert retained == changed
        return retained
    targets = {
        "decision-missing": (decision, "recovery_decision_records", "decision_id", None),
        "decision-action": (decision, "recovery_decision_records", "decision_id",
                            {"authorized_next_action": RecoveryActionClass.TERMINATE_RUN}),
        "decision-attempt": (decision, "recovery_decision_records", "decision_id",
                             {"new_attempt_id" if decision.new_attempt_id else "resumed_attempt_id": "other-attempt"}),
        "decision-checkpoint": (decision, "recovery_decision_records", "decision_id", {"target_checkpoint_id": "absent"}),
        "acceptance-missing": (acceptance, "checkpoint_acceptance_records", "acceptance_id", None),
        "acceptance-class": (acceptance, "checkpoint_acceptance_records", "acceptance_id",
                             {"resumability_class": CheckpointResumabilityClass.RESUME_FORBIDDEN}),
        "checkpoint-class": (checkpoint, "checkpoint_records", "checkpoint_id",
                             {"resumability_class": CheckpointResumabilityClass.RESUME_FORBIDDEN}),
    }
    record, table, key, change = targets[damage]
    changed = None if change is None else type(record).model_validate({**record.model_dump(), **change})
    await overwrite_record(db, table, key, getattr(record, key), changed)
    return resumed


@pytest.mark.parametrize("mode", MODES, ids=["same-attempt", "replacement-attempt"])
# Layer: integration
async def test_admitted_checkpoint_lineage_survives_reopen_without_new_authority(tmp_path, mode):
    db, control, run, original, resumed, decision, checkpoint, acceptance = await admitted_lineage(tmp_path, mode)
    attempts = await control.execution_repository.list_attempt_records(run_id=run.run_id)
    same = mode is CheckpointResumabilityClass.RESUME_SAME_ATTEMPT
    assert len(attempts) == (1 if same else 2)
    assert run.lifecycle_state is RunState.EXECUTING and run.current_attempt_id == resumed.attempt_id
    assert resumed.attempt_state is AttemptState.EXECUTING
    assert decision.failed_attempt_id == original.attempt_id and decision.run_id == run.run_id
    assert decision.target_checkpoint_id == checkpoint.checkpoint_id
    assert decision.required_precondition_refs == [checkpoint.checkpoint_id, acceptance.acceptance_id, checkpoint.state_snapshot_ref]
    if same:
        assert resumed == original and decision.resumed_attempt_id == original.attempt_id
        assert decision.new_attempt_id is None
    else:
        assert attempts[0].attempt_state is AttemptState.INTERRUPTED
        assert attempts[0].recovery_decision_id == decision.decision_id
        assert resumed.attempt_ordinal == 2 and decision.new_attempt_id == resumed.attempt_id
        assert decision.resumed_attempt_id is None
    before = await logical_state(db)
    reopened = build_turn_tool_control_plane_service(db)
    actual = await load_checkpoint_resume_lineage(execution_repository=reopened.execution_repository,
        publication=reopened.publication, run_id=run.run_id, resumed_attempt=resumed)
    assert actual == (decision, checkpoint, acceptance)
    assert await logical_state(db) == before
    assert await reopened.publication.repository.get_final_truth(run_id=run.run_id) is None
    assert await reopened.publication.repository.list_effect_journal_entries(run_id=run.run_id) == []
    assert await reopened.execution_repository.list_step_records(attempt_id=resumed.attempt_id) == []


COMMON_DAMAGE = ["decision-missing", "decision-action", "decision-attempt", "decision-checkpoint",
                 "acceptance-missing", "acceptance-class", "checkpoint-class"]
CASES = [(mode, damage) for mode in MODES for damage in COMMON_DAMAGE]
CASES += [(MODES[1], damage) for damage in ["prior-link-missing", "snapshot-mismatch"]]


@pytest.mark.parametrize("mode,damage", CASES)
# Layer: integration
async def test_incomplete_or_contradictory_lineage_refuses_without_repair(tmp_path, mode, damage):
    db, control, run, original, resumed, decision, checkpoint, acceptance = await admitted_lineage(tmp_path, mode)
    resumed = await change_lineage(db, control, original, resumed, decision, checkpoint, acceptance, damage)
    before = await logical_state(db)
    reopened = build_turn_tool_control_plane_service(db)
    with pytest.raises(TurnToolCheckpointRecoveryError, match="lineage"):
        await load_checkpoint_resume_lineage(execution_repository=reopened.execution_repository,
            publication=reopened.publication, run_id=run.run_id, resumed_attempt=resumed)
    assert await logical_state(db) == before
    assert await reopened.publication.repository.get_final_truth(run_id=run.run_id) is None
    assert await reopened.publication.repository.list_effect_journal_entries(run_id=run.run_id) == []
    assert await reopened.execution_repository.list_step_records(attempt_id=resumed.attempt_id) == []
