"""Application admission for loop strategy values; no borrowed runtime records."""
from __future__ import annotations

from types import MappingProxyType
from typing import Any

from orket.application.services.decision_context_service import capture_backlog_inputs
from orket.core.cards_runtime_contract import required_read_paths_for_seat, required_write_paths_for_seat
from orket.core.contracts.decision_inputs import (
    GuardReviewDecision,
    GuardReviewInput,
    NoCandidateOutcome,
    PlanningCardInput,
    SeatPolicyInput,
    validate_guard_review_input,
)
from orket.core.types import CardStatus
from orket.exceptions import ExecutionFailed


def capture_seat_policy_input(seat_name: str, issue: Any, turn_status: CardStatus) -> SeatPolicyInput:
    return SeatPolicyInput(seat_name=seat_name, issue=capture_backlog_inputs((issue,))[0] if issue else None,
        turn_status=turn_status,
        required_read_paths=tuple(required_read_paths_for_seat(seat_name=seat_name, issue=issue)),
        required_write_paths=tuple(required_write_paths_for_seat(seat_name=seat_name, issue=issue)))


def admit_policy_names(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)) or any(type(item) is not str for item in value):
        raise ExecutionFailed("E_LOOP_POLICY_INVALID_NAMES")
    return list(value)


def admit_policy_bool(value: Any) -> bool:
    if type(value) is not bool:
        raise ExecutionFailed("E_LOOP_POLICY_INVALID_BOOLEAN")
    return value


def recommend_no_candidate(node: Any, backlog: tuple[PlanningCardInput, ...]) -> NoCandidateOutcome:
    recommend = getattr(node, "no_candidate_outcome", None)
    payload = recommend(backlog) if callable(recommend) else {"is_done": node.is_backlog_done(backlog)}
    return NoCandidateOutcome.model_validate(payload)


def recommend_exhaustion(node: Any, iteration_count: int, max_iterations: int,
                         backlog: tuple[PlanningCardInput, ...]) -> bool:
    recommend = getattr(node, "should_raise_exhaustion", None)
    if callable(recommend):
        return admit_policy_bool(recommend(iteration_count, max_iterations, backlog))
    return not admit_policy_bool(node.is_backlog_done(backlog))


def validate_guard_review(node: Any, payload: Any):
    inputs = GuardReviewInput(rationale=payload.rationale, violations=tuple(payload.violations),
                              remediation_actions=tuple(payload.remediation_actions))
    validate = getattr(node, "validate_guard_rejection_payload", None)
    proposal = validate(inputs) if callable(validate) else validate_guard_review_input(inputs)
    return MappingProxyType(GuardReviewDecision.model_validate(proposal).model_dump())
