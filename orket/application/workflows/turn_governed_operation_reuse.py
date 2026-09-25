"""Validate governed reuse of cached tool outcomes against durable execution authority."""
from __future__ import annotations

from orket.application.services.turn_tool_control_plane_closeout import ensure_current_execution_target
from orket.application.services.turn_tool_control_plane_service import (
    TurnToolControlPlaneError,
    TurnToolControlPlaneService,
)
from orket.application.services.turn_tool_control_plane_state_gate import ensure_existing_run_allows_execution
from orket.application.services.turn_tool_control_plane_support import effect_id_for
from orket.core.domain.control_plane_effect_journal import validate_effect_journal_chain
from orket.core.domain.control_plane_final_truth import ControlPlaneFinalTruthError

from .turn_executor_control_plane_evidence import validate_step_effect_alignment


def _governed_reuse_error(
    *, operation_id: str, reason: str, detail: str = "",
) -> TurnToolControlPlaneError:
    suffix = f": {detail}" if detail else ""
    return TurnToolControlPlaneError(f"E_OPERATION_ARTIFACT_INVALID:{reason}:{operation_id}{suffix}")


async def _require_governed_reuse_authority(
    *, control_plane_service: TurnToolControlPlaneService, run_id: str, attempt_id: str,
    namespace_scope: str, operation_id: str,
) -> None:
    repository = control_plane_service.execution_repository
    run = await repository.get_run_record(run_id=run_id)
    if run is None:
        raise _governed_reuse_error(operation_id=operation_id, reason="control_plane_anchor_missing")
    try:
        await ensure_existing_run_allows_execution(
            execution_repository=repository, publication=control_plane_service.publication,
            run=run, error_type=TurnToolControlPlaneError,
        )
    except (TurnToolControlPlaneError, ControlPlaneFinalTruthError) as exc:
        raise _governed_reuse_error(
            operation_id=operation_id, reason="control_plane_anchor_mismatch", detail=str(exc),
        ) from exc
    attempt = await repository.get_attempt_record(attempt_id=attempt_id)
    retained_run = await repository.get_run_record(run_id=run_id)
    if retained_run is None or attempt is None:
        raise _governed_reuse_error(operation_id=operation_id, reason="control_plane_anchor_missing")
    if retained_run != run:
        raise _governed_reuse_error(
            operation_id=operation_id, reason="control_plane_anchor_mismatch",
            detail="run changed during validation",
        )
    try:
        ensure_current_execution_target(run=retained_run, attempt=attempt,
            operation_name="governed operation reuse", error_type=TurnToolControlPlaneError)
    except TurnToolControlPlaneError as exc:
        raise _governed_reuse_error(
            operation_id=operation_id, reason="control_plane_anchor_mismatch", detail=str(exc),
        ) from exc
    if str(retained_run.namespace_scope or "").strip() != namespace_scope:
        raise _governed_reuse_error(
            operation_id=operation_id, reason="control_plane_anchor_mismatch",
            detail="run namespace changed",
        )


async def validate_governed_operation_reuse(
    *, control_plane_service: TurnToolControlPlaneService, run_id: str, attempt_id: str,
    namespace_scope: str, operation_id: str, expected_input_ref: str, fallback_tool_name: str,
) -> None:
    step = await control_plane_service.execution_repository.get_step_record(step_id=operation_id)
    entries = await control_plane_service.publication.repository.list_effect_journal_entries(run_id=run_id)
    try:
        if entries:
            validate_effect_journal_chain(entries)
    except ValueError as exc:
        raise _governed_reuse_error(
            operation_id=operation_id, reason="control_plane_anchor_mismatch", detail=str(exc),
        ) from exc
    await _require_governed_reuse_authority(
        control_plane_service=control_plane_service, run_id=run_id, attempt_id=attempt_id,
        namespace_scope=namespace_scope, operation_id=operation_id,
    )
    effect = next((entry for entry in entries
                   if entry.effect_id == effect_id_for(operation_id=operation_id)), None)
    if step is None or effect is None:
        raise _governed_reuse_error(operation_id=operation_id, reason="control_plane_anchor_missing")
    if (step.step_id != operation_id or step.attempt_id != attempt_id
            or str(step.input_ref or "").strip() != expected_input_ref):
        raise _governed_reuse_error(operation_id=operation_id, reason="control_plane_anchor_mismatch")
    try:
        validate_step_effect_alignment(
            step=step, effect=effect, operation_id=operation_id, attempt_id=attempt_id,
            namespace_scope=namespace_scope, fallback_tool_name=fallback_tool_name,
        )
    except TurnToolControlPlaneError as exc:
        raise _governed_reuse_error(
            operation_id=operation_id, reason="control_plane_anchor_mismatch", detail=str(exc),
        ) from exc


__all__ = ["validate_governed_operation_reuse"]
