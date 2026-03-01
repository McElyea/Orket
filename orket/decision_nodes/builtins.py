from __future__ import annotations

from typing import Any, Callable, Dict, List
from pathlib import Path
from datetime import timedelta
import uuid
import re
import os

from orket.decision_nodes.contracts import PlanningInput
from orket.schema import CardStatus
from orket.adapters.tools.default_strategy import compose_default_tool_map
from orket.exceptions import CatastrophicFailure, ExecutionFailed, GovernanceViolation
from orket.decision_nodes.api_runtime_strategy_node import DefaultApiRuntimeStrategyNode


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


class DefaultRouterNode:
    """
    Built-in router decision node.
    Preserves existing seat-routing behavior, including integrity-guard preference
    during review turns.
    """

    def route(self, issue: Any, team: Any, is_review_turn: bool) -> str:
        if not is_review_turn:
            return issue.seat

        verifier_seat = next(
            (name for name, seat in team.seats.items() if "integrity_guard" in seat.roles),
            None,
        )
        return verifier_seat or issue.seat


class DefaultPromptStrategyNode:
    """
    Built-in prompt/model strategy decision node.
    Delegates to existing ModelSelector behavior to preserve runtime defaults.
    """

    def __init__(self, model_selector: Any):
        self.model_selector = model_selector

    def select_model(self, role: str, asset_config: Any) -> str:
        return self.model_selector.select(role=role, asset_config=asset_config)

    def select_dialect(self, model: str) -> str:
        return self.model_selector.get_dialect_name(model)


class DefaultEvaluatorNode:
    """
    Built-in evaluator decision node.
    Preserves existing success/failure orchestration decisions.
    """

    def evaluate_success(
        self,
        issue: Any,
        updated_issue: Any,
        turn: Any,
        seat_name: str,
        is_review_turn: bool,
    ) -> Dict[str, Any]:
        return {
            "remember_decision": ("decision" in (turn.content or "").lower()) or ("architect" in seat_name),
            "trigger_sandbox": (
                updated_issue.status == CardStatus.CODE_REVIEW
                or (updated_issue.status == issue.status and not is_review_turn)
            ),
            "promote_code_review": updated_issue.status == issue.status,
        }

    def evaluate_failure(self, issue: Any, result: Any) -> Dict[str, Any]:
        if self._is_recoverable_missing_read_error(result):
            next_retry_count = issue.retry_count + 1
            if next_retry_count > issue.max_retries:
                return {"action": "catastrophic", "next_retry_count": next_retry_count}
            return {"action": "retry", "next_retry_count": next_retry_count}

        if result.violations or self._is_governance_deterministic_failure(result):
            return {"action": "governance_violation", "next_retry_count": issue.retry_count}

        next_retry_count = issue.retry_count + 1
        if next_retry_count > issue.max_retries:
            return {"action": "catastrophic", "next_retry_count": next_retry_count}

        return {"action": "retry", "next_retry_count": next_retry_count}

    def _is_governance_deterministic_failure(self, result: Any) -> bool:
        error_text = str(getattr(result, "error", "") or "").strip().lower()
        if not error_text.startswith("deterministic failure:"):
            return False
        governance_markers = (
            "security scope contract not met",
            "hallucination scope contract not met",
            "consistency scope contract not met",
            "guard rejection payload contract not met",
            "read path contract not met",
            "write path contract not met",
            "architecture decision contract not met",
        )
        return any(marker in error_text for marker in governance_markers)

    def _is_recoverable_missing_read_error(self, result: Any) -> bool:
        violations = [str(item or "").strip().lower() for item in (getattr(result, "violations", []) or [])]
        marker = "tool read_file failed: file not found"
        if violations and all(marker in violation for violation in violations):
            return True
        error_text = str(getattr(result, "error", "") or "").strip().lower()
        return marker in error_text

    def success_post_actions(self, success_eval: Dict[str, Any]) -> Dict[str, Any]:
        trigger_sandbox = bool(success_eval.get("trigger_sandbox"))
        next_status = None
        if trigger_sandbox and success_eval.get("promote_code_review"):
            next_status = CardStatus.CODE_REVIEW
        return {"trigger_sandbox": trigger_sandbox, "next_status": next_status}

    def should_trigger_sandbox(self, success_actions: Dict[str, Any]) -> bool:
        return bool(success_actions.get("trigger_sandbox"))

    def next_status_after_success(self, success_actions: Dict[str, Any]) -> Any:
        return success_actions.get("next_status")

    def status_for_failure_action(self, action: str) -> Any:
        mapping = {
            "governance_violation": CardStatus.BLOCKED,
            "catastrophic": CardStatus.BLOCKED,
            "retry": CardStatus.READY,
        }
        return mapping.get(action, CardStatus.BLOCKED)

    def should_cancel_session(self, action: str) -> bool:
        return action == "catastrophic"

    def failure_event_name(self, action: str) -> str | None:
        mapping = {
            "catastrophic": "catastrophic_failure",
            "retry": "retry_triggered",
        }
        return mapping.get(action)

    def governance_violation_message(self, error: str | None) -> str:
        return f"Governance Violation: {error}"

    def catastrophic_failure_message(self, issue_id: str, max_retries: int) -> str:
        return (
            f"MAX RETRIES EXCEEDED for {issue_id}. "
            f"Limit: {max_retries}. Shutting down project orchestration."
        )

    def unexpected_failure_action_message(self, action: str, issue_id: str) -> str:
        return f"Unexpected evaluator action '{action}' for {issue_id}"

    def retry_failure_message(
        self,
        issue_id: str,
        retry_count: int,
        max_retries: int,
        error: str | None,
    ) -> str:
        return f"Orchestration Turn Failed (Retry {retry_count}/{max_retries}): {error}"

    def failure_exception_class(self, action: str) -> Any:
        mapping = {
            "governance_violation": GovernanceViolation,
            "catastrophic": CatastrophicFailure,
            "retry": ExecutionFailed,
        }
        return mapping.get(action, ExecutionFailed)


