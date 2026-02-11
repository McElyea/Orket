from __future__ import annotations

from typing import Any, List

from orket.decision_nodes.contracts import PlanningInput
from orket.schema import CardStatus


class DefaultPlannerNode:
    """
    Built-in planner decision node.
    Preserves existing orchestration candidate behavior.
    """

    def plan(self, data: PlanningInput) -> List[Any]:
        backlog = data.backlog
        independent_ready = data.independent_ready
        target_issue_id = data.target_issue_id

        in_review = [i for i in backlog if i.status == CardStatus.CODE_REVIEW]

        if target_issue_id:
            target = next((i for i in backlog if i.id == target_issue_id), None)
            if not target:
                return []
            if target.status == CardStatus.CODE_REVIEW:
                return [target]
            if target.status == CardStatus.READY and any(i.id == target_issue_id for i in independent_ready):
                return [target]
            return []

        return in_review + independent_ready
