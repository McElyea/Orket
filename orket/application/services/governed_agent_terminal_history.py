"""Interpret one retained history snapshot before exposing terminal authority."""
from __future__ import annotations

from pydantic import ValidationError

from orket.core.contracts import AttemptRecord, FinalTruthRecord, RunRecord
from orket.core.contracts.governed_agent_replay import GovernedAgentReplayEvidence
from orket.core.domain.control_plane_final_truth import (
    ControlPlaneFinalTruthError,
    validate_terminal_record_consistency,
)


class GovernedAgentTerminalHistoryConflict(ValueError):
    """Retained records cannot support a coherent terminal observation."""


def agent_terminal_history_records(
    evidence: GovernedAgentReplayEvidence,
) -> tuple[RunRecord | None, list[AttemptRecord], FinalTruthRecord | None]:
    if evidence.diagnostics:
        raise GovernedAgentTerminalHistoryConflict('E_AGENT_TERMINAL_AUTHORITY_CONFLICT:history_unreadable')
    if evidence.run is None:
        return None, [], None
    try:
        run = RunRecord.model_validate(evidence.run)
        attempts = [AttemptRecord.model_validate(item) for item in evidence.attempts]
        truth = FinalTruthRecord.model_validate(evidence.final_truth) if evidence.final_truth is not None else None
        attempt = next((item for item in attempts if item.attempt_id == run.current_attempt_id), None)
        validate_terminal_record_consistency(run, attempt, truth)
    except (ValidationError, ControlPlaneFinalTruthError) as exc:
        raise GovernedAgentTerminalHistoryConflict('E_AGENT_TERMINAL_AUTHORITY_CONFLICT:records') from exc
    return run, attempts, truth
