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

    def parse_allowed_origins(self, origins_value: str) -> List[str]:
        ...

    def resolve_asset_id(self, path: str | None, issue_id: str | None) -> str | None:
        ...

    def create_session_id(self) -> str:
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
