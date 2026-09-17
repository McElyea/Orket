"""Own local export fencing without changing retained workload or Git intent."""
from __future__ import annotations

from collections.abc import Callable

from orket.core.contracts.epic_export_recovery import (
    EpicExportDispatch,
    EpicExportRecovery,
    EpicExportRecoveryRequest,
    export_recovery_action,
)
from orket.core.contracts.epic_publication import EpicPreparationRecord, EpicPublicationPlan, EpicPublicationTransaction
from orket.core.domain.outward_authorization import args_hash

EXPORT_OWNER_ARTIFACT = "epic_export_dispatch"


async def retained_export_owner(transaction: EpicPublicationTransaction,
                                preparation: EpicPreparationRecord) -> EpicExportDispatch | None:
    current = await transaction.export_dispatch.get()
    marker = preparation.artifacts.get(EXPORT_OWNER_ARTIFACT)
    if marker is None and current is None:
        return None  # Older preparations allow confirmation, never inferred retry permission.
    if (current is None or marker != current.origin_ref() or preparation.export_intent is None
            or current.intent_digest != args_hash(preparation.export_intent.model_dump(mode="json"))
            or current.session_id != preparation.plan.session_id or preparation.phase not in (4, 5)
            or current.phase != ("settled" if preparation.phase == 5 else "claimed")):
        raise ValueError("E_EPIC_EXPORT_DISPATCH_EVIDENCE_CONFLICT")
    return current


async def validate_published_export(transaction: EpicPublicationTransaction, plan: EpicPublicationPlan) -> None:
    preparation = await transaction.get_preparation()
    marker = plan.ledger["artifacts"].get(EXPORT_OWNER_ARTIFACT)
    if preparation is None:
        if marker is not None or await transaction.export_dispatch.get() is not None:
            raise ValueError("E_EPIC_EXPORT_DISPATCH_EVIDENCE_CONFLICT")
        return
    current = await retained_export_owner(transaction, preparation)
    if marker is None and current is None:
        return
    if current is None or current.phase != "settled" or marker != current.claim_ref():
        raise ValueError("E_EPIC_EXPORT_PUBLICATION_OWNER_CONFLICT")
    receipt = plan.ledger["artifacts"].get("gitea_export", {})
    intent = preparation.export_intent
    if not intent or receipt.get("commit") != intent.commit or receipt.get("tree") != intent.tree:
        raise ValueError("E_EPIC_EXPORT_PUBLICATION_RECEIPT_CONFLICT")


class EpicExportRecoveryService:
    def __init__(self, *, owner_id: Callable[[], str], now: Callable[[], str]):
        self.owner_id, self.now = owner_id, now

    async def claim(self, transaction: EpicPublicationTransaction,
                    preparation: EpicPreparationRecord) -> EpicExportDispatch:
        if preparation.export_intent is None or preparation.phase != 4 or await transaction.export_dispatch.get() is not None:
            raise ValueError("E_EPIC_EXPORT_DISPATCH_CLAIM_CONFLICT")
        claim = EpicExportDispatch(session_id=preparation.plan.session_id, owner_id=self.owner_id(), claimed_at=self.now(),
                                   intent_digest=args_hash(preparation.export_intent.model_dump(mode="json")))
        await transaction.export_dispatch.save(claim)
        return claim

    async def replace(self, transaction: EpicPublicationTransaction, preparation: EpicPreparationRecord,
                      request: EpicExportRecoveryRequest) -> EpicExportDispatch | None:
        current = await retained_export_owner(transaction, preparation)
        if current is None:
            raise ValueError("E_EPIC_EXPORT_RECOVERY_OWNER_MISSING")
        if request.session_id != current.session_id or request.expected_intent_digest != current.intent_digest:
            raise ValueError("E_EPIC_EXPORT_RECOVERY_REQUEST_CONFLICT")
        matches = [entry for entry in current.recoveries if entry.request.request_id == request.request_id]
        if matches:
            if matches[0].request != request:
                raise ValueError("E_EPIC_EXPORT_RECOVERY_REQUEST_CONFLICT")
            if matches[0] != current.recoveries[-1]:
                raise ValueError("E_EPIC_EXPORT_RECOVERY_SUPERSEDED")
            return None  # An observed previous grant is not a fresh local dispatch grant.
        if current.phase != "claimed" or preparation.phase != 4:
            raise ValueError("E_EPIC_EXPORT_RECOVERY_NOT_PENDING")
        if (request.expected_owner_id != current.owner_id
                or request.expected_fencing_generation != current.fencing_generation
                or request.expected_claim_digest != current.claim_ref()["digest"]):
            raise ValueError("E_EPIC_EXPORT_FENCE_CONFLICT")
        owner, at = self.owner_id(), self.now()
        entry = EpicExportRecovery(request=request, owner_id=owner, decided_at=at,
                                   action=export_recovery_action(request, owner, at))
        replacement = EpicExportDispatch.model_validate_json(current.model_copy(update={
            "owner_id": owner, "fencing_generation": current.fencing_generation + 1,
            "recoveries": (*current.recoveries, entry)}).model_dump_json())
        await transaction.export_dispatch.save(replacement)
        return replacement
