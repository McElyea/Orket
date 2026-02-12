"""
Failure Reporter - Phase 3: Elegant Failure & Recovery

Generates high-fidelity reports when the engine hits a governance or state boundary.
Reconstructed for async native I/O and specific policy violation details.
"""
from __future__ import annotations
import json
import aiofiles
from pathlib import Path
from datetime import datetime, UTC
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from orket.logging import log_event


class PolicyViolationReport(BaseModel):
    """Structured artifact explaining a mechanical failure."""
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    session_id: str
    card_id: str
    violation_type: str  # "state_transition", "tool_gate", "idesign", "timeout"
    detail: str
    attempted_action: Optional[Dict[str, Any]] = None
    remedy_suggestion: str
    active_roles: List[str] = Field(default_factory=list)


class FailureReporter:
    """
    Service responsible for generating troubleshooting artifacts.
    """
    
    @staticmethod
    async def generate_report(
        workspace: Path, 
        session_id: str, 
        card_id: str, 
        violation: str, 
        transcript: List[Any],
        roles: List[str] = None
    ) -> Path:
        """
        Generates a JSON report for a failure.
        """
        # Determine violation type and remedy
        v_type = "governance"
        remedy = "Manual intervention required. Check the last turn in orket.log."
        
        if "transition" in violation.lower():
            v_type = "state_transition"
            remedy = "Review the state machine documentation. The requested status change is illegal."
        elif "tool" in violation.lower() or "gate" in violation.lower():
            v_type = "tool_gate"
            remedy = "The agent attempted a restricted tool call. Verify workspace permissions."
        elif "idesign" in violation.lower():
            v_type = "idesign"
            remedy = "Structural violation detected. Ensure the '7 issue' iDesign rule is being followed."

        report = PolicyViolationReport(
            session_id=session_id,
            card_id=card_id,
            violation_type=v_type,
            detail=violation,
            remedy_suggestion=remedy,
            active_roles=roles or []
        )
        
        from orket.domain.verification import AGENT_OUTPUT_DIR
        report_dir = workspace / AGENT_OUTPUT_DIR
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"policy_violation_{card_id}.json"
        
        async with aiofiles.open(report_path, "w", encoding="utf-8") as f:
            await f.write(report.model_dump_json(indent=4))

        log_event(
            "policy_violation_report_saved",
            {"session_id": session_id, "card_id": card_id, "path": str(report_path)},
            workspace,
        )
        return report_path
