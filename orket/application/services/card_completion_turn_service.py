"""Bind card turns to application acceptance and verify their completion claims."""
from __future__ import annotations

import json
from typing import Any

from orket.application.services.card_completion_prompt import card_completion_prompt_payload
from orket.application.services.card_completion_service import CardCompletionService
from orket.application.services.orchestrator_issue_control_plane_support import attempt_id_for_run, run_id_for_dispatch
from orket.core.contracts.card_completion import CompletionEvidenceSnapshot
from orket.core.contracts.card_completion_commit import (
    CardCompletionContext,
    CardCompletionRejected,
    CardCompletionRequest,
    is_card_completion_call,
)
from orket.core.contracts.repositories import CardRepository
from orket.core.domain.execution import ExecutionTurn
from orket.core.policies.card_completion import evaluate_card_completion


async def prepare_card_completion_turn(
    *, service: CardCompletionService | None, cards: CardRepository, context: dict[str, Any],
    card_id: str, session_id: str, seat_name: str, turn_index: int,
) -> str:
    run_id = run_id_for_dispatch(session_id=session_id, issue_id=card_id, seat_name=seat_name, turn_index=turn_index)
    bound = None if service is None else await service.begin_attempt(
        cards, card_id=card_id, run_id=run_id, attempt_id=attempt_id_for_run(run_id=run_id),
    )
    context["card_completion_context"] = bound
    context["card_completion_request"] = None
    if service is None:
        context["card_completion_decision"] = evaluate_card_completion(
            plan=None, scope=None, snapshot=CompletionEvidenceSnapshot(diagnostics=("completion_authority_missing",)),
        )
    else:
        await refresh_card_completion_request(service=service, cards=cards, context=context)
    return "\n\nDeclared card acceptance:\n" + json.dumps(card_completion_prompt_payload(context), ensure_ascii=False)


async def refresh_card_completion_request(
    *, service: CardCompletionService, cards: CardRepository, context: dict[str, Any],
) -> None:
    bound = context.get("card_completion_context")
    if bound is not None and not isinstance(bound, CardCompletionContext):
        raise CardCompletionRejected("E_CARD_COMPLETION_CONTEXT_REQUIRED")
    evaluated = await service.evaluate_attempt(cards, bound)
    context["card_completion_request"] = evaluated.request
    context["card_completion_decision"] = evaluated.decision


async def verify_card_completion_claims(
    *, cards: CardRepository, turn: ExecutionTurn, context: dict[str, Any],
) -> None:
    for call in turn.tool_calls:
        if not is_card_completion_call(call.tool, call.args):
            continue
        payload = call.result if isinstance(call.result, dict) else {}
        if call.error or payload.get("ok") is not True:
            raise CardCompletionRejected("E_CARD_COMPLETION_TOOL_FAILED")
        card_id = str(call.args.get("issue_id") or context.get("issue_id") or turn.issue_id)
        receipt = await cards.read_completion_receipt(card_id)
        if receipt is None or payload.get("completion_ref") != receipt.digest:
            raise CardCompletionRejected("E_CARD_COMPLETION_RESULT_UNVERIFIED")
        bound = context.get("card_completion_context")
        request = context.get("card_completion_request")
        if isinstance(bound, CardCompletionContext):
            matches = receipt.context == bound
        else:
            matches = isinstance(request, CardCompletionRequest) and request.context_digest == receipt.context.digest
        if not matches:
            raise CardCompletionRejected("E_CARD_COMPLETION_RESULT_SCOPE_STALE")


async def verify_turn_completion_claims(*, toolbox: Any, turn: ExecutionTurn, context: dict[str, Any]) -> None:
    if any(is_card_completion_call(call.tool, call.args) for call in turn.tool_calls):
        await toolbox.verify_completion_claims(turn, context)
