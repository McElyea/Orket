"""Application projection of retained approval state into the pure identity rule."""

from __future__ import annotations

from typing import Any

from orket.core.contracts.kernel_authorization import ApprovalIdentity, admission_authorization_refusal

from .nervous_system_approvals import get_approval


def authorization_refusal_for_admission(
    *,
    admission: dict[str, Any],
    session_id: str,
    proposal_digest: str,
    decision_digest: str,
    approval_id: str | None,
) -> str:
    decision = str((admission.get("admission_decision") or {}).get("decision") or "")
    approval = get_approval(approval_id) if decision == "NEEDS_APPROVAL" and approval_id else None
    observed = (
        None
        if approval is None
        else ApprovalIdentity(
            session_id=str(approval.get("session_id") or ""),
            proposal_digest=str(approval.get("proposal_digest") or ""),
            decision_digest=str(approval.get("admission_decision_digest") or ""),
        )
    )
    return admission_authorization_refusal(
        decision=decision,
        expected=ApprovalIdentity(session_id, proposal_digest, decision_digest),
        approval_status=str((approval or {}).get("status") or ""),
        observed=observed,
    )
