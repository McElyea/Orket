"""Retained inputs and progress for publication after epic outcome preparation."""
from __future__ import annotations

import hashlib
from contextlib import AbstractAsyncContextManager
from typing import TYPE_CHECKING, Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from orket.core.contracts.control_plane_models import OperatorActionRecord
from orket.core.contracts.gitea_export import GiteaExportIntent
from orket.core.domain.control_plane_enums import OperatorCommandClass, OperatorInputClass
from orket.core.domain.outward_authorization import args_hash, canonical_json

if TYPE_CHECKING:
    from orket.core.contracts.epic_approval_pause import EpicApprovalPauseTransaction
    from orket.core.contracts.epic_export_recovery import EpicExportDispatchTransaction


class EpicPublicationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["epic_publication.v1"] = "epic_publication.v1"
    session_id: str
    request: dict[str, Any]
    ledger: dict[str, Any]
    snapshot: dict[str, Any] | None
    transcript: list[dict[str, Any]]


class EpicRetainedRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    def digest(self) -> str:
        return hashlib.sha256(canonical_json(self.model_dump(mode="json")).encode("utf-8")).hexdigest()


class EpicPublicationRecord(EpicRetainedRecord):
    plan: EpicPublicationPlan
    phase: Literal[0, 1, 2, 3, 4] = 0


class EpicPreparationRecord(EpicRetainedRecord):
    schema_version: Literal["epic_preparation.v2"] = "epic_preparation.v2"
    plan: EpicPublicationPlan
    policy: dict[str, Any]
    export_binding: dict[str, Any]
    phase: Literal[0, 1, 2, 3, 4, 5] = 0
    artifacts: dict[str, Any]
    summary: dict[str, Any] | None = None
    export_intent: GiteaExportIntent | None = None


