from __future__ import annotations

from typing import Any, Callable, Dict, List
from pathlib import Path
import uuid
import re

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
        return {
            "read_file": toolbox.fs.read_file,
            "write_file": toolbox.fs.write_file,
            "list_directory": toolbox.fs.list_directory,
            "image_analyze": toolbox.vision.image_analyze,
            "image_generate": toolbox.vision.image_generate,
            "create_issue": toolbox.cards.create_issue,
            "update_issue_status": toolbox.cards.update_issue_status,
            "add_issue_comment": toolbox.cards.add_issue_comment,
            "get_issue_context": toolbox.cards.get_issue_context,
            "nominate_card": toolbox.nominate_card,
            "report_credits": toolbox.report_credits,
            "refinement_proposal": toolbox.refinement_proposal,
            "request_excuse": toolbox.request_excuse,
            "archive_eval": toolbox.academy.archive_eval,
            "promote_prompt": toolbox.academy.promote_prompt,
        }


class DefaultApiRuntimeStrategyNode:
    """
    Built-in API runtime strategy node.
    Preserves existing API request/runtime decision behavior.
    """

    def parse_allowed_origins(self, origins_value: str) -> List[str]:
        return [origin.strip() for origin in origins_value.split(",") if origin.strip()]

    def resolve_asset_id(self, path: str | None, issue_id: str | None) -> str | None:
        if issue_id:
            return issue_id
        if path:
            return Path(path).stem
        return None

    def create_session_id(self) -> str:
        return str(uuid.uuid4())[:8]


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
