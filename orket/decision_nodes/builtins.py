from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from orket.core.cards_runtime_contract import (
    required_read_paths_for_seat as resolve_cards_required_read_paths,
)
from orket.core.cards_runtime_contract import (
    required_write_paths_for_seat as resolve_cards_required_write_paths,
)
from orket.core.contracts.decision_inputs import (
    FailureEvaluationInput,
    LoopPolicyInputs,
    PlanningCardInput,
    PlanningInput,
    RoutingInput,
    SuccessEvaluationInput,
    ToolSelectionInput,
)
from orket.core.contracts.model_selection import ModelSelectionInput, model_dialect
from orket.decision_nodes.api_runtime_strategy_node import (
    DefaultApiRuntimeStrategyNode as _DefaultApiRuntimeStrategyNode,
)
from orket.exceptions import CatastrophicFailure, ExecutionFailed, GovernanceViolation
from orket.schema import CardStatus

DefaultApiRuntimeStrategyNode = _DefaultApiRuntimeStrategyNode


class DefaultPlannerNode:
    """Preserve orchestration candidate order over captured card facts."""

    def plan(self, data: PlanningInput) -> list[PlanningCardInput]:
        backlog = data.backlog
        independent_ready = data.independent_ready
        target_issue_id = data.target_issue_id

        in_review = [i for i in backlog if i.status == CardStatus.CODE_REVIEW]

        if target_issue_id:
            target = next((i for i in backlog if i.id == target_issue_id), None)
            if not target:
                return []
            if target.status in {
                CardStatus.IN_PROGRESS,
                CardStatus.CODE_REVIEW,
                CardStatus.AWAITING_GUARD_REVIEW,
            }:
                return [target]
            if target.status == CardStatus.READY and any(i.id == target_issue_id for i in independent_ready):
                return [target]
            return []

        return in_review + list(independent_ready)


class DefaultRouterNode:
    """
    Built-in router decision node.
    Preserves existing seat-routing behavior, including integrity-guard preference
    during review turns.
    """

    def route(self, data: RoutingInput) -> str:
        if not data.is_review_turn:
            return data.issue_seat
        verifier_seat = next((seat.name for seat in data.seats if "integrity_guard" in seat.roles), None)
        return verifier_seat or data.issue_seat


class DefaultPromptStrategyNode:
    """Pure recommendation over immutable, application-supplied values."""

    def select_model(self, inputs: ModelSelectionInput) -> str:
        return (inputs.asset_model or inputs.environment_model or inputs.preferred_model
                or inputs.organization_model or inputs.organization_default or inputs.default_model)

    def select_dialect(self, model: str) -> str:
        return model_dialect(model)


