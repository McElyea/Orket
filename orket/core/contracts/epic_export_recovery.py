"""Bound local authority for initial export and explicitly requested exact retries."""
from __future__ import annotations

from typing import Literal, Protocol

from pydantic import Field, model_validator

from orket.core.contracts.control_plane_models import OperatorActionRecord
from orket.core.contracts.epic_publication import EpicRetainedRecord
from orket.core.domain.control_plane_enums import OperatorCommandClass, OperatorInputClass
from orket.core.domain.outward_authorization import args_hash


class EpicExportRecoveryRequest(EpicRetainedRecord):
    schema_version: Literal["epic_export_recovery_request.v1"] = "epic_export_recovery_request.v1"
    session_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    expected_owner_id: str = Field(min_length=1)
    expected_fencing_generation: int = Field(ge=1, strict=True)
    expected_claim_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_intent_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    operator_ref: str = Field(min_length=1)
    reason_ref: str = Field(min_length=1)
    resolution: Literal["retry_exact_commit"]


class EpicExportRecovery(EpicRetainedRecord):
    request: EpicExportRecoveryRequest
    owner_id: str = Field(min_length=1)
    decided_at: str = Field(min_length=1)
    action: OperatorActionRecord


def export_recovery_action(request: EpicExportRecoveryRequest, owner_id: str, at: str) -> OperatorActionRecord:
    return OperatorActionRecord(
        action_id="epic-export-recovery:" + args_hash({"session": request.session_id, "request": request.request_id}),
        actor_ref=request.operator_ref, input_class=OperatorInputClass.COMMAND,
        command_class=OperatorCommandClass.FORCE_RECONCILE, target_ref="epic-export:" + request.session_id,
        timestamp=at, precondition_basis_ref="request:sha256:" + request.digest(),
        result="export_owner_replaced_for_exact_commit",
        affected_transition_refs=["claim:sha256:" + request.expected_claim_digest,
                                  "intent:sha256:" + request.expected_intent_digest],
        receipt_refs=[f"owner:{owner_id}:fence:{request.expected_fencing_generation + 1}"],
    )


class EpicExportDispatch(EpicRetainedRecord):
    schema_version: Literal["epic_export_dispatch.v1"] = "epic_export_dispatch.v1"
    session_id: str = Field(min_length=1)
    intent_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    owner_id: str = Field(min_length=1)
    claimed_at: str = Field(min_length=1)
    fencing_generation: int = Field(default=1, ge=1, strict=True)
    phase: Literal["claimed", "settled"] = "claimed"
    recoveries: tuple[EpicExportRecovery, ...] = ()

    def claim_ref(self) -> dict[str, str]:
        return {"schema_version": self.schema_version, "session_id": self.session_id,
                "intent_digest": self.intent_digest,
                "digest": self.model_copy(update={"phase": "claimed"}).digest()}

    def origin_ref(self) -> dict[str, str]:
        owner = self.recoveries[0].request.expected_owner_id if self.recoveries else self.owner_id
        return self.model_copy(update={"owner_id": owner, "fencing_generation": 1, "recoveries": ()}).claim_ref()

    @model_validator(mode="after")
    def _validate_chain(self) -> EpicExportDispatch:
        if self.fencing_generation != len(self.recoveries) + 1:
            raise ValueError("E_EPIC_EXPORT_RECOVERY_HISTORY")
        seen = set()
        owner = self.recoveries[0].request.expected_owner_id if self.recoveries else self.owner_id
        for generation, entry in enumerate(self.recoveries, start=1):
            previous = self.model_copy(update={"owner_id": owner, "fencing_generation": generation,
                                               "recoveries": self.recoveries[:generation - 1]})
            request = entry.request
            if (request.request_id in seen or request.session_id != self.session_id
                    or request.expected_owner_id != owner or entry.owner_id == owner
                    or request.expected_fencing_generation != generation
                    or request.expected_intent_digest != self.intent_digest
                    or request.expected_claim_digest != previous.claim_ref()["digest"]
                    or entry.action != export_recovery_action(request, entry.owner_id, entry.decided_at)):
                raise ValueError("E_EPIC_EXPORT_RECOVERY_HISTORY")
            seen.add(request.request_id)
            owner = entry.owner_id
        if self.owner_id != owner:
            raise ValueError("E_EPIC_EXPORT_RECOVERY_HISTORY")
        return self


def export_dispatch_transition_allowed(prior: EpicExportDispatch, current: EpicExportDispatch) -> bool:
    if prior == current:
        return True
    if prior.phase != "claimed":
        return False
    if current == prior.model_copy(update={"phase": "settled"}):
        return True
    return (current.phase == "claimed" and current.owner_id != prior.owner_id
            and current.fencing_generation == prior.fencing_generation + 1
            and current.recoveries[:-1] == prior.recoveries
            and len(current.recoveries) == len(prior.recoveries) + 1
            and current.model_copy(update={"owner_id": prior.owner_id, "fencing_generation": prior.fencing_generation,
                                           "recoveries": prior.recoveries}) == prior)


class EpicExportDispatchTransaction(Protocol):
    async def get(self) -> EpicExportDispatch | None: ...

    async def save(self, record: EpicExportDispatch) -> None: ...
