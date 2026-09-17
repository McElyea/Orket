"""Card completion requests identify evidence; only application authority admits it."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Annotated, Literal, Protocol, Self, TypeVar

from pydantic import Field, model_validator

from orket.core.contracts.card_completion import CardCompletionDecision, CompletionRecord, Reference, Sha256

if TYPE_CHECKING:
    from orket.core.domain.records import IssueRecord

SUCCESSFUL_CARD_STATUSES = frozenset({"done", "guard_approved"})
MutationResult = TypeVar("MutationResult")


def is_card_completion_call(tool_name: str, arguments: dict) -> bool:
    return tool_name == "update_issue_status" and str(arguments.get("status", "")).lower() in SUCCESSFUL_CARD_STATUSES


def card_completion_inputs(record: IssueRecord) -> str:
    excluded = {"status", "note", "verification", "metrics", "created_at", "completion_generation",
                "completion_context", "completion_ref"}
    return json.dumps(record.model_dump(mode="json", exclude=excluded), sort_keys=True, separators=(",", ":"), allow_nan=False)


class CardCompletionContext(CompletionRecord):
    schema_version: Literal["card_completion_context.v1"] = "card_completion_context.v1"
    card_id: Reference
    run_id: Reference
    attempt_id: Reference
    generation: Annotated[int, Field(strict=True, ge=1, le=9_223_372_036_854_775_807)]
    workspace_root: Reference
    definition_digest: Sha256
    workload_inputs_json: Reference

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode("utf-8")).hexdigest()

    @property
    def verification_inputs_json(self) -> str:
        return json.dumps({"completion_context": self.model_dump(mode="json"),
                           "card_inputs": json.loads(self.workload_inputs_json)}, sort_keys=True, separators=(",", ":"))


class CardCompletionRequest(CompletionRecord):
    context_digest: Sha256
    evidence_digest: Sha256


class CardCompletionReceipt(CompletionRecord):
    schema_version: Literal["card_completion_receipt.v1"] = "card_completion_receipt.v1"
    context: CardCompletionContext
    request: CardCompletionRequest
    target_status: Literal["done", "guard_approved"]
    decision: CardCompletionDecision

    @model_validator(mode="after")
    def require_bound_acceptance(self) -> Self:
        scope = self.decision.scope
        if (not self.decision.sufficient or scope is None or self.request.context_digest != self.context.digest
                or (scope.card_id, scope.run_id, scope.attempt_id) !=
                (self.context.card_id, self.context.run_id, self.context.attempt_id)):
            raise ValueError("E_CARD_COMPLETION_RECEIPT_BINDING")
        return self

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode("utf-8")).hexdigest()


class CardCompletionRejected(ValueError):
    def __init__(self, reason: str, decision: CardCompletionDecision | None = None):
        super().__init__(reason)
        self.decision = decision


def require_current_completion_receipt(record: IssueRecord, receipt: CardCompletionReceipt) -> None:
    if (record.status.value != receipt.target_status or record.completion_ref != receipt.digest
            or record.completion_context != receipt.context or record.completion_generation != receipt.context.generation
            or card_completion_inputs(record) != receipt.context.workload_inputs_json):
        raise CardCompletionRejected("E_CARD_COMPLETION_RECEIPT_STALE")


class CardCompletionAuthority(Protocol):
    async def authorize_completion(
        self, *, record: IssueRecord, context: CardCompletionContext, request: CardCompletionRequest,
    ) -> CardCompletionDecision: ...

    async def inspect_completion_receipt(
        self, *, record: IssueRecord, receipt: CardCompletionReceipt,
    ) -> CardCompletionDecision: ...


class CardWorkspaceMutationAuthority(Protocol):
    async def run(self, operation: Callable[[], Awaitable[MutationResult]]) -> MutationResult: ...
