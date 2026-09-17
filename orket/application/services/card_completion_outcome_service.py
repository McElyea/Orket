"""Inspect a complete build under the card writer guard before claiming success."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from orket.core.contracts.card_completion_commit import (
    SUCCESSFUL_CARD_STATUSES,
    CardCompletionReceipt,
    CardCompletionRejected,
    require_current_completion_receipt,
)
from orket.core.contracts.repositories import CardRepository
from orket.core.domain.records import IssueRecord


@dataclass(frozen=True)
class BuildCompletionSnapshot:
    build_id: str
    expected_card_ids: tuple[str, ...]
    backlog: tuple[IssueRecord, ...]
    accepted_receipts: tuple[tuple[str, str], ...]
    unverified_cards: tuple[tuple[str, str], ...]

    @property
    def sufficient(self) -> bool:
        return bool(self.backlog) and not self.unverified_cards and len(self.accepted_receipts) == len(self.backlog)

    @property
    def failure_reason(self) -> str | None:
        if self.sufficient:
            return None
        return "card_completion_unverified:" + (",".join(card for card, _ in self.unverified_cards) or "empty_backlog")

    def to_artifact(self) -> dict[str, Any]:
        return {
            "schema_version": "card_completion_outcome.v1", "build_id": self.build_id,
            "expected_card_ids": list(self.expected_card_ids),
            "card_count": len(self.backlog), "acceptance_satisfied": self.sufficient,
            "accepted_receipts": dict(self.accepted_receipts), "unverified_cards": dict(self.unverified_cards),
            "diagnostics": [] if self.backlog else ["empty_backlog"],
        }


async def inspect_build_completion(
    *, cards: CardRepository, build_id: str, expected_card_ids: tuple[str, ...],
) -> BuildCompletionSnapshot:
    accepted, unverified = [], []
    # Read the complete inventory and all receipt bindings while supported card
    # writers are excluded. Individually valid reads need not form a valid build snapshot.
    async with cards.completion_write_guard():
        backlog = tuple(await cards.get_by_build(build_id))
        present_ids = {record.id for record in backlog}
        unverified.extend((card, "E_CARD_COMPLETION_CARD_MISSING") for card in expected_card_ids if card not in present_ids)
        for record in backlog:
            try:
                receipt = await require_accepted_card_receipt(cards=cards, record=record)
            except CardCompletionRejected as exc:
                unverified.append((record.id, str(exc)))
                continue
            accepted.append((record.id, receipt.digest))
    return BuildCompletionSnapshot(build_id, expected_card_ids, backlog, tuple(accepted), tuple(unverified))


async def require_accepted_card_receipt(*, cards: CardRepository, record: IssueRecord) -> CardCompletionReceipt:
    """Shared acceptance read; aggregate callers hold the repository writer guard."""
    if record.status.value not in SUCCESSFUL_CARD_STATUSES:
        raise CardCompletionRejected(f"card_status:{record.status.value}")
    receipt = await cards.read_completion_receipt(record.id)
    if receipt is None:
        raise CardCompletionRejected("E_CARD_COMPLETION_RECEIPT_MISSING")
    require_current_completion_receipt(record, receipt)
    return receipt


async def project_card_completion(*, cards: CardRepository, record: IssueRecord) -> dict[str, Any]:
    """Project current retained acceptance; caller holds the repository writer guard."""
    try:
        receipt = await require_accepted_card_receipt(cards=cards, record=record)
    except CardCompletionRejected as exc:
        return {"completion_accepted": False, "completion_ref": None, "completion_rejection": str(exc)}
    return {"completion_accepted": True, "completion_ref": receipt.digest, "completion_rejection": None}
