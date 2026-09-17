"""Explicit local ownership and recovery inputs for a consumed approval pause."""
from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import TYPE_CHECKING, Literal, Protocol

from pydantic import Field, model_validator

from orket.core.contracts.control_plane_models import OperatorActionRecord
from orket.core.contracts.epic_publication import EpicRetainedRecord
from orket.core.domain.control_plane_enums import OperatorCommandClass, OperatorInputClass
from orket.core.domain.outward_authorization import args_hash

EPIC_CONTINUATION_LOCK_ARTIFACT = "epic_continuation_lock"
EPIC_APPROVAL_RECOVERY_ARTIFACT = "epic_approval_recoveries"

if TYPE_CHECKING:
    from orket.core.contracts.epic_approval_pause import EpicApprovalPause


class EpicContinuationLockRef(EpicRetainedRecord):
    schema_version: Literal["epic_continuation_lock.v1"] = "epic_continuation_lock.v1"
    session_id: str = Field(min_length=1)
    journal_path: str = Field(min_length=1)
    lock_path: str = Field(min_length=1)
    device: int = Field(ge=0, strict=True)
    inode: int = Field(gt=0, strict=True)


class EpicApprovalRecoveryRequest(EpicRetainedRecord):
    schema_version: Literal["epic_approval_recovery_request.v1"] = "epic_approval_recovery_request.v1"
    session_id: str = Field(min_length=1)
    sequence: int = Field(ge=1, strict=True)
    request_id: str = Field(min_length=1)
    expected_pause_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_recovery_digest: str | None = Field(pattern=r"^[0-9a-f]{64}$")
    operator_ref: str = Field(min_length=1)
    reason_ref: str = Field(min_length=1)
    resolution: Literal["continue_resolved_pause"]


class EpicApprovalRecovery(EpicRetainedRecord):
    schema_version: Literal["epic_approval_recovery.v1"] = "epic_approval_recovery.v1"
    ordinal: int = Field(ge=1, strict=True)
    request: EpicApprovalRecoveryRequest
    lock: EpicContinuationLockRef
    decided_at: str = Field(min_length=1)
    action: OperatorActionRecord

    def reference(self) -> dict[str, str | int]:
        return {"schema_version": self.schema_version, "session_id": self.request.session_id,
                "sequence": self.request.sequence, "request_id": self.request.request_id, "digest": self.digest()}

    @model_validator(mode="after")
    def _binding(self) -> EpicApprovalRecovery:
        if (self.request.session_id != self.lock.session_id
                or (self.ordinal == 1) != (self.request.expected_recovery_digest is None)
                or self.action != approval_recovery_action(self.request, self.lock, self.decided_at)):
            raise ValueError("E_EPIC_APPROVAL_RECOVERY_RECORD_CONFLICT")
        return self


def approval_recovery_action(request: EpicApprovalRecoveryRequest, lock: EpicContinuationLockRef,
                             at: str) -> OperatorActionRecord:
    prior = (["approval-recovery:sha256:" + request.expected_recovery_digest]
             if request.expected_recovery_digest else [])
    return OperatorActionRecord(
        action_id="epic-approval-recovery:" + args_hash({"session": request.session_id, "request": request.request_id}),
        actor_ref=request.operator_ref, input_class=OperatorInputClass.COMMAND,
        command_class=OperatorCommandClass.FORCE_RECONCILE,
        target_ref=f"epic-approval:{request.session_id}:{request.sequence}", timestamp=at,
        precondition_basis_ref="request:sha256:" + request.digest(), result="approval_continuation_granted",
        affected_transition_refs=["approval-pause:sha256:" + request.expected_pause_digest, *prior],
        receipt_refs=["continuation-lock:sha256:" + lock.digest()],
    )


def approval_claim_transition_allowed(prior: EpicApprovalPause, current: EpicApprovalPause) -> bool:
    if prior.phase != "waiting" or current.phase != "claimed":
        return False
    artifacts = dict(current.artifacts)
    marker = artifacts.get(EPIC_CONTINUATION_LOCK_ARTIFACT)
    if marker is not None:
        reference = EpicContinuationLockRef.model_validate(marker)
        if reference.session_id != current.session_id:
            return False
        if EPIC_CONTINUATION_LOCK_ARTIFACT not in prior.artifacts:
            artifacts.pop(EPIC_CONTINUATION_LOCK_ARTIFACT)
    return current.model_copy(update={"phase": "waiting", "decisions": {}, "artifacts": artifacts}) == prior


class EpicContinuationLockProvider(Protocol):
    def hold(self, session_id: str, *, expected: EpicContinuationLockRef | None = None
             ) -> AbstractAsyncContextManager[EpicContinuationLockRef]: ...
