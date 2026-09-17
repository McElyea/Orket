"""Retained unfinished epic execution at an admitted tool approval boundary."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, Protocol

from pydantic import Field, model_validator

from orket.core.contracts.epic_publication import EpicRetainedRecord

if TYPE_CHECKING:
    from orket.core.contracts.epic_approval_recovery import EpicApprovalRecovery

EPIC_APPROVAL_DENIED = "Epic stopped after tool approval was denied."


class EpicApprovalPause(EpicRetainedRecord):
    schema_version: Literal["epic_approval_pause.v1"] = "epic_approval_pause.v1"
    session_id: str = Field(min_length=1)
    sequence: int = Field(ge=1, strict=True)
    epic_asset: str = Field(min_length=1)
    model_override: str
    request: dict[str, Any]
    export_binding: dict[str, Any]
    artifacts: dict[str, Any]
    transcript: list[dict[str, Any]]
    approvals: dict[str, dict[str, Any]] = Field(min_length=1)
    phase: Literal["waiting", "claimed"] = "waiting"
    decisions: dict[str, Literal["approved", "denied"]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _decision_binding(self) -> EpicApprovalPause:
        if self.phase == "waiting" and self.decisions:
            raise ValueError("E_EPIC_APPROVAL_PREMATURE_DECISION")
        if self.phase == "claimed" and self.decisions.keys() != self.approvals.keys():
            raise ValueError("E_EPIC_APPROVAL_DECISION_MISSING")
        return self


class EpicApprovalPauseTransaction(Protocol):
    async def latest(self) -> EpicApprovalPause | None: ...

    async def save(self, record: EpicApprovalPause) -> None: ...

    async def recoveries(self) -> list[EpicApprovalRecovery]: ...

    async def save_recovery(self, record: EpicApprovalRecovery) -> None: ...
