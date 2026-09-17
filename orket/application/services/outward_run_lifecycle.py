from __future__ import annotations

from dataclasses import replace
from typing import Any

from orket.application.services.outward_run_execution_plan import proposal_suffix, step_event_id
from orket.core.domain import ResultClass
from orket.core.domain.outward_run_events import LedgerEvent
from orket.core.domain.outward_runs import OutwardRunRecord


def terminal_projection(outcome: str) -> tuple[str, ResultClass]:
    if outcome == "success":
        return "completed", ResultClass.SUCCESS
    if outcome == "failed":
        return "failed", ResultClass.FAILED
    if outcome in {"denied", "expired", "policy_rejected", "handoff_rejected"}:
        return "failed" if outcome == "expired" else "completed", ResultClass.BLOCKED
    raise ValueError("E_OUTWARD_TERMINAL_OUTCOME_UNSUPPORTED")


def run_event(run: OutwardRunRecord, *, event_id: str, event_type: str, at: str, payload: dict[str, Any]) -> LedgerEvent:
    return LedgerEvent(
        event_id=event_id, event_type=event_type, run_id=run.run_id, turn=run.current_turn,
        agent_id="outward-agent", at=at, payload=payload,
    )


def turn_completion_events(
    run: OutwardRunRecord, tool: str, proposal_id: str, *, at: str, outcome: str, record_commitment: bool = True,
) -> list[LedgerEvent]:
    events = []
    if record_commitment:
        events.append(run_event(
            run, event_id=step_event_id(run.run_id, run.current_turn, 500, f"commitment:{tool}:{proposal_suffix(proposal_id)}"),
            event_type="commitment_recorded", at=at, payload={"run_id": run.run_id, "tool": tool, "outcome": outcome},
        ))
    events.append(run_event(
        run, event_id=step_event_id(run.run_id, run.current_turn, 600, "turn:completed"),
        event_type="turn_completed", at=at, payload={"run_id": run.run_id, "turn": run.current_turn, "outcome": outcome},
    ))
    return events


def terminal_transition(
    run: OutwardRunRecord, *, at: str, status: str, reason: str | None, outcome: str,
) -> tuple[OutwardRunRecord, LedgerEvent]:
    terminal = replace(run, status=status, pending_proposals=(), completed_at=at, stop_reason=reason)
    failed = status == "failed"
    return terminal, run_event(
        terminal, event_id=f"run:{run.run_id}:0900:failed" if failed else f"run:{run.run_id}:0700:completed",
        event_type="run_failed" if failed else "run_completed", at=at,
        payload={"run_id": run.run_id, "status": status, "completed_at": at,
                 **({"reason": reason} if failed else {"outcome": outcome})},
    )


def turn_started_event(run: OutwardRunRecord, *, at: str) -> LedgerEvent:
    return run_event(
        run, event_id=step_event_id(run.run_id, run.current_turn, 200, "turn:started"),
        event_type="turn_started", at=at,
        payload={"run_id": run.run_id, "turn": run.current_turn, "agent_id": "outward-agent"},
    )
