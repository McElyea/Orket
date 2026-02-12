from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Protocol


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

    def success_post_actions(self, success_eval: Dict[str, Any]) -> Dict[str, Any]:
        ...

    def status_for_failure_action(self, action: str) -> Any:
        ...

    def should_cancel_session(self, action: str) -> bool:
        ...

    def failure_event_name(self, action: str) -> str | None:
        ...


class PromptStrategyNode(Protocol):
    """Decision node: chooses model and dialect strategy for a turn."""

    def select_model(self, role: str, asset_config: Any) -> str:
        ...

    def select_dialect(self, model: str) -> str:
        ...


class ToolStrategyNode(Protocol):
    """Decision node: composes tool-name to callable mappings."""

    def compose(self, toolbox: Any) -> Dict[str, Callable]:
        ...


class ApiRuntimeStrategyNode(Protocol):
    """Decision node: runtime-variable API choices."""

    def default_allowed_origins_value(self) -> str:
        ...

    def parse_allowed_origins(self, origins_value: str) -> List[str]:
        ...

    def is_api_key_valid(self, expected_key: str | None, provided_key: str | None) -> bool:
        ...

    def resolve_asset_id(self, path: str | None, issue_id: str | None) -> str | None:
        ...

    def create_session_id(self) -> str:
        ...

    def resolve_run_active_invocation(
        self,
        asset_id: str,
        build_id: str | None,
        session_id: str,
        request_type: str | None,
    ) -> Dict[str, Any]:
        ...

    def resolve_clear_logs_path(self) -> str:
        ...

    def normalize_metrics(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        ...

    def calendar_window(self, now: Any) -> Dict[str, str]:
        ...

    def resolve_explorer_path(self, project_root: Any, path: str) -> Any | None:
        ...

    def include_explorer_entry(self, entry_name: str) -> bool:
        ...

    def sort_explorer_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        ...

    def resolve_preview_target(self, path: str, issue_id: str | None) -> Dict[str, str]:
        ...

    def select_preview_build_method(self, mode: str) -> str:
        ...

    def resolve_preview_invocation(self, target: Dict[str, str], issue_id: str | None) -> Dict[str, Any]:
        ...

    def create_preview_builder(self, model_root: Any) -> Any:
        ...

    def create_chat_driver(self) -> Any:
        ...

    def resolve_member_metrics_workspace(self, project_root: Any, session_id: str) -> Any:
        ...

    def resolve_sandbox_workspace(self, project_root: Any) -> Any:
        ...

    def create_execution_pipeline(self, workspace_root: Any) -> Any:
        ...

    def resolve_api_workspace(self, project_root: Any) -> Any:
        ...

    def create_engine(self, workspace_root: Any) -> Any:
        ...

    def create_file_tools(self, project_root: Any) -> Any:
        ...

    def resolve_system_board(self, department: str) -> Any:
        ...

    def should_remove_websocket(self, exception: Exception) -> bool:
        ...


class SandboxPolicyNode(Protocol):
    """Decision node: sandbox lifecycle policy choices."""

    def build_sandbox_id(self, rock_id: str) -> str:
        ...

    def build_compose_project(self, sandbox_id: str) -> str:
        ...

    def get_database_url(self, tech_stack: Any, ports: Any, db_password: str = "") -> str:
        ...

    def generate_compose_file(self, sandbox: Any, db_password: str, admin_password: str) -> str:
        ...


class EngineRuntimePolicyNode(Protocol):
    """Decision node: engine bootstrap/runtime wiring choices."""

    def bootstrap_environment(self) -> None:
        ...

    def resolve_config_root(self, config_root: Any) -> Any:
        ...


class LoaderStrategyNode(Protocol):
    """Decision node: config/model loader path and override policy."""

    def organization_modular_paths(self, config_dir: Any) -> tuple[Any, Any]:
        ...

    def organization_fallback_paths(self, config_dir: Any, model_dir: Any) -> List[Any]:
        ...

    def department_paths(self, config_dir: Any, model_dir: Any, name: str) -> List[Any]:
        ...

    def asset_paths(self, config_dir: Any, model_dir: Any, dept: str, category: str, name: str) -> List[Any]:
        ...

    def list_asset_search_paths(self, config_dir: Any, model_dir: Any, dept: str, category: str) -> List[Any]:
        ...

    def apply_organization_overrides(self, org: Any, get_setting: Any) -> Any:
        ...


class ExecutionRuntimeStrategyNode(Protocol):
    """Decision node: execution runtime id/build selection policy."""

    def select_run_id(self, session_id: str | None) -> str:
        ...

    def select_epic_build_id(self, build_id: str | None, epic_name: str, sanitize_name: Any) -> str:
        ...

    def select_rock_session_id(self, session_id: str | None) -> str:
        ...

    def select_rock_build_id(self, build_id: str | None, rock_name: str, sanitize_name: Any) -> str:
        ...


class PipelineWiringStrategyNode(Protocol):
    """Decision node: execution pipeline wiring and subordinate spawn policy."""

    def create_sandbox_orchestrator(self, workspace: Any, organization: Any) -> Any:
        ...

    def create_webhook_database(self) -> Any:
        ...

    def create_bug_fix_manager(self, organization: Any, webhook_db: Any) -> Any:
        ...

    def create_orchestrator(
        self,
        workspace: Any,
        async_cards: Any,
        snapshots: Any,
        org: Any,
        config_root: Any,
        db_path: str,
        loader: Any,
        sandbox_orchestrator: Any,
    ) -> Any:
        ...

    def create_sub_pipeline(self, parent_pipeline: Any, epic_workspace: Any, department: str) -> Any:
        ...


class OrchestrationLoopPolicyNode(Protocol):
    """Decision node: execution-loop policy knobs for orchestrator runtime."""

    def concurrency_limit(self, organization: Any) -> int:
        ...

    def max_iterations(self, organization: Any) -> int:
        ...

    def context_window(self, organization: Any) -> int:
        ...

    def is_review_turn(self, issue_status: Any) -> bool:
        ...

    def turn_status_for_issue(self, is_review_turn: bool) -> Any:
        ...

    def role_order_for_turn(self, roles: List[str], is_review_turn: bool) -> List[str]:
        ...

    def missing_seat_status(self) -> Any:
        ...

    def is_backlog_done(self, backlog: List[Any]) -> bool:
        ...


class ModelClientPolicyNode(Protocol):
    """Decision node: model provider/client construction policy."""

    def create_provider(self, selected_model: str, env: Any) -> Any:
        ...

    def create_client(self, provider: Any) -> Any:
        ...
