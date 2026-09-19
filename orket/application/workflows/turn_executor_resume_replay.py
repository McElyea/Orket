from __future__ import annotations

from typing import Any

from orket.application.services.turn_tool_control_plane_recovery import load_checkpoint_resume_lineage
from orket.application.services.turn_tool_control_plane_support import attempt_id_for, run_id_for
from orket.application.services.turn_tool_recovery_transaction import (
    reconcile_orphan_operation_artifacts_atomic,
    recover_pre_effect_attempt_atomic,
)
from orket.core.domain import AttemptState, RunState
from orket.core.domain.execution import ExecutionTurn

from .turn_checkpoint_snapshot import validate_resume_snapshot_semantics
from .turn_executor_completed_replay import control_plane_service_for_executor
from .turn_executor_control_plane_evidence import (
    list_operation_artifact_refs,
    load_checkpoint_snapshot_payload,
    planned_tool_call_objects,
    validate_snapshot_identity,
)


async def load_pre_effect_resume_turn_if_needed(
    *,
    executor: Any,
    issue_id: str,
    role_name: str,
    context: dict[str, Any],
) -> ExecutionTurn | None:
    if not bool(context.get("resume_mode")) or bool(context.get("protocol_replay_mode")):
        return None
    control_plane_service = control_plane_service_for_executor(executor)
    if control_plane_service is None:
        return None
    run_id = run_id_for(
        session_id=str(context.get("session_id", "unknown-session")),
        issue_id=issue_id,
        role_name=role_name,
        turn_index=int(context.get("turn_index", 0)),
    )
    run = await control_plane_service.execution_repository.get_run_record(run_id=run_id)
    if run is None or run.final_truth_record_id is not None:
        return None
    attempt = await control_plane_service.execution_repository.get_attempt_record(
        attempt_id=run.current_attempt_id or attempt_id_for(run_id=run_id)
    )
    if attempt is None or run.lifecycle_state is not RunState.EXECUTING or attempt.attempt_state is not AttemptState.EXECUTING:
        return None
    run, attempt = await recover_pre_effect_attempt_atomic(
        transactions=control_plane_service.transactions,
        publication=control_plane_service.publication,
        run=run,
        current_attempt=attempt,
    )
    recovery_decision, checkpoint, checkpoint_acceptance = await load_checkpoint_resume_lineage(
        execution_repository=control_plane_service.execution_repository,
        publication=control_plane_service.publication,
        run_id=run.run_id,
        resumed_attempt=attempt,
    )
    snapshot_payload = await load_checkpoint_snapshot_payload(
        executor=executor,
        issue_id=issue_id,
        role_name=role_name,
        context=context,
        state_snapshot_ref=checkpoint.state_snapshot_ref,
    )
    validate_resume_snapshot_semantics(
        snapshot_payload=snapshot_payload,
        attempt_id=attempt.attempt_id,
        resumability_class=checkpoint_acceptance.resumability_class,
    )
    validate_snapshot_identity(
        snapshot_payload=snapshot_payload,
        issue_id=issue_id,
        role_name=role_name,
        context=context,
        error_prefix=f"resumed governed attempt {attempt.attempt_id}",
    )
    operation_refs = await list_operation_artifact_refs(
        executor=executor,
        issue_id=issue_id,
        role_name=role_name,
        context=context,
    )
    if operation_refs:
        await reconcile_orphan_operation_artifacts_atomic(
            transactions=control_plane_service.transactions,
            publication=control_plane_service.publication,
            run=run,
            current_attempt=attempt,
            checkpoint=checkpoint,
            acceptance=checkpoint_acceptance,
            operation_refs=operation_refs,
        )
    return ExecutionTurn(
        timestamp=None,  # Reusing a tool plan does not observe a new model response.
        role=role_name,
        issue_id=issue_id,
        content="",
        tool_calls=planned_tool_call_objects(
            snapshot_payload,
            error_prefix="checkpoint",
        ),
        tokens_used=0,
        raw={
            "prompt_hash": snapshot_payload.get("prompt_hash"),
            "model": snapshot_payload.get("model"),
            "prompt_metadata": snapshot_payload.get("prompt_metadata", {}),
            "state_delta": snapshot_payload.get("state_delta", {}),
            "control_plane_resume": {
                "artifact_reused": True,
                "run_id": run.run_id,
                "attempt_id": attempt.attempt_id,
                "recovery_decision_id": recovery_decision.decision_id,
                "checkpoint_id": checkpoint.checkpoint_id,
                "checkpoint_acceptance_id": checkpoint_acceptance.acceptance_id,
                "state_snapshot_ref": checkpoint.state_snapshot_ref,
                "authorized_next_action": recovery_decision.authorized_next_action.value,
                "resumability_class": checkpoint_acceptance.resumability_class.value,
            },
        },
        note="control_plane_checkpoint_resume",
    )




__all__ = ["load_pre_effect_resume_turn_if_needed"]
