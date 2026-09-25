from __future__ import annotations

from orket.application.services.turn_tool_control_plane_service import (
    TurnToolControlPlaneError,
    TurnToolControlPlaneService,
)
from orket.application.services.turn_tool_control_plane_support import attempt_id_for
from orket.core.contracts import (
    AttemptRecord,
    CheckpointAcceptanceRecord,
    CheckpointRecord,
    FinalTruthRecord,
    RunRecord,
)
from orket.core.domain import (
    AttemptState,
    CheckpointAcceptanceOutcome,
    CheckpointResumabilityClass,
    ResultClass,
    RunState,
)
from orket.core.domain.execution import ExecutionTurn

from .turn_artifact_destination import TurnArtifactDestination
from .turn_checkpoint_snapshot import validate_checkpoint_snapshot_integrity
from .turn_control_plane_binding import TurnControlPlaneBinding
from .turn_executor_control_plane_evidence import (
    load_checkpoint_snapshot_payload,
    load_completed_replay_tool_calls,
)


async def load_completed_turn_replay_if_needed(
    *,
    control_plane: TurnControlPlaneBinding,
    destination: TurnArtifactDestination,
) -> ExecutionTurn | None:
    control_plane_service = control_plane.service
    if control_plane_service is None or control_plane.protocol_replay_mode:
        return None
    run_id = destination.control_plane_run_id
    issue_id, role_name = destination.issue_id, destination.role_name
    namespace_scope = control_plane.namespace_scope
    run = await control_plane_service.execution_repository.get_run_record(run_id=run_id)
    if run is None:
        return None
    truth = await _load_successful_completed_truth(control_plane_service=control_plane_service, run=run)
    if truth is None:
        return None
    attempt = await _load_completed_attempt(control_plane_service=control_plane_service, run_id=run_id, run=run)
    checkpoint, checkpoint_acceptance = await _load_completed_checkpoint_authority(
        control_plane_service=control_plane_service,
        attempt_id=attempt.attempt_id,
    )
    snapshot_payload = await load_checkpoint_snapshot_payload(
        destination=destination, state_snapshot_ref=checkpoint.state_snapshot_ref,
    )
    validate_checkpoint_snapshot_integrity(
        snapshot_payload=snapshot_payload,
        integrity_verification_ref=checkpoint.integrity_verification_ref,
    )
    tool_calls = await load_completed_replay_tool_calls(
        control_plane_service=control_plane_service,
        run_id=run.run_id,
        attempt_id=attempt.attempt_id,
        destination=destination, namespace_scope=namespace_scope,
        snapshot_payload=snapshot_payload,
    )
    return ExecutionTurn(
        timestamp=None,  # The retained checkpoint has no original response timestamp.
        role=role_name,
        issue_id=issue_id,
        content="",
        tool_calls=tool_calls,
        tokens_used=0,
        raw={
            "prompt_hash": snapshot_payload.get("prompt_hash"),
            "model": snapshot_payload.get("model"),
            "prompt_metadata": snapshot_payload.get("prompt_metadata", {}),
            "state_delta": snapshot_payload.get("state_delta", {}),
            "control_plane_replay": {
                "artifact_reused": True,
                "run_id": run.run_id,
                "attempt_id": attempt.attempt_id,
                "checkpoint_id": checkpoint.checkpoint_id,
                "checkpoint_acceptance_id": checkpoint_acceptance.acceptance_id,
                "state_snapshot_ref": checkpoint.state_snapshot_ref,
                "final_truth_record_id": truth.final_truth_record_id,
                "authoritative_result_ref": truth.authoritative_result_ref,
                "closure_basis": truth.closure_basis.value,
            },
        },
        note="control_plane_completed_replay",
    )


async def _load_successful_completed_truth(
    *,
    control_plane_service: TurnToolControlPlaneService,
    run: RunRecord,
) -> FinalTruthRecord | None:
    if run.final_truth_record_id is None:
        if run.lifecycle_state is RunState.COMPLETED:
            raise TurnToolControlPlaneError(
                f"completed governed turn {run.run_id} is missing durable final truth for artifact replay"
            )
        return None
    truth = await control_plane_service.publication.repository.get_final_truth(run_id=run.run_id)
    if truth is None:
        raise TurnToolControlPlaneError(
            f"governed turn run {run.run_id} carries final_truth_record_id without durable final truth"
        )
    if truth.result_class is ResultClass.SUCCESS and run.lifecycle_state is RunState.COMPLETED:
        return truth
    raise TurnToolControlPlaneError(
        f"governed turn run {run.run_id} already closed with "
        f"{truth.result_class.value} via {truth.closure_basis.value}; execution cannot continue"
    )


async def _load_completed_attempt(
    *,
    control_plane_service: TurnToolControlPlaneService,
    run_id: str,
    run: RunRecord,
) -> AttemptRecord:
    attempt = await control_plane_service.execution_repository.get_attempt_record(
        attempt_id=run.current_attempt_id or attempt_id_for(run_id=run_id)
    )
    if attempt is None:
        raise TurnToolControlPlaneError(f"completed governed turn is missing current attempt: {run.run_id}")
    if attempt.attempt_state is not AttemptState.COMPLETED:
        raise TurnToolControlPlaneError(
            f"completed governed turn {run.run_id} has non-completed attempt {attempt.attempt_id}"
        )
    return attempt


async def _load_completed_checkpoint_authority(
    *,
    control_plane_service: TurnToolControlPlaneService,
    attempt_id: str,
) -> tuple[CheckpointRecord, CheckpointAcceptanceRecord]:
    checkpoints = await control_plane_service.publication.repository.list_checkpoints(parent_ref=attempt_id)
    if not checkpoints:
        raise TurnToolControlPlaneError(
            f"completed governed turn {attempt_id} is missing accepted checkpoint authority for artifact replay"
        )
    checkpoint = checkpoints[-1]
    acceptance = await control_plane_service.publication.repository.get_checkpoint_acceptance(
        checkpoint_id=checkpoint.checkpoint_id
    )
    if acceptance is None or acceptance.outcome is not CheckpointAcceptanceOutcome.ACCEPTED:
        raise TurnToolControlPlaneError(
            f"completed governed turn {attempt_id} is missing accepted checkpoint authority for artifact replay"
        )
    if checkpoint.resumability_class not in {
        CheckpointResumabilityClass.RESUME_SAME_ATTEMPT,
        CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT,
    }:
        raise TurnToolControlPlaneError(
            f"completed governed turn {attempt_id} requires resumable checkpoint authority for replay"
        )
    if acceptance.resumability_class is not checkpoint.resumability_class:
        raise TurnToolControlPlaneError(
            f"completed governed turn {attempt_id} requires accepted checkpoint authority that matches checkpoint resumability"
        )
    return checkpoint, acceptance


__all__ = [
    "load_checkpoint_snapshot_payload",
    "load_completed_turn_replay_if_needed",
]
