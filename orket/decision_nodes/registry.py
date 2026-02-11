from __future__ import annotations

from typing import Any, Dict

from orket.decision_nodes.builtins import DefaultPlannerNode
from orket.decision_nodes.contracts import PlannerNode


class DecisionNodeRegistry:
    """
    Minimal plugin registry for decision node implementations.
    """

    def __init__(self):
        self._planner_nodes: Dict[str, PlannerNode] = {"default": DefaultPlannerNode()}

    def register_planner(self, name: str, node: PlannerNode) -> None:
        self._planner_nodes[name] = node

    def resolve_planner(self, organization: Any = None) -> PlannerNode:
        planner_name = "default"
        if organization and getattr(organization, "process_rules", None):
            planner_name = organization.process_rules.get("planner_node", "default")
        return self._planner_nodes.get(planner_name, self._planner_nodes["default"])
