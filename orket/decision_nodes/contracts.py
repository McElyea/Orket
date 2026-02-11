from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Protocol


@dataclass
class PlanningInput:
    """Stable contract payload for planner decision nodes."""
    backlog: List[Any]
    independent_ready: List[Any]
    target_issue_id: str | None = None


class PlannerNode(Protocol):
    """Decision node: determines which issues are candidates this tick."""

    def plan(self, data: PlanningInput) -> List[Any]:
        ...


class RouterNode(Protocol):
    """Decision node: determines which seat should execute an issue."""

    def route(self, issue: Any, team: Any, is_review_turn: bool) -> str:
        ...


class EvaluatorNode(Protocol):
    """Decision node: evaluates issue outcomes and quality signals."""

    def evaluate_success(
        self,
        issue: Any,
        updated_issue: Any,
        turn: Any,
        seat_name: str,
        is_review_turn: bool,
    ) -> Any:
        ...

    def evaluate_failure(self, issue: Any, result: Any) -> Any:
        ...


class PromptStrategyNode(Protocol):
    """Decision node: chooses model and dialect strategy for a turn."""

    def select_model(self, role: str, asset_config: Any) -> str:
        ...

    def select_dialect(self, model: str) -> str:
        ...