class DefaultEvaluatorNode:
    """
    Built-in evaluator decision node.
    Preserves existing success/failure orchestration decisions.
    """

    def evaluate_success(self, inputs: SuccessEvaluationInput) -> dict[str, Any]:
        turn = inputs.turn
        return {
            "remember_decision": ("decision" in turn.content.lower()) or ("architect" in turn.seat_name),
            "trigger_sandbox": (
                inputs.updated_issue_status == CardStatus.CODE_REVIEW
                or (inputs.updated_issue_status == turn.issue_status and not turn.is_review_turn)
            ),
            "promote_code_review": inputs.updated_issue_status == turn.issue_status,
        }

    def evaluate_failure(self, inputs: FailureEvaluationInput) -> dict[str, Any]:
        if self._is_recoverable_missing_read_error(inputs):
            next_retry_count = inputs.retry_count + 1
            if next_retry_count > inputs.max_retries:
                return {"action": "catastrophic", "next_retry_count": next_retry_count}
            return {"action": "retry", "next_retry_count": next_retry_count}

        if self._is_approval_required_pending(inputs):
            return {"action": "approval_pending", "next_retry_count": inputs.retry_count}

        if inputs.violations or self._is_governance_deterministic_failure(inputs):
            return {"action": "governance_violation", "next_retry_count": inputs.retry_count}

        next_retry_count = inputs.retry_count + 1
        if next_retry_count > inputs.max_retries:
            return {"action": "catastrophic", "next_retry_count": next_retry_count}

        return {"action": "retry", "next_retry_count": next_retry_count}

    def _is_governance_deterministic_failure(self, result: FailureEvaluationInput) -> bool:
        error_text = str(getattr(result, "error", "") or "").strip().lower()
        if not error_text.startswith("deterministic failure:"):
            return False
        # Corrective reprompts only happen after a deterministic contract failure.
        # If the follow-up still cannot satisfy progress, fail closed instead of retrying.
        governance_markers = (
            "security scope contract not met",
            "hallucination scope contract not met",
            "consistency scope contract not met",
            "guard rejection payload contract not met",
            "read path contract not met",
            "write path contract not met",
            "architecture decision contract not met",
            "progress contract not met after corrective reprompt",
            "turn contract not met after corrective reprompt",
        )
        return any(marker in error_text for marker in governance_markers)

    def _is_recoverable_missing_read_error(self, result: FailureEvaluationInput) -> bool:
        violations = [str(item or "").strip().lower() for item in (getattr(result, "violations", []) or [])]
        marker = "tool read_file failed: file not found"
        if violations and all(marker in violation for violation in violations):
            return True
        error_text = str(getattr(result, "error", "") or "").strip().lower()
        return marker in error_text

    def _is_approval_required_pending(self, result: FailureEvaluationInput) -> bool:
        error_text = str(getattr(result, "error", "") or "").strip().lower()
        return "approval required for tool 'write_file' before execution." in error_text

    def success_post_actions(self, success_eval: Mapping[str, Any]) -> dict[str, Any]:
        trigger_sandbox = bool(success_eval.get("trigger_sandbox"))
        next_status = None
        if trigger_sandbox and success_eval.get("promote_code_review"):
            next_status = CardStatus.CODE_REVIEW
        return {"trigger_sandbox": trigger_sandbox, "next_status": next_status}

    def should_trigger_sandbox(self, success_actions: Mapping[str, Any]) -> bool:
        return bool(success_actions.get("trigger_sandbox"))

    def next_status_after_success(self, success_actions: Mapping[str, Any]) -> Any:
        return success_actions.get("next_status")

    def status_for_failure_action(self, action: str) -> Any:
        mapping = {
            "approval_pending": CardStatus.READY,
            "governance_violation": CardStatus.BLOCKED,
            "catastrophic": CardStatus.BLOCKED,
            "retry": CardStatus.READY,
        }
        return mapping.get(action, CardStatus.BLOCKED)

    def should_cancel_session(self, action: str) -> bool:
        return action == "catastrophic"

    def failure_event_name(self, action: str) -> str | None:
        mapping = {
            "approval_pending": "approval_pending",
            "catastrophic": "catastrophic_failure",
            "retry": "retry_triggered",
        }
        return mapping.get(action)

    def governance_violation_message(self, error: str | None) -> str:
        return f"Governance Violation: {error}"

    def catastrophic_failure_message(self, issue_id: str, max_retries: int) -> str:
        return f"MAX RETRIES EXCEEDED for {issue_id}. Limit: {max_retries}. Shutting down project orchestration."

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
            "approval_pending": ExecutionFailed,
            "governance_violation": GovernanceViolation,
            "catastrophic": CatastrophicFailure,
            "retry": ExecutionFailed,
        }
        return mapping.get(action, ExecutionFailed)


