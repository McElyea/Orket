"""Capture small immutable configuration inputs before invoking strategy."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from orket.core.contracts.decision_inputs import (
    FailureEvaluationInput,
    FailureRecommendation,
    LoopPolicyInputs,
    PlanningCardInput,
    PlanningInput,
    RoutingInput,
    RoutingSeatInput,
    ScalarLimit,
    SuccessActions,
    SuccessRecommendation,
    SuccessTurnInput,
)
from orket.exceptions import ExecutionFailed


def _limit(value: Any) -> ScalarLimit:
    return value if isinstance(value, (str, int, float, bool)) else None


def capture_loop_policy_inputs(organization: Any, environment: Mapping[str, str]) -> LoopPolicyInputs:
    rules = getattr(organization, "process_rules", None)
    configured = rules.get("orchestrator_max_iterations") if isinstance(rules, dict) else None
    return LoopPolicyInputs(
        concurrency=_limit(environment.get("ORKET_ORCHESTRATOR_CONCURRENCY")),
        max_iterations=_limit(environment.get("ORKET_ORCHESTRATOR_MAX_ITERATIONS")),
        configured_max_iterations=_limit(configured),
        context_window=_limit(environment.get("ORKET_CONTEXT_WINDOW")),
    )


def capture_planning_inputs(backlog: Any, independent_ready: Any, target_issue_id: str | None) -> PlanningInput:
    """Project only declared card facts; arbitrary runtime params are not strategy context."""
    def capture(card: Any) -> PlanningCardInput:
        return PlanningCardInput(id=card.id, status=card.status, seat=getattr(card, "seat", ""),
            summary=getattr(card, "summary", None) or getattr(card, "name", None) or "",
            priority=getattr(card, "priority", 2.0), depends_on=tuple(getattr(card, "depends_on", ())))

    return PlanningInput(backlog=tuple(capture(card) for card in backlog),
                         independent_ready=tuple(capture(card) for card in independent_ready),
                         target_issue_id=target_issue_id)


def capture_routing_input(issue: Any, team: Any, is_review_turn: bool) -> RoutingInput:
    return RoutingInput(issue_id=issue.id, issue_seat=issue.seat, is_review_turn=is_review_turn,
                        seats=tuple(RoutingSeatInput(name=name, roles=tuple(seat.roles))
                                    for name, seat in team.seats.items()))


def recommend_routing_seat(router: Any, issue: Any, team: Any, is_review_turn: bool) -> str:
    selected = router.route(capture_routing_input(issue, team, is_review_turn))
    if type(selected) is not str:
        raise ExecutionFailed("E_CARD_ROUTING_INVALID_RECOMMENDATION")
    return selected


def capture_failure_evaluation(issue: Any, result: Any) -> FailureEvaluationInput:
    return FailureEvaluationInput(issue_id=issue.id, retry_count=issue.retry_count, max_retries=issue.max_retries,
        error=getattr(result, "error", None), violations=tuple(getattr(result, "violations", ()) or ()))


def capture_success_turn(issue: Any, turn: Any, seat_name: str, is_review_turn: bool) -> SuccessTurnInput:
    return SuccessTurnInput(issue_id=issue.id, issue_status=issue.status, content=turn.content or "",
                            seat_name=seat_name, is_review_turn=is_review_turn)


def admit_failure_recommendation(payload: Mapping[str, Any], inputs: FailureEvaluationInput) -> FailureRecommendation:
    return FailureRecommendation.model_validate({"next_retry_count": inputs.retry_count, **payload})


def admit_success_recommendation(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(SuccessRecommendation.model_validate(payload).model_dump())


def admit_success_actions(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(SuccessActions.model_validate(payload).model_dump())
