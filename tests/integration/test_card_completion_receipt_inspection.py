"""Completion claims require current state and readable retained acceptance."""
from __future__ import annotations

import asyncio

import pytest

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.application.services.card_completion_turn_service import verify_card_completion_claims
from orket.core.contracts.card_completion_commit import CardCompletionRejected
from orket.core.domain.execution import ExecutionTurn, ToolCall
from orket.core.domain.records import IssueRecord
from orket.schema import CardStatus
from tests.helpers.card_completion import complete_existing_card

pytestmark = pytest.mark.integration


async def _completed(tmp_path):
    repo = AsyncCardRepository(tmp_path / "cards.db")
    await repo.save(IssueRecord(id="card", summary="Increment", seat="developer"))
    repo, service, bound, evaluation = await complete_existing_card(repo, "card", tmp_path / "workspace")
    receipt = await repo.read_completion_receipt("card")
    turn = ExecutionTurn(timestamp=None, role="integrity_guard", issue_id="card", content="", tokens_used=0,
                         tool_calls=[ToolCall(tool="update_issue_status", args={"status": "done"},
                                              result={"ok": True, "completion_ref": receipt.digest})])
    context = {"issue_id": "card", "card_completion_context": bound, "card_completion_request": evaluation.request}
    return repo, service, turn, context


@pytest.mark.asyncio
# Layer: integration
async def test_completion_inspection_does_not_initialize_a_missing_store(tmp_path):
    missing = tmp_path / "absent.db"
    with pytest.raises(CardCompletionRejected, match="RECEIPT_UNVERIFIABLE"):
        await AsyncCardRepository(missing).read_completion_receipt("card")
    assert not await asyncio.to_thread(missing.exists)


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["none", "reopen", "receipt_ref", "scope", "missing_evidence"])
# Layer: integration
async def test_completion_claim_revalidates_current_receipt_and_retained_evidence(tmp_path, change):
    repo, service, turn, context = await _completed(tmp_path)
    if change == "reopen":
        await repo.update_status("card", CardStatus.CODE_REVIEW)
    elif change == "receipt_ref":
        turn.tool_calls[0].result["completion_ref"] = "0" * 64
    elif change == "scope":
        context["card_completion_context"] = context["card_completion_context"].model_copy(update={"run_id": "different"})
    elif change == "missing_evidence":
        await asyncio.to_thread(service.acceptance.evidence_store.db_path.unlink)
    if change == "none":
        await verify_card_completion_claims(cards=repo, turn=turn, context=context)
    else:
        with pytest.raises(CardCompletionRejected):
            await verify_card_completion_claims(cards=repo, turn=turn, context=context)
    if change == "missing_evidence":
        assert not await asyncio.to_thread(service.acceptance.evidence_store.db_path.exists)
