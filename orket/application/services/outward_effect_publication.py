from __future__ import annotations

from dataclasses import replace

from orket.adapters.storage.outward_store_transaction import OutwardStoreTransaction
from orket.application.services.outward_model_admission_inputs import admit_model_turn
from orket.application.services.outward_run_execution_plan import (
    acceptance_tool_steps,
    failure_reason,
    is_last_step,
    proposal_suffix,
    step_event_id,
    task_with_tool_result,
)
from orket.application.services.outward_run_lifecycle import (
    run_event,
    turn_completion_events,
    turn_started_event,
)
from orket.application.services.outward_terminal_service import publish_outward_terminal
from orket.core.domain.outward_authorization import OutwardAuthorization
from orket.core.domain.outward_effects import OutwardEffectRecord
from orket.core.domain.outward_runs import OutwardRunRecord


async def publish_effect_projection(
    transaction: OutwardStoreTransaction, binding: OutwardAuthorization,
    effect: OutwardEffectRecord, run: OutwardRunRecord, *, at: str,
) -> tuple[OutwardRunRecord, bool]:
    receipt = effect.receipt
    if receipt is None:
        raise RuntimeError("E_OUTWARD_EFFECT_RECEIPT_REQUIRED")
    payload, result = receipt["event"], receipt["result"]
    events = [run_event(
        run, event_id=step_event_id(run.run_id, binding.turn, 400, f"tool:{binding.tool}:{proposal_suffix(binding.proposal_id)}"),
        event_type="tool_invoked", at=receipt["observed_at"], payload=payload,
    )]
    advance = False
    terminal_outcome, terminal_reason = None, None
    if payload.get("outcome") != "success":
        projected = run
        terminal_outcome, terminal_reason = "failed", failure_reason(payload)
    else:
        projected = replace(run, task=task_with_tool_result(
            run, proposal_id=binding.proposal_id, tool=binding.tool, result=result,
        ))
        events.extend(turn_completion_events(run, binding.tool, binding.proposal_id, at=at, outcome="success"))
        if is_last_step(run, acceptance_tool_steps(run)):
            terminal_outcome = "success"
        elif run.current_turn >= run.max_turns:
            terminal_outcome, terminal_reason = "failed", "max_turns exceeded before next governed step"
        else:
            projected = replace(projected, status="running", current_turn=run.current_turn + 1, pending_proposals=())
            events.append(turn_started_event(projected, at=at))
            await admit_model_turn(transaction, projected, at=at)
            advance = True
    for event in events:
        if await transaction.get_event(event.event_id) is not None:
            raise RuntimeError("E_OUTWARD_EFFECT_PUBLICATION_CONFLICT")
        await transaction.append_event(event)
    if terminal_outcome is not None:
        projected = await publish_outward_terminal(transaction, projected, at=at, outcome=terminal_outcome,
            reason=terminal_reason, cause=effect)
        return projected, False
    await transaction.update_run(projected)
    return projected, advance
