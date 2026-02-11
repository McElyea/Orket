from __future__ import annotations

from typing import Any, Dict

from orket.decision_nodes.builtins import (
    DefaultApiRuntimeStrategyNode,
    DefaultEngineRuntimePolicyNode,
    DefaultEvaluatorNode,
    DefaultPlannerNode,
    DefaultPromptStrategyNode,
    DefaultRouterNode,
    DefaultSandboxPolicyNode,
    DefaultToolStrategyNode,
)
from orket.decision_nodes.contracts import (
    EvaluatorNode,
    EngineRuntimePolicyNode,
    PlannerNode,
    PromptStrategyNode,
    RouterNode,
    ApiRuntimeStrategyNode,
    SandboxPolicyNode,
    ToolStrategyNode,
)
from orket.settings import get_setting


class DecisionNodeRegistry:
    """
    Minimal plugin registry for decision node implementations.
    """

    def __init__(self):
        self._planner_nodes: Dict[str, PlannerNode] = {"default": DefaultPlannerNode()}
        self._router_nodes: Dict[str, RouterNode] = {"default": DefaultRouterNode()}
        self._prompt_strategy_nodes: Dict[str, PromptStrategyNode] = {}
        self._evaluator_nodes: Dict[str, EvaluatorNode] = {"default": DefaultEvaluatorNode()}
        self._tool_strategy_nodes: Dict[str, ToolStrategyNode] = {"default": DefaultToolStrategyNode()}
        self._api_runtime_nodes: Dict[str, ApiRuntimeStrategyNode] = {
            "default": DefaultApiRuntimeStrategyNode()
        }
        self._sandbox_policy_nodes: Dict[str, SandboxPolicyNode] = {
            "default": DefaultSandboxPolicyNode()
        }
        self._engine_runtime_nodes: Dict[str, EngineRuntimePolicyNode] = {
            "default": DefaultEngineRuntimePolicyNode()
        }

    def register_planner(self, name: str, node: PlannerNode) -> None:
        self._planner_nodes[name] = node

    def register_router(self, name: str, node: RouterNode) -> None:
        self._router_nodes[name] = node

    def register_prompt_strategy(self, name: str, node: PromptStrategyNode) -> None:
        self._prompt_strategy_nodes[name] = node

    def register_evaluator(self, name: str, node: EvaluatorNode) -> None:
        self._evaluator_nodes[name] = node

    def register_tool_strategy(self, name: str, node: ToolStrategyNode) -> None:
        self._tool_strategy_nodes[name] = node

    def register_api_runtime(self, name: str, node: ApiRuntimeStrategyNode) -> None:
        self._api_runtime_nodes[name] = node

    def register_sandbox_policy(self, name: str, node: SandboxPolicyNode) -> None:
        self._sandbox_policy_nodes[name] = node

    def register_engine_runtime(self, name: str, node: EngineRuntimePolicyNode) -> None:
        self._engine_runtime_nodes[name] = node

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

    def resolve_tool_strategy(self, organization: Any = None) -> ToolStrategyNode:
        tool_strategy_name = "default"
        if organization and getattr(organization, "process_rules", None):
            tool_strategy_name = organization.process_rules.get("tool_strategy_node", "default")

        env_override = get_setting("ORKET_TOOL_STRATEGY_NODE")
        if isinstance(env_override, str) and env_override.strip():
            tool_strategy_name = env_override.strip()

        return self._tool_strategy_nodes.get(tool_strategy_name, self._tool_strategy_nodes["default"])

    def resolve_api_runtime(self, organization: Any = None) -> ApiRuntimeStrategyNode:
        api_runtime_name = "default"
        if organization and getattr(organization, "process_rules", None):
            api_runtime_name = organization.process_rules.get("api_runtime_node", "default")

        env_override = get_setting("ORKET_API_RUNTIME_NODE")
        if isinstance(env_override, str) and env_override.strip():
            api_runtime_name = env_override.strip()

        return self._api_runtime_nodes.get(api_runtime_name, self._api_runtime_nodes["default"])

    def resolve_sandbox_policy(self, organization: Any = None) -> SandboxPolicyNode:
        sandbox_policy_name = "default"
        if organization and getattr(organization, "process_rules", None):
            sandbox_policy_name = organization.process_rules.get("sandbox_policy_node", "default")

        env_override = get_setting("ORKET_SANDBOX_POLICY_NODE")
        if isinstance(env_override, str) and env_override.strip():
            sandbox_policy_name = env_override.strip()

        return self._sandbox_policy_nodes.get(sandbox_policy_name, self._sandbox_policy_nodes["default"])

    def resolve_engine_runtime(self, organization: Any = None) -> EngineRuntimePolicyNode:
        engine_runtime_name = "default"
        if organization and getattr(organization, "process_rules", None):
            engine_runtime_name = organization.process_rules.get("engine_runtime_node", "default")

        env_override = get_setting("ORKET_ENGINE_RUNTIME_NODE")
        if isinstance(env_override, str) and env_override.strip():
            engine_runtime_name = env_override.strip()

        return self._engine_runtime_nodes.get(engine_runtime_name, self._engine_runtime_nodes["default"])
