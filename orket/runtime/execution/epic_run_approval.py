"""Serialize and restore the original epic context at an approval pause."""
from dataclasses import replace

from pydantic import TypeAdapter

from orket.core.contracts import (
    AttemptRecord,
    CheckpointAcceptanceRecord,
    CheckpointRecord,
    RunRecord,
    StepRecord,
)
from orket.core.domain.execution import ExecutionTurn
from orket.runtime.execution.epic_run_support import build_execution_artifacts
from orket.runtime.execution.epic_run_types import EpicRunContext


async def retain_approval_pause(owner, context):
    if owner.approval_pauses is None:
        raise ValueError("E_EPIC_APPROVAL_SERVICE_REQUIRED")
    await owner.approval_pauses.retain(
        session_id=context.setup.run_id, request=context.setup.publication_request,
        epic_asset=context.setup.epic_asset, model_override=context.setup.model_override,
        export_binding=owner.preparation.export_binding,
        artifacts=build_execution_artifacts(callbacks=owner.callbacks, context=context),
        transcript=TypeAdapter(list[ExecutionTurn]).dump_python(owner.orchestrator.transcript, mode="json"))


async def restore_approval_context(owner, setup, pause):
    async with owner.publication.repository.transaction(setup.run_id) as tx:
        admission = await tx.get_admission()
    artifacts = {**pause.artifacts, **await owner.approval_pauses.recovery_artifacts(setup.run_id)}
    owner.orchestrator.transcript[:] = TypeAdapter(list[ExecutionTurn]).validate_python(pause.transcript)
    owner._apply_runtime_capabilities(artifacts)
    return EpicRunContext(
        setup=replace(setup, admission=admission, resume_mode=True),
        deterministic_mode_contract=artifacts["deterministic_mode_contract"],
        route_decision_artifact=artifacts["route_decision_artifact"],
        control_plane_run=RunRecord.model_validate(artifacts["control_plane_run_record"]),
        control_plane_attempt=AttemptRecord.model_validate(artifacts["control_plane_attempt_record"]),
        control_plane_start_step=StepRecord.model_validate(artifacts["control_plane_step_record"]),
        control_plane_checkpoint=CheckpointRecord.model_validate(artifacts["control_plane_checkpoint_record"]),
        control_plane_checkpoint_acceptance=CheckpointAcceptanceRecord.model_validate(
            artifacts["control_plane_checkpoint_acceptance_record"]),
        run_contract_artifacts=artifacts,
        approval_resume_turns=await owner.approval_pauses.resume_turns(pause))
