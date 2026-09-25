"""Check the original child authority before granting an interrupted continuation."""
from __future__ import annotations

from orket.application.services.turn_tool_checkpoint_authority import (
    resolve_checkpoint_recovery_authority,
    validate_checkpoint_recovery_inputs,
)
from orket.application.services.turn_tool_control_plane_recovery import load_checkpoint_resume_lineage
from orket.application.workflows.turn_checkpoint_snapshot import (
    validate_checkpoint_snapshot_integrity,
    validate_resume_snapshot_semantics,
)
from orket.application.workflows.turn_executor_control_plane_evidence import (
    load_checkpoint_snapshot_at,
    operation_artifact_ids_at,
    planned_tool_call_objects,
    validate_snapshot_identity,
)
from orket.core.domain import AttemptState, RunState

from .turn_artifact_destination import TurnArtifactDestination


def capture_approval_destinations(pause, *, writer, workspace):
    return {key: TurnArtifactDestination(writer=writer, workspace=workspace,
        session_id=pause.session_id, issue_id=identity["issue_id"], role_name=identity["seat_name"], role_id=None,
        turn_index=identity["payload_json"]["turn_index"]) for key, identity in pause.approvals.items()}


def validate_approval_destinations(pause, destinations):
    if set(pause.approvals) != set(destinations):
        raise ValueError("E_EPIC_APPROVAL_IDENTITY_CONFLICT")
    for key, identity in pause.approvals.items():
        destination = destinations[key]
        if (pause.session_id != destination.session_id or identity["session_id"] != destination.session_id
                or identity["issue_id"] != destination.issue_id or identity["seat_name"] != destination.role_name
                or identity["payload_json"]["turn_index"] != destination.turn_index
                or identity["payload_json"]["control_plane_target_ref"] != destination.control_plane_run_id):
            raise ValueError("E_EPIC_APPROVAL_IDENTITY_CONFLICT")


async def validate_approval_checkpoints(pause, *, execution_repository, publication, destinations):
    validate_approval_destinations(pause, destinations)
    if "denied" in pause.decisions.values():
        return  # This continuation only stops execution; it cannot dispatch an approved tool.
    seen = set()
    for approval_id, identity in pause.approvals.items():
        destination = destinations[approval_id]
        target = identity["payload_json"]["control_plane_target_ref"]
        if target in seen:
            continue
        seen.add(target)
        run = await execution_repository.get_run_record(run_id=target)
        if run is None or run.namespace_scope != "issue:" + identity["issue_id"]:
            raise ValueError("E_EPIC_APPROVAL_CHILD_CONFLICT")
        truth = await publication.repository.get_final_truth(run_id=target)
        # This recovery grant is limited to an entirely pre-effect continuation.
        # Completed children require a separate reconciliation decision.
        if truth is not None and run.final_truth_record_id == truth.final_truth_record_id:
            raise ValueError("E_EPIC_APPROVAL_RECOVERY_POST_EFFECT")
        attempt = await execution_repository.get_attempt_record(attempt_id=run.current_attempt_id)
        if (run.lifecycle_state != RunState.EXECUTING or run.final_truth_record_id is not None or attempt is None
                or attempt.attempt_state != AttemptState.EXECUTING):
            raise ValueError("E_EPIC_APPROVAL_CHILD_CONFLICT")
        if (await execution_repository.list_step_records(attempt_id=attempt.attempt_id)
                or any(entry.attempt_id == attempt.attempt_id for entry in
                       await publication.repository.list_effect_journal_entries(run_id=target))):
            raise ValueError("E_EPIC_APPROVAL_RECOVERY_POST_EFFECT")
        if attempt.attempt_ordinal > 1:
            _, checkpoint, acceptance = await load_checkpoint_resume_lineage(
                execution_repository=execution_repository, publication=publication,
                run_id=target, resumed_attempt=attempt)
        else:
            checkpoint, acceptance = await resolve_checkpoint_recovery_authority(
                publication=publication, attempt_id=attempt.attempt_id)
        resumability, _ = validate_checkpoint_recovery_inputs(
            run=run, current_attempt=attempt, checkpoint=checkpoint, acceptance=acceptance)
        snapshot = await load_checkpoint_snapshot_at(destination, checkpoint.state_snapshot_ref)
        validate_checkpoint_snapshot_integrity(
            snapshot_payload=snapshot,
            integrity_verification_ref=checkpoint.integrity_verification_ref,
        )
        validate_resume_snapshot_semantics(snapshot_payload=snapshot, attempt_id=attempt.attempt_id,
                                          resumability_class=resumability)
        validate_snapshot_identity(snapshot_payload=snapshot, destination=destination,
                                   namespace_scope="issue:" + destination.issue_id, error_prefix="approval recovery")
        planned_tool_call_objects(snapshot, error_prefix="approval recovery")
        if await operation_artifact_ids_at(destination):
            raise ValueError("E_EPIC_APPROVAL_RECOVERY_ORPHAN_OPERATIONS")
