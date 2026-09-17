from __future__ import annotations

from dataclasses import replace
from typing import Any

from orket.adapters.storage.outward_store_transaction import OutwardStoreTransaction
from orket.application.services.outward_approval_service import redacted_args_preview
from orket.application.services.outward_run_execution_plan import (
    args_hash,
    model_proposal_ref,
    step_event_id,
    task_with_model_tool_call,
    task_with_policy_rejection,
)
from orket.application.services.outward_run_lifecycle import turn_completion_events
from orket.application.services.outward_terminal_service import publish_outward_terminal
from orket.core.domain.outward_run_events import LedgerEvent
from orket.core.domain.outward_runs import OutwardRunRecord

MODEL_PROPOSAL_CONTEXT = "model-produced governed tool call from retained provider response"


async def record_model_proposal_event(
    transaction: OutwardStoreTransaction,
    run: OutwardRunRecord,
    tool: str,
    tool_call: dict[str, Any],
    evidence: dict[str, Any],
    pii_fields: tuple[str, ...],
    *, at: str,
) -> OutwardRunRecord:
    model_invocation_ref = str(evidence.get("model_invocation_ref") or "").strip()
    tool_args_hash = str(evidence.get("tool_args_hash") or args_hash(tool_call["args"]))
    proposal_ref = model_proposal_ref(
        run_id=run.run_id,
        turn=run.current_turn,
        tool=tool,
        tool_args_hash=tool_args_hash,
    )
    run_with_model_call = replace(
        run,
        task=task_with_model_tool_call(
            run,
            tool_call=tool_call,
            model_invocation_ref=model_invocation_ref,
            proposal_ref=proposal_ref,
        ),
    )
    await transaction.update_run(run_with_model_call)
    await append_model_event(transaction, at=at,
        event_id=step_event_id(run.run_id, run.current_turn, 300, f"proposal:{tool}:{len(run.pending_proposals) + 1:04d}"),
        event_type="proposal_made",
        run=run_with_model_call,
        turn=run.current_turn,
        payload={
            "run_id": run.run_id,
            "namespace": run.namespace,
            "tool": tool,
            "args_preview": redacted_args_preview(tool_call["args"], pii_fields),
            "context_summary": MODEL_PROPOSAL_CONTEXT,
            "model_invocation_ref": model_invocation_ref,
            "model_invocation_sha256": str(evidence.get("model_invocation_sha256") or ""),
            "model_prompt_redacted_sha256": str(evidence.get("model_prompt_redacted_sha256") or ""),
            "model_response_content_sha256": str(evidence.get("model_response_content_sha256") or ""),
            "model_response_redacted_sha256": str(evidence.get("model_response_redacted_sha256") or ""),
            "proposal_extraction_ref": str(evidence.get("proposal_extraction_ref") or ""),
            "proposal_extraction_sha256": str(evidence.get("proposal_extraction_sha256") or ""),
            "provider_name": evidence.get("provider_name"),
            "model_name": evidence.get("model_name"),
            "tool_name": tool,
            "tool_args_hash": tool_args_hash,
            "proposal_ref": proposal_ref,
        },
    )
    return run_with_model_call

async def policy_reject(
    transaction: OutwardStoreTransaction,
    run: OutwardRunRecord,
    tool: str,
    tool_call: dict[str, Any],
    pii_fields: tuple[str, ...],
    reason: str,
    *, at: str,
) -> OutwardRunRecord:
    tool_args_hash = args_hash(tool_call["args"])
    proposal_ref = model_proposal_ref(
        run_id=run.run_id,
        turn=run.current_turn,
        tool=tool,
        tool_args_hash=tool_args_hash,
    )
    run_with_rejection = replace(
        run,
        task=task_with_policy_rejection(
            run,
            tool=tool,
            tool_args_hash=tool_args_hash,
            proposal_ref=proposal_ref,
            reason=reason,
        ),
    )
    await transaction.update_run(run_with_rejection)
    await append_model_event(transaction, at=at,
        event_id=step_event_id(run.run_id, run.current_turn, 350, f"proposal_policy_rejected:{tool}"),
        event_type="proposal_policy_rejected",
        run=run_with_rejection,
        turn=run.current_turn,
        payload={
            "run_id": run.run_id,
            "turn": run.current_turn,
            "tool": tool,
            "tool_name": tool,
            "args_preview": redacted_args_preview(tool_call["args"], pii_fields),
            "policy_result": "rejected",
            "reason": reason,
            "tool_args_hash": tool_args_hash,
            "proposal_ref": proposal_ref,
        },
    )
    for event in turn_completion_events(
        run_with_rejection, tool, "policy", at=at, outcome="policy_rejected", record_commitment=False,
    ):
        await append_new_event(transaction, event)
    return await publish_outward_terminal(
        transaction, run_with_rejection, at=at, reason=reason, outcome="policy_rejected",
        cause=await transaction.get_event(step_event_id(run.run_id, run.current_turn, 350, f"proposal_policy_rejected:{tool}")),
    )


async def append_model_event(
    transaction: OutwardStoreTransaction, *, event_id: str, event_type: str, run: OutwardRunRecord,
    turn: int, payload: dict[str, Any], at: str,
) -> None:
    await append_new_event(transaction, LedgerEvent(
        event_id=event_id, event_type=event_type, run_id=run.run_id, turn=turn,
        agent_id="outward-agent", at=at, payload=payload,
    ))


async def append_new_event(transaction: OutwardStoreTransaction, event: LedgerEvent) -> None:
    if await transaction.get_event(event.event_id) is not None:
        raise RuntimeError("E_OUTWARD_MODEL_PUBLICATION_CONFLICT")
    await transaction.append_event(event)