class DefaultToolStrategyNode:
    """
    Built-in tool strategy decision node.
    Selects names from the application-owned tool inventory.
    """

    def select_tools(self, inputs: ToolSelectionInput) -> tuple[str, ...]:
        return inputs.available_names


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
        if value == "fastapi-vue-mongo":
            return f"mongodb://localhost:{ports.database}/appdb"
        if value == "csharp-razor-ef":
            return f"Server=localhost,{ports.database};Database=appdb;User=sa;Password={db_password}"
        if value == "fastapi-react-postgres":
            return f"postgresql://postgres:{db_password}@localhost:{ports.database}/appdb"
        raise ValueError(f"Unsupported tech stack: {tech_stack}")

    def generate_compose_file(self, sandbox: Any, db_password: str, admin_password: str) -> str:
        if sandbox.tech_stack.value == "fastapi-react-postgres":
            return f"""services:
  api:
    build:
      context: ../../
      dockerfile: agent_output/deployment/Dockerfile
    labels:
      orket.managed: "true"
      orket.sandbox_id: "{sandbox.id}"
      orket.run_id: "{sandbox.rock_id}"
    ports:
      - "{sandbox.ports.api}:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:{db_password}@db:5432/appdb
    depends_on:
      - db
    restart: unless-stopped

  frontend:
    image: nginx:alpine
    labels:
      orket.managed: "true"
      orket.sandbox_id: "{sandbox.id}"
      orket.run_id: "{sandbox.rock_id}"
    ports:
      - "{sandbox.ports.frontend}:80"
    volumes:
      - ../frontend:/usr/share/nginx/html:ro
    depends_on:
      - api
    restart: unless-stopped

  db:
    image: postgres:16
    labels:
      orket.managed: "true"
      orket.sandbox_id: "{sandbox.id}"
      orket.run_id: "{sandbox.rock_id}"
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
    labels:
      orket.managed: "true"
      orket.sandbox_id: "{sandbox.id}"
      orket.run_id: "{sandbox.rock_id}"
    environment:
      - PGADMIN_DEFAULT_EMAIL=admin@orket.dev
      - PGADMIN_DEFAULT_PASSWORD={admin_password}
    ports:
      - "{sandbox.ports.admin_tool}:80"
    depends_on:
      - db
    restart: unless-stopped

volumes:
  db-data:
    labels:
      orket.managed: "true"
      orket.sandbox_id: "{sandbox.id}"
      orket.run_id: "{sandbox.rock_id}"

networks:
  default:
    labels:
      orket.managed: "true"
      orket.sandbox_id: "{sandbox.id}"
      orket.run_id: "{sandbox.rock_id}"
"""

        if sandbox.tech_stack.value == "fastapi-vue-mongo":
            return f"""services:
  api:
    build:
      context: ../../
      dockerfile: agent_output/deployment/Dockerfile
    labels:
      orket.managed: "true"
      orket.sandbox_id: "{sandbox.id}"
      orket.run_id: "{sandbox.rock_id}"
    ports:
      - "{sandbox.ports.api}:8000"
    environment:
      - MONGO_URL=mongodb://orket:{db_password}@mongo:27017/appdb?authSource=admin
    depends_on:
      - mongo
    restart: unless-stopped

  frontend:
    image: nginx:alpine
    labels:
      orket.managed: "true"
      orket.sandbox_id: "{sandbox.id}"
      orket.run_id: "{sandbox.rock_id}"
    ports:
      - "{sandbox.ports.frontend}:80"
    volumes:
      - ../frontend:/usr/share/nginx/html:ro
    depends_on:
      - api
    restart: unless-stopped

  mongo:
    image: mongo:7
    labels:
      orket.managed: "true"
      orket.sandbox_id: "{sandbox.id}"
      orket.run_id: "{sandbox.rock_id}"
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
    labels:
      orket.managed: "true"
      orket.sandbox_id: "{sandbox.id}"
      orket.run_id: "{sandbox.rock_id}"
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
    labels:
      orket.managed: "true"
      orket.sandbox_id: "{sandbox.id}"
      orket.run_id: "{sandbox.rock_id}"

networks:
  default:
    labels:
      orket.managed: "true"
      orket.sandbox_id: "{sandbox.id}"
      orket.run_id: "{sandbox.rock_id}"
"""

        if sandbox.tech_stack.value == "csharp-razor-ef":
            return f"""services:
  app:
    build:
      context: ../../
      dockerfile: agent_output/deployment/Dockerfile
    labels:
      orket.managed: "true"
      orket.sandbox_id: "{sandbox.id}"
      orket.run_id: "{sandbox.rock_id}"
    ports:
      - "{sandbox.ports.api}:8080"
      - "{sandbox.ports.frontend}:8443"
    environment:
      - ASPNETCORE_ENVIRONMENT=Development
      - >-
        ConnectionStrings__DefaultConnection=Server=db;Database=appdb;User=sa;
        Password={db_password};TrustServerCertificate=True
    depends_on:
      - db
    restart: unless-stopped

  db:
    image: mcr.microsoft.com/mssql/server:2022-latest
    labels:
      orket.managed: "true"
      orket.sandbox_id: "{sandbox.id}"
      orket.run_id: "{sandbox.rock_id}"
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
    labels:
      orket.managed: "true"
      orket.sandbox_id: "{sandbox.id}"
      orket.run_id: "{sandbox.rock_id}"

networks:
  default:
    labels:
      orket.managed: "true"
      orket.sandbox_id: "{sandbox.id}"
      orket.run_id: "{sandbox.rock_id}"
"""

        raise ValueError(f"Unsupported tech stack: {sandbox.tech_stack}")


