from __future__ import annotations

from typing import Any, Dict

from orket.decision_nodes.builtins import (
    DefaultEvaluatorNode,
    DefaultPlannerNode,
    DefaultPromptStrategyNode,
    DefaultRouterNode,
)
from orket.decision_nodes.contracts import EvaluatorNode, PlannerNode, PromptStrategyNode, RouterNode


class DecisionNodeRegistry:
    """
    Minimal plugin registry for decision node implementations.
    """

    def __init__(self):
        self._planner_nodes: Dict[str, PlannerNode] = {"default": DefaultPlannerNode()}
        self._router_nodes: Dict[str, RouterNode] = {"default": DefaultRouterNode()}
        self._prompt_strategy_nodes: Dict[str, PromptStrategyNode] = {}
        self._evaluator_nodes: Dict[str, EvaluatorNode] = {"default": DefaultEvaluatorNode()}

    def register_planner(self, name: str, node: PlannerNode) -> None:
        self._planner_nodes[name] = node

    def register_router(self, name: str, node: RouterNode) -> None:
        self._router_nodes[name] = node

    def register_prompt_strategy(self, name: str, node: PromptStrategyNode) -> None:
        self._prompt_strategy_nodes[name] = node

    def register_evaluator(self, name: str, node: EvaluatorNode) -> None:
        self._evaluator_nodes[name] = node

    def resolve_planner(self, organization: Any = None) -> PlannerNode:
        planner_name = "default"
        if organization and getattr(organization, "process_rules", None):
            planner_name = organization.process_rules.get("planner_node", "default")
        return self._planner_nodes.get(planner_name, self._planner_nodes["default"])

    def resolve_router(self, organization: Any = None) -> RouterNode:
        router_name = "default"
        if organization and getattr(organization, "process_rules", None):
            router_name = organization.process_rules.get("router_node", "default")
        return self._router_nodes.get(router_name, self._router_nodes["default"])

    def resolve_prompt_strategy(self, model_selector: Any, organization: Any = None) -> PromptStrategyNode:
        prompt_name = "default"
        if organization and getattr(organization, "process_rules", None):
            prompt_name = organization.process_rules.get("prompt_strategy_node", "default")
        if prompt_name == "default":
            return DefaultPromptStrategyNode(model_selector)
        return self._prompt_strategy_nodes.get(prompt_name, DefaultPromptStrategyNode(model_selector))

    def resolve_evaluator(self, organization: Any = None) -> EvaluatorNode:
        evaluator_name = "default"
        if organization and getattr(organization, "process_rules", None):
            evaluator_name = organization.process_rules.get("evaluator_node", "default")
        return self._evaluator_nodes.get(evaluator_name, self._evaluator_nodes["default"])
