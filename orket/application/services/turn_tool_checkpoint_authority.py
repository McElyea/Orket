"""Read-only checkpoint admission shared by recovery and explicit approval recovery."""
from __future__ import annotations

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.core.contracts import AttemptRecord, CheckpointAcceptanceRecord, CheckpointRecord, RunRecord
from orket.core.domain import AttemptState, CheckpointAcceptanceOutcome, CheckpointResumabilityClass, RunState


class TurnToolCheckpointRecoveryError(ValueError):
    """Raised when governed turn checkpoint recovery would exceed authority."""


class TurnToolReconciliationClosed(TurnToolCheckpointRecoveryError):
    """Signal a fully staged reconciliation; its transaction commits before refusal."""



async def resolve_checkpoint_recovery_authority(
    *,
    publication: ControlPlanePublicationService,
    attempt_id: str,
) -> tuple[CheckpointRecord, CheckpointAcceptanceRecord | None]:
    checkpoints = await publication.repository.list_checkpoints(parent_ref=attempt_id)
    if not checkpoints:
        raise TurnToolCheckpointRecoveryError(
            f"resume_mode requires an accepted governed turn checkpoint for attempt {attempt_id}"
        )
    checkpoint = checkpoints[-1]
    acceptance = await publication.repository.get_checkpoint_acceptance(checkpoint_id=checkpoint.checkpoint_id)
    return checkpoint, acceptance



def validate_checkpoint_recovery_inputs(
    *,
    run: RunRecord,
    current_attempt: AttemptRecord,
    checkpoint: CheckpointRecord,
    acceptance: CheckpointAcceptanceRecord | None,
) -> tuple[CheckpointResumabilityClass, CheckpointAcceptanceRecord]:
    if run.lifecycle_state is not RunState.EXECUTING:
        raise TurnToolCheckpointRecoveryError(
            f"resume_mode requires an unfinished executing run; found {run.lifecycle_state.value}"
        )
    if current_attempt.attempt_state is not AttemptState.EXECUTING:
        raise TurnToolCheckpointRecoveryError(
            f"resume_mode requires an unfinished executing attempt; found {current_attempt.attempt_state.value}"
        )
    if acceptance is None or acceptance.outcome is not CheckpointAcceptanceOutcome.ACCEPTED:
        raise TurnToolCheckpointRecoveryError(
            f"resume_mode requires accepted checkpoint authority for {checkpoint.checkpoint_id}"
        )
    if checkpoint.resumability_class not in {
        CheckpointResumabilityClass.RESUME_SAME_ATTEMPT,
        CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT,
    }:
        raise TurnToolCheckpointRecoveryError(
            "resume_mode requires a resumable governed turn checkpoint"
        )
    if acceptance.resumability_class is not checkpoint.resumability_class:
        raise TurnToolCheckpointRecoveryError(
            "resume_mode requires checkpoint acceptance that matches checkpoint resumability"
        )
    return checkpoint.resumability_class, acceptance