class DefaultLoaderStrategyNode:
    """
    Built-in loader strategy node.
    Preserves ConfigLoader path priority and organization env override behavior.
    """

    def organization_modular_paths(self, config_dir: Any) -> tuple[Any, Any]:
        return (config_dir / "org_info.json", config_dir / "architecture.json")

    def organization_fallback_paths(self, config_dir: Any, model_dir: Any) -> list[Any]:
        return [config_dir / "organization.json", model_dir / "organization.json"]

    def department_paths(self, config_dir: Any, model_dir: Any, name: str) -> list[Any]:
        return [
            config_dir / "departments" / f"{name}.json",
            model_dir / name / "department.json",
        ]

    def asset_paths(self, config_dir: Any, model_dir: Any, dept: str, category: str, name: str) -> list[Any]:
        return [
            config_dir / category / f"{name}.json",
            model_dir / dept / category / f"{name}.json",
            model_dir / "core" / category / f"{name}.json",
        ]

    def list_asset_search_paths(self, config_dir: Any, model_dir: Any, dept: str, category: str) -> list[Any]:
        return [
            config_dir / category,
            model_dir / dept / category,
            model_dir / "core" / category,
        ]



class DefaultExecutionRuntimeStrategyNode:
    """
    Built-in execution runtime strategy node.
    Preserves run/build id selection behavior.
    """

    def select_run_id(self, session_id: str | None) -> str:
        if not session_id:
            raise ValueError("session_id is required")
        return session_id

    def select_epic_build_id(self, build_id: str | None, epic_name: str, sanitize_name: Any) -> str:
        return build_id or f"build-{sanitize_name(epic_name)}"

    def select_epic_collection_session_id(self, session_id: str | None) -> str:
        if not session_id:
            raise ValueError("session_id is required")
        return session_id

    def select_epic_collection_build_id(
        self, build_id: str | None, collection_name: str, sanitize_name: Any
    ) -> str:
        return build_id or f"epic-collection-build-{sanitize_name(collection_name)}"

