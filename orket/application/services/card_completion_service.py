"""Application authority for declared card acceptance and final evidence review."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from pydantic import TypeAdapter

from orket.application.services.card_acceptance_evaluation import build_card_acceptance_plan
from orket.application.services.card_acceptance_service import CardAcceptanceService
from orket.core.contracts.card_acceptance_inputs import CardAcceptanceDefinition
from orket.core.contracts.card_completion import CardCompletionDecision, CompletionEvidenceSnapshot
from orket.core.contracts.card_completion_commit import (
    CardCompletionContext,
    CardCompletionReceipt,
    CardCompletionRejected,
    CardCompletionRequest,
    card_completion_inputs,
)
from orket.core.contracts.repositories import CardRepository
from orket.core.domain.records import IssueRecord
from orket.core.policies.card_completion import evaluate_card_completion

# Reuse one immutable union parser; no runtime authority is retained here.
_DEFINITION_ADAPTER = TypeAdapter(CardAcceptanceDefinition)


def declared_card_acceptance(record: IssueRecord) -> CardAcceptanceDefinition | None:
    raw = record.params.get("completion_acceptance")
    return _DEFINITION_ADAPTER.validate_python(raw) if raw is not None else None


@dataclass(frozen=True)
class CardCompletionEvaluation:
    request: CardCompletionRequest | None
    decision: CardCompletionDecision


class CardCompletionService:
    def __init__(self, *, workspace_root: Path, acceptance: CardAcceptanceService):
        self.workspace_root = workspace_root
        self.acceptance = acceptance

    async def begin_attempt(
        self, cards: CardRepository, *, card_id: str, run_id: str, attempt_id: str,
    ) -> CardCompletionContext | None:
        record = await cards.get_by_id(card_id)
        if record is None:
            raise CardCompletionRejected("E_CARD_COMPLETION_CARD_MISSING")
        definition = declared_card_acceptance(record)
        if definition is None:
            return None
        root = await asyncio.to_thread(self.workspace_root.resolve)
        context = CardCompletionContext(
            card_id=record.id, run_id=run_id, attempt_id=attempt_id, generation=record.completion_generation + 1,
            workspace_root=str(root), definition_digest=definition.digest,
            workload_inputs_json=card_completion_inputs(record),
        )
        await cards.begin_completion_attempt(context)
        return context

    async def evaluate_attempt(
        self, cards: CardRepository, context: CardCompletionContext | None,
    ) -> CardCompletionEvaluation:
        if context is None:
            return CardCompletionEvaluation(None, evaluate_card_completion(
                plan=None, scope=None, snapshot=CompletionEvidenceSnapshot(),
            ))
        record = await cards.get_by_id(context.card_id)
        if record is None:
            raise CardCompletionRejected("E_CARD_COMPLETION_CARD_MISSING")
        definition = await self._current_definition(record, context)
        evaluated = await self.acceptance.verify(
            workspace_root=Path(context.workspace_root), definition=definition, card_id=context.card_id,
            run_id=context.run_id, attempt_id=context.attempt_id, workload_inputs_json=context.verification_inputs_json,
        )
        request = (CardCompletionRequest(context_digest=context.digest, evidence_digest=evaluated.evidence_digest)
                   if evaluated.evidence_digest is not None else None)
        return CardCompletionEvaluation(request, evaluated.decision)

    async def _current_definition(
        self, record: IssueRecord, context: CardCompletionContext,
    ) -> CardAcceptanceDefinition:
        definition = declared_card_acceptance(record)
        root = await asyncio.to_thread(self.workspace_root.resolve)
        if (definition is None or definition.digest != context.definition_digest
                or str(root) != context.workspace_root or record.id != context.card_id
                or record.completion_context != context or record.completion_generation != context.generation
                or card_completion_inputs(record) != context.workload_inputs_json):
            raise CardCompletionRejected("E_CARD_COMPLETION_CONTEXT_STALE")
        return definition

    async def authorize_completion(
        self, *, record: IssueRecord, context: CardCompletionContext, request: CardCompletionRequest,
    ) -> CardCompletionDecision:
        definition = await self._current_definition(record, context)
        if request.context_digest != context.digest:
            raise CardCompletionRejected("E_CARD_COMPLETION_CONTEXT_STALE")
        capture = await self.acceptance.capture_scope(
            workspace_root=Path(context.workspace_root), definition=definition, card_id=context.card_id,
            run_id=context.run_id, attempt_id=context.attempt_id, workload_inputs_json=context.verification_inputs_json,
        )
        if capture.diagnostics:
            return evaluate_card_completion(
                plan=build_card_acceptance_plan(definition), scope=capture.scope,
                snapshot=CompletionEvidenceSnapshot(diagnostics=capture.diagnostics),
            )
        return await self.acceptance.inspect(request.evidence_digest, definition=definition, scope=capture.scope)

    async def inspect_completion_receipt(
        self, *, record: IssueRecord, receipt: CardCompletionReceipt,
    ) -> CardCompletionDecision:
        definition = await self._current_definition(record, receipt.context)
        return await self.acceptance.inspect(
            receipt.request.evidence_digest, definition=definition, scope=receipt.decision.scope,
        )
