"""Application-owned dependency inspection and bounded planner input."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from orket.application.services.card_completion_outcome_service import (
    inspect_build_completion,
    require_accepted_card_receipt,
)
from orket.core.contracts.card_completion_commit import CardCompletionRejected
from orket.core.contracts.repositories import CardRepository
from orket.core.domain.records import IssueRecord
from orket.decision_nodes.contracts import PlanningInput
from orket.exceptions import ExecutionFailed
from orket.schema import CardStatus, IssueConfig

_DISPATCHABLE = frozenset({CardStatus.READY, CardStatus.IN_PROGRESS, CardStatus.CODE_REVIEW,
                          CardStatus.AWAITING_GUARD_REVIEW})


@dataclass(frozen=True)
class CardDispatchSnapshot:
    backlog: tuple[IssueRecord, ...]
    eligible: tuple[IssueRecord, ...]
    dependency_rejections: dict[str, dict[str, str]]

    @property
    def independent_ready(self) -> list[IssueRecord]:
        return [card for card in self.eligible if card.status == CardStatus.READY]

    def plan(self, planner: Any, target_issue_id: str | None) -> list[IssueRecord]:
        # Strategies select among inspected cards; mutations to their copies do
        # not rewrite the authoritative dispatch payload or dependency inventory.
        proposed = planner.plan(PlanningInput(
            backlog=[card.model_copy(deep=True) for card in self.eligible],
            independent_ready=[card.model_copy(deep=True) for card in self.independent_ready],
            target_issue_id=target_issue_id,
        ))
        by_id = {card.id: card for card in self.eligible}
        selected = []
        seen = set()
        for proposal in proposed:
            card_id = getattr(proposal, "id", None)
            if card_id not in by_id or card_id in seen:
                raise ExecutionFailed(f"E_CARD_DISPATCH_UNADMITTED:{card_id}")
            selected.append(by_id[card_id])
            seen.add(card_id)
        return selected


async def read_card_dispatch_snapshot(*, cards: CardRepository, build_id: str) -> CardDispatchSnapshot:
    inspection = await inspect_build_completion(cards=cards, build_id=build_id, expected_card_ids=())
    accepted = {card_id for card_id, _ in inspection.accepted_receipts}
    failures = dict(inspection.unverified_cards)
    rejected = {card.id: {dep: failures.get(dep, "E_CARD_DEPENDENCY_NOT_IN_BUILD")
                         for dep in card.depends_on if dep not in accepted} for card in inspection.backlog}
    rejected = {card_id: reasons for card_id, reasons in rejected.items() if reasons}
    eligible = tuple(card for card in inspection.backlog
                     if card.status in _DISPATCHABLE and card.id not in rejected)
    return CardDispatchSnapshot(inspection.backlog, eligible, rejected)


async def build_card_dependency_context(*, cards: CardRepository, issue: IssueConfig) -> dict[str, Any]:
    depends_on = list(issue.depends_on or [])
    async with cards.completion_write_guard():
        current = await cards.get_by_id(issue.id)
        if current is None:
            raise ExecutionFailed(f"E_CARD_DISPATCH_CARD_MISSING:{issue.id}")
        if current.build_id != issue.build_id or list(current.depends_on) != depends_on:
            raise ExecutionFailed(f"E_CARD_DEPENDENCY_INPUT_STALE:{issue.id}")
        if current.status != issue.status:
            raise ExecutionFailed(f"E_CARD_DISPATCH_STATE_STALE:{issue.id}")
        return await inspect_card_dependencies(cards=cards, record=current)


async def inspect_card_dependencies(*, cards: CardRepository, record: IssueRecord) -> dict[str, Any]:
    """Inspect dependencies for dispatch or projection; caller holds the writer guard."""
    depends_on = list(record.depends_on)
    statuses, accepted, rejected = {}, {}, {}
    for dep_id in depends_on:
        prerequisite = await cards.get_by_id(dep_id)
        statuses[dep_id] = prerequisite.status.value if prerequisite else "missing"
        try:
            if prerequisite is None:
                raise CardCompletionRejected("E_CARD_COMPLETION_CARD_MISSING")
            if prerequisite.build_id != record.build_id:
                raise CardCompletionRejected("E_CARD_DEPENDENCY_BUILD_MISMATCH")
            receipt = await require_accepted_card_receipt(cards=cards, record=prerequisite)
        except CardCompletionRejected as exc:
            rejected[dep_id] = str(exc)
        else:
            accepted[dep_id] = receipt.digest
    return {"depends_on": depends_on, "dependency_count": len(depends_on), "dependency_statuses": statuses,
            "unresolved_dependencies": [dep for dep in depends_on if dep in rejected],
            "accepted_dependency_receipts": accepted, "dependency_rejections": rejected}
