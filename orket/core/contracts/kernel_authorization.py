"""Pure Kernel admission and approval identity checks over immutable values."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ApprovalIdentity:
    session_id: str
    proposal_digest: str
    decision_digest: str

    def __post_init__(self) -> None:
        if any(type(value) is not str for value in (self.session_id, self.proposal_digest, self.decision_digest)):
            raise ValueError("E_APPROVAL_IDENTITY_INVALID")


def admission_authorization_refusal(
    *,
    decision: str,
    expected: ApprovalIdentity,
    approval_status: str,
    observed: ApprovalIdentity | None,
) -> str:
    if decision not in {"ACCEPT_TO_UNIFY", "NEEDS_APPROVAL"}:
        return "REJECTED_POLICY"
    if decision == "NEEDS_APPROVAL" and (approval_status != "APPROVED" or observed != expected):
        return "REJECTED_APPROVAL_MISSING"
    return ""