class DefaultToolStrategyNode:
    """
    Built-in tool strategy decision node.
    Preserves the legacy static tool mapping behavior.
    """

    def compose(self, toolbox: Any) -> Dict[str, Callable]:
        return compose_default_tool_map(toolbox)


class DefaultSandboxPolicyNode:
    """
    Built-in sandbox policy node.
    Preserves current sandbox naming, compose generation, and DB URL behavior.
    """

    def build_sandbox_id(self, rock_id: str) -> str:
        sanitized_rock = re.sub(r"[^a-z0-9_-]", "", rock_id.lower())
        return f"sandbox-{sanitized_rock}"

    def build_compose_project(self, sandbox_id: str) -> str:
        return f"orket-{sandbox_id}"

    def get_database_url(self, tech_stack: Any, ports: Any, db_password: str = "") -> str:
        value = tech_stack.value if hasattr(tech_stack, "value") else str(tech_stack)
        if "mongo" in value:
            return f"mongodb://localhost:{ports.database}/appdb"
        if "csharp" in value:
            return f"Server=localhost,{ports.database};Database=appdb;User=sa;Password={db_password}"
        return f"postgresql://postgres:{db_password}@localhost:{ports.database}/appdb"

    def generate_compose_file(self, sandbox: Any, db_password: str, admin_password: str) -> str:
        if sandbox.tech_stack.value == "fastapi-react-postgres":
            return f"""version: "3.8"

services:
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "{sandbox.ports.api}:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:{db_password}@db:5432/appdb
    depends_on:
      - db
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "{sandbox.ports.frontend}:3000"
    environment:
      - REACT_APP_API_URL=http://localhost:{sandbox.ports.api}
    depends_on:
      - api
    restart: unless-stopped

  db:
    image: postgres:16
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD={db_password}
      - POSTGRES_DB=appdb
    ports:
      - "{sandbox.ports.database}:5432"
    volumes:
      - db-data:/var/lib/postgresql/data
    restart: unless-stopped

  pgadmin:
    image: dpage/pgadmin4:latest
    environment:
      - PGADMIN_DEFAULT_EMAIL=admin@orket.local
      - PGADMIN_DEFAULT_PASSWORD={admin_password}
    ports:
      - "{sandbox.ports.admin_tool}:80"
    depends_on:
      - db
    restart: unless-stopped

volumes:
  db-data:
"""

        if sandbox.tech_stack.value == "fastapi-vue-mongo":
            return f"""version: "3.8"

services:
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "{sandbox.ports.api}:8000"
    environment:
      - MONGO_URL=mongodb://orket:{db_password}@mongo:27017/appdb?authSource=admin
    depends_on:
      - mongo
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "{sandbox.ports.frontend}:3000"
    environment:
      - VUE_APP_API_URL=http://localhost:{sandbox.ports.api}
    depends_on:
      - api
    restart: unless-stopped

  mongo:
    image: mongo:7
    environment:
      - MONGO_INITDB_ROOT_USERNAME=orket
      - MONGO_INITDB_ROOT_PASSWORD={db_password}
    ports:
      - "{sandbox.ports.database}:27017"
    volumes:
      - mongo-data:/data/db
    restart: unless-stopped

  mongo-express:
    image: mongo-express:latest
    environment:
      - ME_CONFIG_MONGODB_ADMINUSERNAME=orket
      - ME_CONFIG_MONGODB_ADMINPASSWORD={db_password}
      - ME_CONFIG_MONGODB_URL=mongodb://orket:{db_password}@mongo:27017/
      - ME_CONFIG_BASICAUTH_USERNAME=admin
      - ME_CONFIG_BASICAUTH_PASSWORD={admin_password}
    ports:
      - "{sandbox.ports.admin_tool}:8081"
    depends_on:
      - mongo
    restart: unless-stopped

volumes:
  mongo-data:
"""

        if sandbox.tech_stack.value == "csharp-razor-ef":
            return f"""version: "3.8"

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "{sandbox.ports.api}:8080"
      - "{sandbox.ports.frontend}:8443"
    environment:
      - ASPNETCORE_ENVIRONMENT=Development
      - ConnectionStrings__DefaultConnection=Server=db;Database=appdb;User=sa;Password={db_password};TrustServerCertificate=True
    depends_on:
      - db
    restart: unless-stopped

  db:
    image: mcr.microsoft.com/mssql/server:2022-latest
    environment:
      - ACCEPT_EULA=Y
      - SA_PASSWORD={db_password}
    ports:
      - "{sandbox.ports.database}:1433"
    volumes:
      - mssql-data:/var/opt/mssql
    restart: unless-stopped

volumes:
  mssql-data:
"""

        raise ValueError(f"Unsupported tech stack: {sandbox.tech_stack}")


