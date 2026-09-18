from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from orket.decision_nodes.api_runtime_strategy_node import DefaultApiRuntimeStrategyNode
from orket.decision_nodes.builtins import (
    DefaultEvaluatorNode,
    DefaultExecutionRuntimeStrategyNode,
    DefaultLoaderStrategyNode,
    DefaultOrchestrationLoopPolicyNode,
    DefaultPlannerNode,
    DefaultPromptStrategyNode,
    DefaultRouterNode,
    DefaultSandboxPolicyNode,
    DefaultToolStrategyNode,
)
from orket.decision_nodes.contracts import (
    ApiRuntimeStrategyNode,
    EvaluatorNode,
    ExecutionRuntimeStrategyNode,
    LoaderStrategyNode,
    OrchestrationLoopPolicyNode,
    PlannerNode,
    PromptStrategyNode,
    RouterNode,
    SandboxPolicyNode,
    ToolStrategyNode,
)


class DecisionNodeRegistry:
    """
    Minimal plugin registry for decision node implementations.
    """

    def __init__(self, *, settings: Mapping[str, Any] | None = None) -> None:
        self._settings = MappingProxyType(dict(settings or {}))
        if self._settings.get("ORKET_MODEL_CLIENT_NODE"):
            raise ValueError("ORKET_MODEL_CLIENT_NODE is retired; configure an application model-client factory.")
        self._planner_nodes: dict[str, PlannerNode] = {"default": DefaultPlannerNode()}
        self._router_nodes: dict[str, RouterNode] = {"default": DefaultRouterNode()}
        self._prompt_strategy_nodes: dict[str, PromptStrategyNode] = {}
        self._evaluator_nodes: dict[str, EvaluatorNode] = {"default": DefaultEvaluatorNode()}
        self._tool_strategy_nodes: dict[str, ToolStrategyNode] = {"default": DefaultToolStrategyNode()}
        self._api_runtime_nodes: dict[str, ApiRuntimeStrategyNode] = {"default": DefaultApiRuntimeStrategyNode()}
        self._sandbox_policy_nodes: dict[str, SandboxPolicyNode] = {"default": DefaultSandboxPolicyNode()}
        self._loader_strategy_nodes: dict[str, LoaderStrategyNode] = {"default": DefaultLoaderStrategyNode()}
        self._execution_runtime_nodes: dict[str, ExecutionRuntimeStrategyNode] = {
            "default": DefaultExecutionRuntimeStrategyNode()
        }
        self._orchestration_loop_nodes: dict[str, OrchestrationLoopPolicyNode] = {
            "default": DefaultOrchestrationLoopPolicyNode()
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

    def register_loader_strategy(self, name: str, node: LoaderStrategyNode) -> None:
        self._loader_strategy_nodes[name] = node

    def register_execution_runtime(self, name: str, node: ExecutionRuntimeStrategyNode) -> None:
        self._execution_runtime_nodes[name] = node

    def register_orchestration_loop(self, name: str, node: OrchestrationLoopPolicyNode) -> None:
        self._orchestration_loop_nodes[name] = node

    def register_module_nodes(self, module_id: str, registrations: dict[str, Any]) -> None:
        """
        Register a module-provided set of decision nodes using explicit keys.
        Supported keys:
        planner, router, prompt_strategy, evaluator, tool_strategy, api_runtime,
        sandbox_policy, loader_strategy, execution_runtime, orchestration_loop.
        """
        key = str(module_id or "").strip()
        if not key:
            raise ValueError("module_id is required for module node registration")
        if not isinstance(registrations, dict):
            raise TypeError("registrations must be a mapping")

        for node_type, node in registrations.items():
            slot = str(node_type or "").strip().lower()
            if slot == "planner":
                self.register_planner(key, node)
            elif slot == "router":
                self.register_router(key, node)
            elif slot == "prompt_strategy":
                self.register_prompt_strategy(key, node)
            elif slot == "evaluator":
                self.register_evaluator(key, node)
            elif slot == "tool_strategy":
                self.register_tool_strategy(key, node)
            elif slot == "api_runtime":
                self.register_api_runtime(key, node)
            elif slot == "sandbox_policy":
                self.register_sandbox_policy(key, node)
            elif slot == "loader_strategy":
                self.register_loader_strategy(key, node)
            elif slot == "execution_runtime":
                self.register_execution_runtime(key, node)
            elif slot == "orchestration_loop":
                self.register_orchestration_loop(key, node)
            else:
                raise ValueError(f"Unsupported decision node registration type '{node_type}'")

    def resolve_planner(self, organization: Any = None) -> PlannerNode:
        planner_name = "default"
        rules = _process_rules(organization)
        if rules:
            planner_name = rules.get("planner_node", "default")
        return self._planner_nodes.get(planner_name, self._planner_nodes["default"])

    def resolve_router(self, organization: Any = None) -> RouterNode:
        router_name = "default"
        rules = _process_rules(organization)
        if rules:
            router_name = rules.get("router_node", "default")
        return self._router_nodes.get(router_name, self._router_nodes["default"])

    def resolve_prompt_strategy(self, model_selector: Any, organization: Any = None) -> PromptStrategyNode:
        prompt_name = "default"
        rules = _process_rules(organization)
        if rules:
            prompt_name = rules.get("prompt_strategy_node", "default")
        if prompt_name == "default":
            return DefaultPromptStrategyNode(model_selector)
        return self._prompt_strategy_nodes.get(prompt_name, DefaultPromptStrategyNode(model_selector))

    def resolve_evaluator(self, organization: Any = None) -> EvaluatorNode:
        evaluator_name = "default"
        rules = _process_rules(organization)
        if rules:
            evaluator_name = rules.get("evaluator_node", "default")
        return self._evaluator_nodes.get(evaluator_name, self._evaluator_nodes["default"])

    def resolve_tool_strategy(self, organization: Any = None) -> ToolStrategyNode:
        tool_strategy_name = "default"
        rules = _process_rules(organization)
        if rules:
            tool_strategy_name = rules.get("tool_strategy_node", "default")

        env_override = self._settings.get("ORKET_TOOL_STRATEGY_NODE")
        if isinstance(env_override, str) and env_override.strip():
            tool_strategy_name = env_override.strip()

        return self._tool_strategy_nodes.get(tool_strategy_name, self._tool_strategy_nodes["default"])

    def resolve_api_runtime(self, organization: Any = None) -> ApiRuntimeStrategyNode:
        api_runtime_name = "default"
        rules = _process_rules(organization)
        if rules:
            api_runtime_name = rules.get("api_runtime_node", "default")

        env_override = self._settings.get("ORKET_API_RUNTIME_NODE")
        if isinstance(env_override, str) and env_override.strip():
            api_runtime_name = env_override.strip()

        return self._api_runtime_nodes.get(api_runtime_name, self._api_runtime_nodes["default"])

    def resolve_sandbox_policy(self, organization: Any = None) -> SandboxPolicyNode:
        sandbox_policy_name = "default"
        rules = _process_rules(organization)
        if rules:
            sandbox_policy_name = rules.get("sandbox_policy_node", "default")

        env_override = self._settings.get("ORKET_SANDBOX_POLICY_NODE")
        if isinstance(env_override, str) and env_override.strip():
            sandbox_policy_name = env_override.strip()

        return self._sandbox_policy_nodes.get(sandbox_policy_name, self._sandbox_policy_nodes["default"])

    def resolve_loader_strategy(self, organization: Any = None) -> LoaderStrategyNode:
        loader_strategy_name = "default"
        rules = _process_rules(organization)
        if rules:
            loader_strategy_name = rules.get("loader_strategy_node", "default")

        env_override = self._settings.get("ORKET_LOADER_STRATEGY_NODE")
        if isinstance(env_override, str) and env_override.strip():
            loader_strategy_name = env_override.strip()

        return self._loader_strategy_nodes.get(loader_strategy_name, self._loader_strategy_nodes["default"])

    def resolve_execution_runtime(self, organization: Any = None) -> ExecutionRuntimeStrategyNode:
        execution_runtime_name = "default"
        rules = _process_rules(organization)
        if rules:
            execution_runtime_name = rules.get("execution_runtime_node", "default")

        env_override = self._settings.get("ORKET_EXECUTION_RUNTIME_NODE")
        if isinstance(env_override, str) and env_override.strip():
            execution_runtime_name = env_override.strip()

        return self._execution_runtime_nodes.get(
            execution_runtime_name,
            self._execution_runtime_nodes["default"],
        )

    def resolve_orchestration_loop(self, organization: Any = None) -> OrchestrationLoopPolicyNode:
        loop_policy_name = "default"
        rules = _process_rules(organization)
        if rules:
            loop_policy_name = rules.get("orchestration_loop_node", "default")

        env_override = self._settings.get("ORKET_ORCHESTRATION_LOOP_NODE")
        if isinstance(env_override, str) and env_override.strip():
            loop_policy_name = env_override.strip()

        return self._orchestration_loop_nodes.get(
            loop_policy_name,
            self._orchestration_loop_nodes["default"],
        )


def _process_rules(organization: Any) -> Mapping[str, Any]:
    rules = getattr(organization, "process_rules", None) or {}
    if "model_client_node" in rules:
        raise ValueError("model_client_node is retired; configure an application model-client factory.")
    return rules


def build_decision_node_registry(*, environment: Mapping[str, str] | None = None) -> DecisionNodeRegistry:
    """Composition boundary: capture settings once; strategies never observe this source."""
    import os

    from orket.settings import load_user_settings

    captured = dict(os.environ if environment is None else environment)
    if captured.get("ORKET_MODEL_CLIENT_NODE"):
        raise ValueError("ORKET_MODEL_CLIENT_NODE is retired; configure an application model-client factory.")
    stored = load_user_settings()
    if stored.get("ORKET_MODEL_CLIENT_NODE"):
        raise ValueError("ORKET_MODEL_CLIENT_NODE is retired; configure an application model-client factory.")
    names = (
        "TOOL_STRATEGY",
        "API_RUNTIME",
        "SANDBOX_POLICY",
        "LOADER_STRATEGY",
        "EXECUTION_RUNTIME",
        "ORCHESTRATION_LOOP",
    )
    keys = tuple("ORKET_" + name + "_NODE" for name in names)
    return DecisionNodeRegistry(settings={key: captured.get(key, stored.get(key)) for key in keys})
