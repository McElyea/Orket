from __future__ import annotations

from typing import Any, Dict

from orket.decision_nodes.builtins import (
    DefaultApiRuntimeStrategyNode,
    DefaultEngineRuntimePolicyNode,
    DefaultExecutionRuntimeStrategyNode,
    DefaultEvaluatorNode,
    DefaultLoaderStrategyNode,
    DefaultModelClientPolicyNode,
    DefaultOrchestrationLoopPolicyNode,
    DefaultPipelineWiringStrategyNode,
    DefaultPlannerNode,
    DefaultPromptStrategyNode,
    DefaultRouterNode,
    DefaultSandboxPolicyNode,
    DefaultToolStrategyNode,
)
from orket.decision_nodes.contracts import (
    EvaluatorNode,
    EngineRuntimePolicyNode,
    ExecutionRuntimeStrategyNode,
    LoaderStrategyNode,
    ModelClientPolicyNode,
    OrchestrationLoopPolicyNode,
    PipelineWiringStrategyNode,
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
        self._loader_strategy_nodes: Dict[str, LoaderStrategyNode] = {
            "default": DefaultLoaderStrategyNode()
        }
        self._execution_runtime_nodes: Dict[str, ExecutionRuntimeStrategyNode] = {
            "default": DefaultExecutionRuntimeStrategyNode()
        }
        self._pipeline_wiring_nodes: Dict[str, PipelineWiringStrategyNode] = {
            "default": DefaultPipelineWiringStrategyNode()
        }
        self._orchestration_loop_nodes: Dict[str, OrchestrationLoopPolicyNode] = {
            "default": DefaultOrchestrationLoopPolicyNode()
        }
        self._model_client_nodes: Dict[str, ModelClientPolicyNode] = {
            "default": DefaultModelClientPolicyNode()
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

    def register_loader_strategy(self, name: str, node: LoaderStrategyNode) -> None:
        self._loader_strategy_nodes[name] = node

    def register_execution_runtime(self, name: str, node: ExecutionRuntimeStrategyNode) -> None:
        self._execution_runtime_nodes[name] = node

    def register_pipeline_wiring(self, name: str, node: PipelineWiringStrategyNode) -> None:
        self._pipeline_wiring_nodes[name] = node

    def register_orchestration_loop(self, name: str, node: OrchestrationLoopPolicyNode) -> None:
        self._orchestration_loop_nodes[name] = node

    def register_model_client(self, name: str, node: ModelClientPolicyNode) -> None:
        self._model_client_nodes[name] = node

    def register_module_nodes(self, module_id: str, registrations: Dict[str, Any]) -> None:
        """
        Register a module-provided set of decision nodes using explicit keys.
        Supported keys:
        planner, router, prompt_strategy, evaluator, tool_strategy, api_runtime,
        sandbox_policy, engine_runtime, loader_strategy, execution_runtime,
        pipeline_wiring, orchestration_loop, model_client.
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
            elif slot == "engine_runtime":
                self.register_engine_runtime(key, node)
            elif slot == "loader_strategy":
                self.register_loader_strategy(key, node)
            elif slot == "execution_runtime":
                self.register_execution_runtime(key, node)
            elif slot == "pipeline_wiring":
                self.register_pipeline_wiring(key, node)
            elif slot == "orchestration_loop":
                self.register_orchestration_loop(key, node)
            elif slot == "model_client":
                self.register_model_client(key, node)
            else:
                raise ValueError(f"Unsupported decision node registration type '{node_type}'")

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

    def resolve_loader_strategy(self, organization: Any = None) -> LoaderStrategyNode:
        loader_strategy_name = "default"
        if organization and getattr(organization, "process_rules", None):
            loader_strategy_name = organization.process_rules.get("loader_strategy_node", "default")

        env_override = get_setting("ORKET_LOADER_STRATEGY_NODE")
        if isinstance(env_override, str) and env_override.strip():
            loader_strategy_name = env_override.strip()

        return self._loader_strategy_nodes.get(loader_strategy_name, self._loader_strategy_nodes["default"])

    def resolve_execution_runtime(self, organization: Any = None) -> ExecutionRuntimeStrategyNode:
        execution_runtime_name = "default"
        if organization and getattr(organization, "process_rules", None):
            execution_runtime_name = organization.process_rules.get("execution_runtime_node", "default")

        env_override = get_setting("ORKET_EXECUTION_RUNTIME_NODE")
        if isinstance(env_override, str) and env_override.strip():
            execution_runtime_name = env_override.strip()

        return self._execution_runtime_nodes.get(
            execution_runtime_name,
            self._execution_runtime_nodes["default"],
        )

    def resolve_pipeline_wiring(self, organization: Any = None) -> PipelineWiringStrategyNode:
        pipeline_wiring_name = "default"
        if organization and getattr(organization, "process_rules", None):
            pipeline_wiring_name = organization.process_rules.get("pipeline_wiring_node", "default")

        env_override = get_setting("ORKET_PIPELINE_WIRING_NODE")
        if isinstance(env_override, str) and env_override.strip():
            pipeline_wiring_name = env_override.strip()

        return self._pipeline_wiring_nodes.get(
            pipeline_wiring_name,
            self._pipeline_wiring_nodes["default"],
        )

    def resolve_orchestration_loop(self, organization: Any = None) -> OrchestrationLoopPolicyNode:
        loop_policy_name = "default"
        if organization and getattr(organization, "process_rules", None):
            loop_policy_name = organization.process_rules.get("orchestration_loop_node", "default")

        env_override = get_setting("ORKET_ORCHESTRATION_LOOP_NODE")
        if isinstance(env_override, str) and env_override.strip():
            loop_policy_name = env_override.strip()

        return self._orchestration_loop_nodes.get(
            loop_policy_name,
            self._orchestration_loop_nodes["default"],
        )

    def resolve_model_client(self, organization: Any = None) -> ModelClientPolicyNode:
        model_client_name = "default"
        if organization and getattr(organization, "process_rules", None):
            model_client_name = organization.process_rules.get("model_client_node", "default")

        env_override = get_setting("ORKET_MODEL_CLIENT_NODE")
        if isinstance(env_override, str) and env_override.strip():
            model_client_name = env_override.strip()

        return self._model_client_nodes.get(
            model_client_name,
            self._model_client_nodes["default"],
        )