class DefaultOrchestrationLoopPolicyNode:
    """
    Built-in orchestrator loop policy node.
    Preserves existing concurrency and iteration defaults.
    """

    def concurrency_limit(self, inputs: LoopPolicyInputs) -> int:
        raw = inputs.concurrency
        if raw is not None:
            try:
                return max(1, int(raw))
            except (TypeError, ValueError):
                pass
        return 3

    def max_iterations(self, inputs: LoopPolicyInputs) -> int:
        raw = inputs.max_iterations or inputs.configured_max_iterations
        if raw is not None:
            try:
                return max(1, int(raw))
            except (TypeError, ValueError):
                pass
        # Default above 20 so multi-issue builder+guard epics can complete without a custom loop policy.
        return 40

    def context_window(self, inputs: LoopPolicyInputs) -> int:
        raw = inputs.context_window
        try:
            return max(1, int(raw))
        except (TypeError, ValueError):
            return 10

    def is_review_turn(self, issue_status: Any) -> bool:
        return bool(issue_status == CardStatus.CODE_REVIEW)

    def turn_status_for_issue(self, is_review_turn: bool) -> Any:
        return CardStatus.CODE_REVIEW if is_review_turn else CardStatus.IN_PROGRESS

    def role_order_for_turn(self, roles: list[str], is_review_turn: bool) -> list[str]:
        ordered_roles = list(roles)
        if is_review_turn and "integrity_guard" not in ordered_roles:
            ordered_roles.insert(0, "integrity_guard")
        return ordered_roles

    def required_action_tools_for_seat(self, seat_name: str, **_kwargs: Any) -> list[str]:
        seat = (seat_name or "").strip().lower()
        issue = _kwargs.get("issue")
        issue_seat = str(getattr(issue, "seat", "") or "").strip().lower()
        seat_requirements = {
            # Governed required tools must stay aligned with the shipped role surface.
            "requirements_analyst": ["write_file", "update_issue_status"],
            "architect": ["write_file", "update_issue_status"],
            "coder": ["write_file", "update_issue_status"],
            "developer": ["write_file", "update_issue_status"],
            "evidence_reviewer": ["write_file", "update_issue_status"],
            "code_reviewer": ["read_file", "update_issue_status"],
            "reviewer": ["read_file", "update_issue_status"],
            "integrity_guard": ["update_issue_status"],
        }
        resolved = list(seat_requirements.get(seat, []))
        if seat == "integrity_guard":
            review_paths = resolve_cards_required_read_paths(seat_name=seat_name, issue=issue)
            if review_paths or issue_seat in {"code_reviewer", "reviewer"}:
                return ["read_file", "update_issue_status"]
        return resolved

    def required_statuses_for_seat(self, seat_name: str, **_kwargs: Any) -> list[str]:
        seat = (seat_name or "").strip().lower()
        issue = _kwargs.get("issue")
        issue_seat = str(getattr(issue, "seat", "") or "").strip().lower()
        status_requirements = {
            "requirements_analyst": ["code_review"],
            "architect": ["code_review"],
            "coder": ["code_review"],
            "developer": ["code_review"],
            "evidence_reviewer": ["code_review"],
            "code_reviewer": ["code_review"],
            "reviewer": ["code_review"],
            "integrity_guard": ["done", "blocked"],
        }
        if seat == "integrity_guard" and issue_seat and issue_seat not in {"code_reviewer", "reviewer"}:
            # Guard can block only on final review issue; upstream handoff guards must resolve done.
            return ["done"]
        return status_requirements.get(seat, [])

    def required_read_paths_for_seat(self, seat_name: str, **_kwargs: Any) -> list[str]:
        issue = _kwargs.get("issue")
        return resolve_cards_required_read_paths(seat_name=seat_name, issue=issue)

    def required_write_paths_for_seat(self, seat_name: str, **_kwargs: Any) -> list[str]:
        issue = _kwargs.get("issue")
        return resolve_cards_required_write_paths(seat_name=seat_name, issue=issue)

    def gate_mode_for_seat(self, seat_name: str, **_kwargs: Any) -> str:
        seat = (seat_name or "").strip().lower()
        if seat == "integrity_guard":
            return "review_required"
        return "auto"

    def approval_required_tools_for_seat(self, seat_name: str, **_kwargs: Any) -> list[str]:
        # Default OFF to preserve current behavior. Enable per seat via custom loop policy node.
        _ = (seat_name or "").strip().lower()
        return []

    def validate_guard_rejection_payload(self, payload: Any) -> dict[str, Any]:
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

    def is_backlog_done(self, backlog: list[Any]) -> bool:
        terminal_statuses = {
            CardStatus.DONE,
            CardStatus.CANCELED,
            CardStatus.ARCHIVED,
            CardStatus.BLOCKED,
            CardStatus.GUARD_REJECTED,
            CardStatus.GUARD_APPROVED,
        }
        return all(i.status in terminal_statuses for i in backlog)

    def no_candidate_outcome(self, backlog: list[Any]) -> dict[str, Any]:
        is_done = self.is_backlog_done(backlog)
        return {
            "is_done": is_done,
            "event_name": "orchestrator_epic_stopped" if is_done else None,
        }

    def should_raise_exhaustion(
        self,
        iteration_count: int,
        max_iterations: int,
        backlog: list[Any],
    ) -> bool:
        return iteration_count >= max_iterations and not self.is_backlog_done(backlog)
