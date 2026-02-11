from __future__ import annotations

from typing import Any, Callable, Dict, List
from pathlib import Path
from datetime import timedelta
import uuid
import re
import os

from orket.decision_nodes.contracts import PlanningInput
from orket.schema import CardStatus
from orket.tool_strategy.default import compose_default_tool_map


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
        if result.violations:
            return {"action": "governance_violation", "next_retry_count": issue.retry_count}

        next_retry_count = issue.retry_count + 1
        if next_retry_count > issue.max_retries:
            return {"action": "catastrophic", "next_retry_count": next_retry_count}

        return {"action": "retry", "next_retry_count": next_retry_count}


class DefaultToolStrategyNode:
    """
    Built-in tool strategy decision node.
    Preserves the legacy static tool mapping behavior.
    """

    def compose(self, toolbox: Any) -> Dict[str, Callable]:
        return compose_default_tool_map(toolbox)


class DefaultApiRuntimeStrategyNode:
    """
    Built-in API runtime strategy node.
    Preserves existing API request/runtime decision behavior.
    """

    def default_allowed_origins_value(self) -> str:
        return "http://localhost:5173,http://127.0.0.1:5173"

    def parse_allowed_origins(self, origins_value: str) -> List[str]:
        return [origin.strip() for origin in origins_value.split(",") if origin.strip()]

    def is_api_key_valid(self, expected_key: str | None, provided_key: str | None) -> bool:
        return (not expected_key) or (provided_key == expected_key)

    def resolve_asset_id(self, path: str | None, issue_id: str | None) -> str | None:
        if issue_id:
            return issue_id
        if path:
            return Path(path).stem
        return None

    def create_session_id(self) -> str:
        return str(uuid.uuid4())[:8]

    def resolve_run_active_invocation(
        self,
        asset_id: str,
        build_id: str | None,
        session_id: str,
        request_type: str | None,
    ) -> Dict[str, Any]:
        return {
            "method_name": "run_card",
            "kwargs": {
                "card_id": asset_id,
                "build_id": build_id,
                "session_id": session_id,
            },
        }

    def resolve_clear_logs_path(self) -> str:
        return "workspace/default/orket.log"

    def normalize_metrics(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(snapshot)
        if "cpu" not in normalized and "cpu_percent" in normalized:
            normalized["cpu"] = normalized["cpu_percent"]
        if "memory" not in normalized and "ram_percent" in normalized:
            normalized["memory"] = normalized["ram_percent"]
        return normalized

    def calendar_window(self, now: Any) -> Dict[str, str]:
        return {
            "sprint_start": (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d"),
            "sprint_end": (now + timedelta(days=4 - now.weekday())).strftime("%Y-%m-%d"),
        }

    def resolve_explorer_path(self, project_root: Any, path: str) -> Any | None:
        candidate_path = path or "."
        if any(part == ".." for part in Path(candidate_path).parts):
            return None
        rel_path = candidate_path.strip("./") if candidate_path != "." else ""
        target = (project_root / rel_path).resolve()
        if not target.is_relative_to(project_root):
            return None
        return target

    def include_explorer_entry(self, entry_name: str) -> bool:
        if entry_name.startswith("."):
            return False
        if "__pycache__" in entry_name:
            return False
        if entry_name == "node_modules":
            return False
        return True

    def sort_explorer_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return sorted(items, key=lambda item: (not item["is_dir"], item["name"].lower()))

    def resolve_preview_target(self, path: str, issue_id: str | None) -> Dict[str, str]:
        resolved_path = Path(path)
        asset_name = resolved_path.stem
        department = "core"
        if "model" in resolved_path.parts:
            model_index = resolved_path.parts.index("model")
            if len(resolved_path.parts) > model_index + 1:
                department = resolved_path.parts[model_index + 1]

        mode = "epic"
        if issue_id:
            mode = "issue"
        elif "rocks" in resolved_path.parts:
            mode = "rock"

        return {"mode": mode, "asset_name": asset_name, "department": department}

    def select_preview_build_method(self, mode: str) -> str:
        method_map = {
            "issue": "build_issue_preview",
            "rock": "build_rock_preview",
        }
        return method_map.get(mode, "build_epic_preview")

    def resolve_preview_invocation(self, target: Dict[str, str], issue_id: str | None) -> Dict[str, Any]:
        method_name = self.select_preview_build_method(target["mode"])
        if target["mode"] == "issue":
            return {
                "method_name": method_name,
                "args": [issue_id, target["asset_name"], target["department"]],
            }
        return {
            "method_name": method_name,
            "args": [target["asset_name"], target["department"]],
        }

    def create_preview_builder(self, model_root: Any) -> Any:
        from orket.preview import PreviewBuilder
        return PreviewBuilder(model_root)

    def create_chat_driver(self) -> Any:
        from orket.driver import OrketDriver
        return OrketDriver()

    def resolve_member_metrics_workspace(self, project_root: Any, session_id: str) -> Any:
        workspace = project_root / "workspace" / "runs" / session_id
        if workspace.exists():
            return workspace
        return project_root / "workspace" / "default"

    def resolve_sandbox_workspace(self, project_root: Any) -> Any:
        return project_root / "workspace" / "default"

    def create_execution_pipeline(self, workspace_root: Any) -> Any:
        from orket.orket import ExecutionPipeline
        return ExecutionPipeline(workspace_root)

    def resolve_api_workspace(self, project_root: Any) -> Any:
        return project_root / "workspace" / "default"

    def create_engine(self, workspace_root: Any) -> Any:
        from orket.orchestration.engine import OrchestrationEngine
        return OrchestrationEngine(workspace_root)

    def create_file_tools(self, project_root: Any) -> Any:
        from orket.infrastructure.async_file_tools import AsyncFileTools
        return AsyncFileTools(project_root)

    def resolve_system_board(self, department: str) -> Any:
        from orket.board import get_board_hierarchy
        return get_board_hierarchy(department)

    def should_remove_websocket(self, exception: Exception) -> bool:
        return isinstance(exception, (RuntimeError, ValueError))


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
        from orket.services.webhook_db import WebhookDatabase
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
        from orket.orchestration.orchestrator import Orchestrator
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

    def missing_seat_status(self) -> Any:
        return CardStatus.CANCELED

    def is_backlog_done(self, backlog: List[Any]) -> bool:
        return all(i.status in [CardStatus.DONE, CardStatus.CANCELED] for i in backlog)


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
        from orket.llm import LocalModelProvider
        return LocalModelProvider(model=selected_model, temperature=env.temperature, timeout=env.timeout)

    def create_client(self, provider: Any) -> Any:
        return _DefaultAsyncModelClient(provider)