class DefaultEngineRuntimePolicyNode:
    """
    Built-in engine runtime policy node.
    Preserves environment bootstrap and config-root fallback behavior.
    """

    def bootstrap_environment(self) -> None:
        from orket.settings import load_env
        load_env()

    def resolve_config_root(self, config_root: Any) -> Any:
        return config_root or Path(".").resolve()


class DefaultLoaderStrategyNode:
    """
    Built-in loader strategy node.
    Preserves ConfigLoader path priority and organization env override behavior.
    """

    def organization_modular_paths(self, config_dir: Any) -> tuple[Any, Any]:
        return (config_dir / "org_info.json", config_dir / "architecture.json")

    def organization_fallback_paths(self, config_dir: Any, model_dir: Any) -> List[Any]:
        return [config_dir / "organization.json", model_dir / "organization.json"]

    def department_paths(self, config_dir: Any, model_dir: Any, name: str) -> List[Any]:
        return [
            config_dir / "departments" / f"{name}.json",
            model_dir / name / "department.json",
        ]

    def asset_paths(self, config_dir: Any, model_dir: Any, dept: str, category: str, name: str) -> List[Any]:
        return [
            config_dir / category / f"{name}.json",
            model_dir / dept / category / f"{name}.json",
            model_dir / "core" / category / f"{name}.json",
        ]

    def list_asset_search_paths(self, config_dir: Any, model_dir: Any, dept: str, category: str) -> List[Any]:
        return [
            config_dir / category,
            model_dir / dept / category,
            model_dir / "core" / category,
        ]

    def apply_organization_overrides(self, org: Any, get_setting: Any) -> Any:
        env_name = get_setting("ORKET_ORG_NAME")
        if env_name:
            org.name = env_name

        env_vision = get_setting("ORKET_ORG_VISION")
        if env_vision:
            org.vision = env_vision
        return org


