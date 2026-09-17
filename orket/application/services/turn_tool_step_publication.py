"""Atomic dispatch admission and observed step/effect publication."""
from __future__ import annotations

from copy import deepcopy

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.turn_tool_control_plane_closeout import ensure_current_execution_target
from orket.application.services.turn_tool_control_plane_state_gate import (
    ensure_existing_run_allows_execution,
    existing_effect_for_operation,
    require_turn_dispatch_contract,
)
from orket.application.services.turn_tool_control_plane_support import (
    capability_for,
    digest,
    effect_id_for,
    resource_refs,
    step_result_classification,
    tool_authorization_ref,
    tool_call_ref,
    tool_operation_ref,
    tool_result_ref,
    utc_now,
)
from orket.core.contracts import StepRecord
from orket.core.contracts.turn_tool_dispatch import DISPATCH_STARTED, is_unresolved_tool_dispatch
from orket.core.domain import ResidualUncertaintyClassification


def _step(*, run, attempt_id, step_id, tool_name, tool_args, binding, operation_id, result=None, replayed=False):
    call_digest = digest({"tool_name": tool_name, "tool_args": tool_args,
                          "binding": dict(binding or {}), "operation_id": operation_id})
    observed = result is not None
    return StepRecord(
        step_id=step_id, attempt_id=attempt_id, step_kind="governed_tool_operation",
        namespace_scope=run.namespace_scope, input_ref=tool_call_ref(tool_call_digest=call_digest),
        output_ref=tool_result_ref(operation_id=operation_id) if observed else None,
        capability_used=capability_for(tool_name=tool_name, binding=binding) if observed else None,
        resources_touched=resource_refs(tool_name=tool_name, tool_args=tool_args, result=result,
                                       namespace_scope=run.namespace_scope) if observed else [],
        observed_result_classification=step_result_classification(result=result, replayed=replayed) if observed else DISPATCH_STARTED,
        receipt_refs=[tool_operation_ref(operation_id=operation_id), tool_call_ref(tool_call_digest=call_digest)],
        closure_classification=("step_completed" if bool(result.get("ok", False)) else "step_failed") if observed else DISPATCH_STARTED,
    ), call_digest


async def _current_target(execution, run_id, attempt_id, error_type):
    run = await execution.get_run_record(run_id=run_id)
    attempt = await execution.get_attempt_record(attempt_id=attempt_id)
    if run is None or attempt is None:
        raise error_type(f"governed turn-tool execution not found: {run_id}/{attempt_id}")
    ensure_current_execution_target(run=run, attempt=attempt, operation_name="tool dispatch publication", error_type=error_type)
    return run


def _require_same_step(existing, proposed, error_type):
    fields = ("step_id", "attempt_id", "step_kind", "namespace_scope", "input_ref", "receipt_refs")
    if existing is not None and any(getattr(existing, field) != getattr(proposed, field) for field in fields):
        raise error_type(f"governed tool step authority mismatch: {proposed.step_id}")


async def prepare_tool_dispatch(
    *, transactions, authority, run_id, attempt_id, step_id, tool_name, tool_args, binding, operation_id, error_type,
):
    # Capture caller-owned inputs before the first transaction await.
    tool_args, binding = deepcopy((tool_args, binding))
    async with transactions() as transaction:
        publication = ControlPlanePublicationService(repository=transaction.records, authority=authority)
        run = await _current_target(transaction.execution, run_id, attempt_id, error_type)
        await ensure_existing_run_allows_execution(execution_repository=transaction.execution,
            publication=publication, run=run, error_type=error_type)
        existing = await transaction.execution.get_step_record(step_id=step_id)
        effect = await existing_effect_for_operation(publication=publication, run_id=run_id,
                                                     effect_id=effect_id_for(operation_id=operation_id))
        if existing is not None or effect is not None:
            raise error_type(f"governed tool operation already admitted: {operation_id}; redispatch refused")
        record, _ = _step(run=run, attempt_id=attempt_id, step_id=step_id, tool_name=tool_name,
                          tool_args=tool_args, binding=binding, operation_id=operation_id)
        return await transaction.execution.save_step_record(record=record)


async def publish_step_result_atomic(
    *, transactions, authority, run_id, attempt_id, step_id, tool_name, tool_args, result, binding,
    operation_id, replayed, error_type,
):
    tool_args, binding, result = deepcopy((tool_args, binding, result))
    async with transactions() as transaction:
        publication = ControlPlanePublicationService(repository=transaction.records, authority=authority)
        run = await transaction.execution.get_run_record(run_id=run_id)
        if run is None:
            raise error_type(f"governed turn-tool run not found: {run_id}")
        proposed, call_digest = _step(run=run, attempt_id=attempt_id, step_id=step_id, tool_name=tool_name,
            tool_args=tool_args, binding=binding, operation_id=operation_id, result=result, replayed=replayed)
        existing = await transaction.execution.get_step_record(step_id=step_id)
        _require_same_step(existing, proposed, error_type)
        effect = await existing_effect_for_operation(publication=publication, run_id=run_id,
                                                     effect_id=effect_id_for(operation_id=operation_id))
        if effect is not None:
            if (existing is None or is_unresolved_tool_dispatch(existing) or effect.attempt_id != attempt_id
                    or effect.step_id != step_id or effect.authorization_basis_ref != tool_authorization_ref(tool_call_digest=call_digest)):
                raise error_type(f"governed tool effect authority mismatch: {operation_id}")
            return existing, effect
        await require_turn_dispatch_contract(transaction.records, run, error_type)
        await _current_target(transaction.execution, run_id, attempt_id, error_type)
        record = existing
        if record is None or is_unresolved_tool_dispatch(record):
            if record is not None:
                proposed = proposed.model_copy(update={"state_revision": record.state_revision})
            record = await transaction.execution.save_step_record(record=proposed)
        effect = await publication.append_effect_journal_entry(
            journal_entry_id=f"turn-tool-journal:{operation_id}", effect_id=effect_id_for(operation_id=operation_id),
            run_id=run_id, attempt_id=attempt_id, step_id=step_id,
            authorization_basis_ref=tool_authorization_ref(tool_call_digest=call_digest), publication_timestamp=utc_now(),
            intended_target_ref=record.resources_touched[0] if record.resources_touched else f"tool:{tool_name}",
            observed_result_ref=tool_result_ref(operation_id=operation_id),
            uncertainty_classification=ResidualUncertaintyClassification.NONE,
            integrity_verification_ref=tool_operation_ref(operation_id=operation_id),
        )
        return record, effect
