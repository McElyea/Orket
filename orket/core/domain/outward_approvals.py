from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from orket.core.domain.outward_authorization import OutwardAuthorization


@dataclass(frozen=True)
class OutwardApprovalProposal:
    proposal_id: str
    run_id: str
    namespace: str
    tool: str
    args_preview: dict[str, Any]
    context_summary: str
    risk_level: str
    submitted_at: str
    expires_at: str
    status: str = "pending"
    operator_ref: str | None = None
    decision: str | None = None
    reason: str | None = None
    note: str | None = None
    decided_at: str | None = None
    authorization_json: str | None = None
    authorization_digest: str | None = None

    @property
    def authorization(self) -> OutwardAuthorization | None:
        if self.authorization_json is None:
            if self.authorization_digest is not None:
                raise ValueError("E_OUTWARD_AUTHORIZATION_INCOMPLETE")
            return None
        binding = OutwardAuthorization.from_json(self.authorization_json, self.authorization_digest or "")
        if (binding.proposal_id, binding.run_id, binding.namespace, binding.tool, binding.submitted_at, binding.expires_at) != (
            self.proposal_id, self.run_id, self.namespace, self.tool, self.submitted_at, self.expires_at,
        ):
            raise ValueError("E_OUTWARD_AUTHORIZATION_PROPOSAL_MISMATCH")
        return binding

    def to_queue_payload(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "run_id": self.run_id,
            "namespace": self.namespace,
            "tool": self.tool,
            "args_preview": dict(self.args_preview),
            "context_summary": self.context_summary,
            "risk_level": self.risk_level,
            "submitted_at": self.submitted_at,
            "expires_at": self.expires_at,
            "status": self.status,
        }

    def to_decision_payload(self) -> dict[str, Any]:
        return {
            **self.to_queue_payload(),
            "operator_ref": self.operator_ref,
            "decision": self.decision,
            "reason": self.reason,
            "note": self.note,
            "decided_at": self.decided_at,
        }


__all__ = ["OutwardApprovalProposal"]