class DefaultExecutionRuntimeStrategyNode:
    """
    Built-in execution runtime strategy node.
    Preserves run/build id selection behavior.
    """

    def select_run_id(self, session_id: str | None) -> str:
        return session_id or str(uuid.uuid4())[:8]

    def select_epic_build_id(self, build_id: str | None, epic_name: str, sanitize_name: Any) -> str:
        return build_id or f"build-{sanitize_name(epic_name)}"

    def select_rock_session_id(self, session_id: str | None) -> str:
        return session_id or str(uuid.uuid4())[:8]

    def select_rock_build_id(self, build_id: str | None, rock_name: str, sanitize_name: Any) -> str:
        return build_id or f"rock-build-{sanitize_name(rock_name)}"


class DefaultPipelineWiringStrategyNode:
    """
    Built-in execution-pipeline wiring strategy node.
    Preserves current pipeline composition and subordinate sub-pipeline spawn behavior.
    """

    def create_sandbox_orchestrator(self, workspace: Any, organization: Any) -> Any:
        from orket.services.sandbox_orchestrator import SandboxOrchestrator
        return SandboxOrchestrator(workspace, organization=organization)

    def create_webhook_database(self) -> Any:
        from orket.adapters.vcs.webhook_db import WebhookDatabase
        return WebhookDatabase()

    def create_bug_fix_manager(self, organization: Any, webhook_db: Any) -> Any:
        from orket.domain.bug_fix_phase import BugFixPhaseManager
        return BugFixPhaseManager(
            organization_config=organization.process_rules if organization else {},
            db=webhook_db,
        )

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
        from orket.application.workflows.orchestrator import Orchestrator
        return Orchestrator(
            workspace=workspace,
            async_cards=async_cards,
            snapshots=snapshots,
            org=org,
            config_root=config_root,
            db_path=db_path,
            loader=loader,
            sandbox_orchestrator=sandbox_orchestrator,
        )

    def create_sub_pipeline(self, parent_pipeline: Any, epic_workspace: Any, department: str) -> Any:
        return parent_pipeline.__class__(
            epic_workspace,
            department,
            db_path=parent_pipeline.db_path,
            config_root=parent_pipeline.config_root,
            decision_nodes=parent_pipeline.decision_nodes,
        )


