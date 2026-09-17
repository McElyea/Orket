"""Pure failure values; application services own timestamps and publication."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class PolicyViolationReport(BaseModel):
    """Structured artifact explaining a mechanical failure."""

    model_config = ConfigDict(frozen=True)

    timestamp: str
    session_id: str
    card_id: str
    violation_type: str  # "state_transition", "tool_gate", "structural", "timeout"
    detail: str
    attempted_action: dict[str, Any] | None = None
    remedy_suggestion: str
    active_roles: tuple[str, ...] = ()


class FailureReporter:
    """Construct a failure value from explicit inputs without effects."""

    @staticmethod
    def build_report(
        *,
        timestamp: str,
        session_id: str,
        card_id: str,
        violation: str,
        roles: tuple[str, ...] = (),
    ) -> PolicyViolationReport:
        # Determine violation type and remedy
        v_type = "governance"
        remedy = "Manual intervention required. Check the last turn in orket.log."

        if "transition" in violation.lower():
            v_type = "state_transition"
            remedy = "Review the state machine documentation. The requested status change is illegal."
        elif "tool" in violation.lower() or "gate" in violation.lower():
            v_type = "tool_gate"
            remedy = "The agent attempted a restricted tool call. Verify workspace permissions."
        elif "idesign" in violation.lower() or "structural" in violation.lower():
            v_type = "structural"
            remedy = "Structural violation detected. Review architecture governance settings and scope contracts."

        return PolicyViolationReport(
            timestamp=timestamp,
            session_id=session_id,
            card_id=card_id,
            violation_type=v_type,
            detail=violation,
            remedy_suggestion=remedy,
            active_roles=roles,
        )