class EpicWorkloadFailure(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    reason: str
    failure_class: str


class EpicWorkloadOutcome(EpicRetainedRecord):
    """Observed return or failure, not a claim of accepted completion."""

    schema_version: Literal["epic_workload_outcome.v1"] = "epic_workload_outcome.v1"
    session_id: str
    request: dict[str, Any]
    policy: dict[str, Any]
    export_binding: dict[str, Any]
    artifacts: dict[str, Any]
    transcript: list[dict[str, Any]]
    snapshot: dict[str, Any]
    observed_at: str
    failure: EpicWorkloadFailure | None = None


class EpicAdmissionRecoveryRequest(EpicRetainedRecord):
    schema_version: Literal["epic_admission_recovery_request.v1"] = "epic_admission_recovery_request.v1"
    session_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    expected_owner_id: str = Field(min_length=1)
    expected_fencing_generation: int = Field(ge=1, strict=True)
    expected_claim_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    operator_ref: str = Field(min_length=1)
    reason_ref: str = Field(min_length=1)


class EpicAdmissionRecovery(EpicRetainedRecord):
    request: EpicAdmissionRecoveryRequest
    owner_id: str = Field(min_length=1)
    decided_at: str
    action: OperatorActionRecord


def admission_recovery_action(request: EpicAdmissionRecoveryRequest, owner_id: str, at: str) -> OperatorActionRecord:
    return OperatorActionRecord(
        action_id="epic-admission-recovery:" + args_hash({"session": request.session_id, "request": request.request_id}),
        actor_ref=request.operator_ref, input_class=OperatorInputClass.COMMAND,
        command_class=OperatorCommandClass.FORCE_RECONCILE, target_ref="epic-admission:" + request.session_id,
        timestamp=at, precondition_basis_ref="request:sha256:" + request.digest(), result="pre_initialization_owner_replaced",
        affected_transition_refs=["claim:sha256:" + request.expected_claim_digest],
        receipt_refs=[f"owner:{owner_id}:fence:{request.expected_fencing_generation + 1}"],
    )


class EpicRunAdmission(EpicRetainedRecord):
    schema_version: Literal["epic_run_admission.v2"] = "epic_run_admission.v2"
    session_id: str = Field(min_length=1)
    owner_id: str = Field(min_length=1)
    request: dict[str, Any]
    export_binding: dict[str, Any]
    resources: list[str]
    admitted_at: str
    phase: Literal["active", "released"] = "active"
    initialization_started: StrictBool = False
    fencing_generation: int = Field(default=1, ge=1, strict=True)
    recoveries: tuple[EpicAdmissionRecovery, ...] = ()

    def claim_ref(self) -> dict[str, str]:
        return {"schema_version": self.schema_version, "session_id": self.session_id,
                "owner_id": self.owner_id,
                "digest": self.model_copy(update={"phase": "active", "initialization_started": False}).digest()}

    @model_validator(mode="after")
    def _validate_recovery_history(self) -> EpicRunAdmission:
        if self.fencing_generation != len(self.recoveries) + 1:
            raise ValueError("E_EPIC_ADMISSION_RECOVERY_HISTORY")
        request_ids = set()
        for index, recovery in enumerate(self.recoveries):
            request = recovery.request
            previous = self.model_copy(update={"owner_id": request.expected_owner_id, "fencing_generation": index + 1,
                                               "recoveries": self.recoveries[:index]})
            if (request.session_id != self.session_id or request.expected_fencing_generation != index + 1
                    or request.expected_claim_digest != previous.claim_ref()["digest"]
                    or recovery.owner_id == request.expected_owner_id or request.request_id in request_ids
                    or (index and request.expected_owner_id != self.recoveries[index - 1].owner_id)
                    or recovery.action != admission_recovery_action(request, recovery.owner_id, recovery.decided_at)):
                raise ValueError("E_EPIC_ADMISSION_RECOVERY_HISTORY")
            request_ids.add(request.request_id)
        if self.recoveries and self.owner_id != self.recoveries[-1].owner_id:
            raise ValueError("E_EPIC_ADMISSION_RECOVERY_HISTORY")
        if self.phase == "released" and not self.initialization_started:
            raise ValueError("E_EPIC_ADMISSION_RELEASE_UNCONFIRMED")
        return self


def admission_transition_allowed(prior: EpicRunAdmission, current: EpicRunAdmission) -> bool:
    if prior == current:
        return True
    if prior.phase != "active":
        return False
    if prior.initialization_started:
        return current == prior.model_copy(update={"phase": "released"})
    if current == prior.model_copy(update={"initialization_started": True}):
        return True
    return (current.phase == "active" and not current.initialization_started and current.owner_id != prior.owner_id
            and current.fencing_generation == prior.fencing_generation + 1
            and len(current.recoveries) == len(prior.recoveries) + 1 and current.recoveries[:-1] == prior.recoveries
            and current.model_copy(update={"owner_id": prior.owner_id, "fencing_generation": prior.fencing_generation,
                                           "recoveries": prior.recoveries}) == prior)


class EpicPublicationTransaction(Protocol):
    approval_pauses: EpicApprovalPauseTransaction
    export_dispatch: EpicExportDispatchTransaction

    async def get(self) -> EpicPublicationRecord | None: ...

    async def save(self, record: EpicPublicationRecord) -> None: ...

    async def get_preparation(self) -> EpicPreparationRecord | None: ...

    async def save_preparation(self, record: EpicPreparationRecord) -> None: ...

    async def get_outcome(self) -> EpicWorkloadOutcome | None: ...

    async def save_outcome(self, record: EpicWorkloadOutcome) -> None: ...

    async def get_admission(self) -> EpicRunAdmission | None: ...

    async def save_admission(self, record: EpicRunAdmission) -> None: ...

    async def admission_conflicts(self, resources: list[str]) -> list[str]: ...


class EpicPublicationRepository(Protocol):
    def transaction(self, session_id: str) -> AbstractAsyncContextManager[EpicPublicationTransaction]: ...