class DefaultOrchestrationLoopPolicyNode:
    """
    Built-in orchestrator loop policy node.
    Preserves existing concurrency and iteration defaults.
    """

    def concurrency_limit(self, organization: Any) -> int:
        return 3

    def max_iterations(self, organization: Any) -> int:
        return 20

    def context_window(self, organization: Any) -> int:
        raw = os.getenv("ORKET_CONTEXT_WINDOW", "10")
        try:
            return max(1, int(raw))
        except (TypeError, ValueError):
            return 10

    def is_review_turn(self, issue_status: Any) -> bool:
        return issue_status == CardStatus.CODE_REVIEW

    def turn_status_for_issue(self, is_review_turn: bool) -> Any:
        return CardStatus.CODE_REVIEW if is_review_turn else CardStatus.IN_PROGRESS

    def role_order_for_turn(self, roles: List[str], is_review_turn: bool) -> List[str]:
        ordered_roles = list(roles)
        if is_review_turn and "integrity_guard" not in ordered_roles:
            ordered_roles.insert(0, "integrity_guard")
        return ordered_roles

    def required_action_tools_for_seat(self, seat_name: str, **_kwargs) -> List[str]:
        seat = (seat_name or "").strip().lower()
        issue = _kwargs.get("issue")
        issue_seat = str(getattr(issue, "seat", "") or "").strip().lower()
        seat_requirements = {
            "requirements_analyst": ["write_file", "update_issue_status", "reforger_inspect"],
            "architect": ["write_file", "update_issue_status"],
            "coder": ["write_file", "update_issue_status"],
            "developer": ["write_file", "update_issue_status"],
            "code_reviewer": ["read_file", "update_issue_status"],
            "reviewer": ["read_file", "update_issue_status"],
            "integrity_guard": ["update_issue_status"],
        }
        if seat == "integrity_guard" and issue_seat in {"code_reviewer", "reviewer"}:
            return ["read_file", "update_issue_status"]
        return seat_requirements.get(seat, [])

    def required_statuses_for_seat(self, seat_name: str, **_kwargs) -> List[str]:
        seat = (seat_name or "").strip().lower()
        issue = _kwargs.get("issue")
        issue_seat = str(getattr(issue, "seat", "") or "").strip().lower()
        status_requirements = {
            "requirements_analyst": ["code_review"],
            "architect": ["code_review"],
            "coder": ["code_review"],
            "developer": ["code_review"],
            "code_reviewer": ["code_review"],
            "reviewer": ["code_review"],
            "integrity_guard": ["done", "blocked"],
        }
        if seat == "integrity_guard":
            # Guard can block only on final review issue; upstream handoff guards must resolve done.
            if issue_seat and issue_seat not in {"code_reviewer", "reviewer"}:
                return ["done"]
        return status_requirements.get(seat, [])

    def required_read_paths_for_seat(self, seat_name: str, **_kwargs) -> List[str]:
        seat = (seat_name or "").strip().lower()
        issue = _kwargs.get("issue")
        issue_seat = str(getattr(issue, "seat", "") or "").strip().lower()
        if seat in {"code_reviewer", "reviewer"}:
            return [
                "agent_output/requirements.txt",
                "agent_output/main.py",
            ]
        if seat == "integrity_guard" and issue_seat in {"code_reviewer", "reviewer"}:
            return [
                "agent_output/requirements.txt",
                "agent_output/design.txt",
                "agent_output/main.py",
                "agent_output/verification/runtime_verification.json",
            ]
        return []

    def required_write_paths_for_seat(self, seat_name: str, **_kwargs) -> List[str]:
        seat = (seat_name or "").strip().lower()
        seat_paths = {
            "requirements_analyst": ["agent_output/requirements.txt"],
            "architect": ["agent_output/design.txt"],
            "coder": ["agent_output/main.py"],
            "developer": ["agent_output/main.py"],
        }
        return seat_paths.get(seat, [])

    def gate_mode_for_seat(self, seat_name: str, **_kwargs) -> str:
        seat = (seat_name or "").strip().lower()
        if seat == "integrity_guard":
            return "review_required"
        return "auto"

    def approval_required_tools_for_seat(self, seat_name: str, **_kwargs) -> List[str]:
        # Default OFF to preserve current behavior. Enable per seat via custom loop policy node.
        _ = (seat_name or "").strip().lower()
        return []

    def validate_guard_rejection_payload(self, payload: Any) -> Dict[str, Any]:
        rationale = str(getattr(payload, "rationale", "") or "").strip()
        actions = getattr(payload, "remediation_actions", []) or []
        normalized_actions = [str(item).strip() for item in actions if str(item).strip()]

        if not rationale:
            return {
                "valid": False,
                "reason": "missing_rationale",
            }
        if not normalized_actions:
            return {
                "valid": False,
                "reason": "missing_remediation_actions",
            }
        return {"valid": True, "reason": None}

    def missing_seat_status(self) -> Any:
        return CardStatus.CANCELED

    def is_backlog_done(self, backlog: List[Any]) -> bool:
        terminal_statuses = {
            CardStatus.DONE,
            CardStatus.CANCELED,
            CardStatus.ARCHIVED,
            CardStatus.BLOCKED,
            CardStatus.GUARD_REJECTED,
            CardStatus.GUARD_APPROVED,
        }
        return all(i.status in terminal_statuses for i in backlog)

    def no_candidate_outcome(self, backlog: List[Any]) -> Dict[str, Any]:
        is_done = self.is_backlog_done(backlog)
        return {
            "is_done": is_done,
            "event_name": "orchestrator_epic_complete" if is_done else None,
        }

    def should_raise_exhaustion(
        self,
        iteration_count: int,
        max_iterations: int,
        backlog: List[Any],
    ) -> bool:
        return iteration_count >= max_iterations and not self.is_backlog_done(backlog)


class _DefaultAsyncModelClient:
    def __init__(self, provider: Any):
        self.provider = provider

    async def complete(self, messages):
        return await self.provider.complete(messages)


class DefaultModelClientPolicyNode:
    """
    Built-in model client policy node.
    Preserves LocalModelProvider selection and async client wrapping behavior.
    """

    def create_provider(self, selected_model: str, env: Any) -> Any:
        from orket.adapters.llm.local_model_provider import LocalModelProvider
        return LocalModelProvider(model=selected_model, temperature=env.temperature, timeout=env.timeout)

    def create_client(self, provider: Any) -> Any:
        return _DefaultAsyncModelClient(provider)

