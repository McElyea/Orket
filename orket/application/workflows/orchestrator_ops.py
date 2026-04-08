import asyncio
import inspect
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from orket.application.services.dependency_manager import (
    DependencyManager,
    DependencyValidationError,
)
from orket.application.services.deployment_planner import (
    DeploymentPlanner,
    DeploymentValidationError,
)
from orket.application.services.orchestrator_review_preflight_service import (
    OrchestratorReviewPreflightService,
)
from orket.application.services.orchestrator_turn_preparation_service import (
    OrchestratorTurnPreparationService,
    TurnPreparationInput,
)
from orket.application.services.orchestrator_turn_success_handler import (
    OrchestratorTurnSuccessHandler,
)
from orket.application.services.prompt_compiler import PromptCompiler
from orket.application.services.prompt_resolver import PromptResolver
from orket.application.services.runtime_policy import (
    resolve_architecture_mode,
    resolve_frontend_framework_mode,
    resolve_local_prompting_allow_fallback,
    resolve_local_prompting_fallback_profile_id,
    resolve_local_prompting_mode,
    resolve_project_surface_profile,
    resolve_protocol_determinism_controls,
    resolve_small_project_builder_variant,
)
from orket.application.services.runtime_verifier import RuntimeVerifier
from orket.application.services.scaffolder import Scaffolder, ScaffoldValidationError
from orket.application.services.orchestrator_turn_context_builder import (
    OrchestratorTurnContextBuilder,
    TurnContextBuildInput,
)
from orket.application.services.orchestrator_failure_handler import OrchestratorFailureHandler
from orket.application.workflows.turn_executor import TurnExecutor
from orket.core.cards_runtime_contract import apply_epic_cards_runtime_defaults, resolve_cards_runtime
from orket.core.domain.guard_review import GuardReviewPayload
from orket.core.domain.state_machine import StateMachine
from orket.core.domain.workitem_transition import WorkItemTransitionService
from orket.core.policies.tool_gate import ToolGate
from orket.decision_nodes.contracts import PlanningInput
from orket.exceptions import CardNotFound, ExecutionFailed
from orket.logging import log_event
from orket.orchestration.models import ModelSelector
from orket.runtime.settings import resolve_bool, resolve_str
from orket.runtime_paths import resolve_control_plane_db_path
from orket.schema import (
    CardStatus,
    EnvironmentConfig,
    EpicConfig,
    IssueConfig,
    RoleConfig,
    SeatConfig,
    TeamConfig,
    WaitReason,
)
from orket.settings import (
    load_user_preferences as _load_user_preferences,
)
from orket.settings import (
    load_user_preferences_async,
    load_user_settings,
    load_user_settings_async,
    set_runtime_settings_context,
)
from orket.tools import ToolBox
from orket.utils import sanitize_name

load_user_preferences = _load_user_preferences

__all__ = [
    "DependencyManager",
    "DependencyValidationError",
    "DeploymentPlanner",
    "DeploymentValidationError",
    "PromptCompiler",
    "PromptResolver",
    "RuntimeVerifier",
    "Scaffolder",
    "ScaffoldValidationError",
    "load_user_preferences",
    "load_user_settings",
]


async def _close_provider_transport(provider: Any) -> None:
    close_method = getattr(provider, "close", None)
    if not callable(close_method):
        return
    maybe_awaitable = close_method()
    if inspect.isawaitable(maybe_awaitable):
        await maybe_awaitable


def _select_prompt_strategy_model(
    *,
    prompt_strategy_node: Any,
    role: str,
    asset_config: Any,
    override: str | None,
) -> str:
    select_model = prompt_strategy_node.select_model
    override_token = str(override or "").strip()
    if not override_token:
        return str(select_model(role=role, asset_config=asset_config))
    try:
        signature = inspect.signature(select_model)
    except (TypeError, ValueError):
        signature = None
    if signature is not None:
        parameters = signature.parameters
        if "override" in parameters or any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
        ):
            return str(select_model(role=role, asset_config=asset_config, override=override_token))
    return str(select_model(role=role, asset_config=asset_config))


def _should_suppress_reference_context_for_cards_runtime(cards_runtime: dict[str, Any] | None) -> bool:
    runtime = dict(cards_runtime or {})
    profile = str(runtime.get("execution_profile") or runtime.get("base_execution_profile") or "").strip().lower()
    if not profile:
        return False
    artifact_contract = runtime.get("artifact_contract")
    if not isinstance(artifact_contract, dict):
        return False
    has_explicit_paths = any(
        bool(artifact_contract.get(key))
        for key in ("required_read_paths", "required_write_paths", "review_read_paths")
    )
    return has_explicit_paths or bool(runtime.get("scenario_truth"))


def _org_process_rules(org: Any) -> dict[str, Any]:
    process_rules = getattr(org, "process_rules", None) if org else None
    return process_rules if isinstance(process_rules, dict) else {}


def _user_settings(self: Any) -> dict[str, Any]:
    return self.support_services.load_user_settings()


def _normalize_wait_reason_token(value: Any) -> str | None:
    if value is None:
        return None
    token = value.value if hasattr(value, "value") else value
    normalized = str(token).strip().lower()
    return normalized or None


def _set_issue_runtime_retry_note(issue: IssueConfig, note: str | None) -> None:
    params = dict(getattr(issue, "params", None) or {})
    token = str(note or "").strip()
    if token:
        params["runtime_retry_note"] = token
    else:
        params.pop("runtime_retry_note", None)
    issue.params = params


def _clear_issue_runtime_retry_note(issue: IssueConfig) -> None:
    _set_issue_runtime_retry_note(issue, None)


def _resolve_transition_wait_reason(
    *,
    target_status: CardStatus,
    reason: str,
    metadata: dict[str, Any] | None,
) -> str | None:
    if isinstance(metadata, dict):
        explicit = _normalize_wait_reason_token(metadata.get("wait_reason"))
        if explicit is not None:
            return explicit

    if target_status == CardStatus.BLOCKED:
        mapping = {
            "dependency_blocked": WaitReason.DEPENDENCY.value,
            "runtime_guard_terminal_failure": WaitReason.REVIEW.value,
            "catastrophic_failure": WaitReason.SYSTEM.value,
            "governance_violation": WaitReason.SYSTEM.value,
            "team_replan_limit_exceeded": WaitReason.SYSTEM.value,
        }
        return mapping.get(reason, WaitReason.SYSTEM.value)

    return None


def _apply_issue_transition_locally(
    *,
    issue: IssueConfig,
    target_status: CardStatus,
    assignee: str | None,
    wait_reason: str | None,
) -> None:
    issue.status = target_status
    if assignee is not None and hasattr(issue, "assignee"):
        issue.assignee = assignee
    if hasattr(issue, "wait_reason"):
        issue.wait_reason = WaitReason(wait_reason) if wait_reason else None


def _resolve_architecture_mode(self: Any) -> str:
    user_settings = _user_settings(self)
    raw = resolve_str(
        "ORKET_ARCHITECTURE_MODE",
        process_rules=_org_process_rules(self.org),
        process_key="architecture_mode",
        user_key="architecture_mode",
        user_settings=user_settings,
    )
    return str(resolve_architecture_mode(raw, "", ""))


def _resolve_frontend_framework_mode(self: Any) -> str:
    user_settings = _user_settings(self)
    raw = resolve_str(
        "ORKET_FRONTEND_FRAMEWORK_MODE",
        process_rules=_org_process_rules(self.org),
        process_key="frontend_framework_mode",
        user_key="frontend_framework_mode",
        user_settings=user_settings,
    )
    return str(resolve_frontend_framework_mode(raw, "", ""))


def _resolve_architecture_pattern(self: Any) -> str | None:
    mode = self._resolve_architecture_mode()
    if mode == "force_microservices":
        return "microservices"
    if mode == "force_monolith":
        return "monolith"
    return None


def _resolve_project_surface_profile(self: Any) -> str:
    user_settings = _user_settings(self)
    raw = resolve_str(
        "ORKET_PROJECT_SURFACE_PROFILE",
        process_rules=_org_process_rules(self.org),
        process_key="project_surface_profile",
        user_key="project_surface_profile",
        user_settings=user_settings,
    )
    return str(resolve_project_surface_profile(raw, "", ""))


def _resolve_small_project_builder_variant(self: Any) -> str:
    user_settings = _user_settings(self)
    raw = resolve_str(
        "ORKET_SMALL_PROJECT_BUILDER_VARIANT",
        process_rules=_org_process_rules(self.org),
        process_key="small_project_builder_variant",
        user_key="small_project_builder_variant",
        user_settings=user_settings,
    )
    return str(resolve_small_project_builder_variant(raw, "", ""))


def _resolve_protocol_governed_enabled(self: Any) -> bool:
    user_settings = _user_settings(self)
    return bool(resolve_bool(
        "ORKET_PROTOCOL_GOVERNED_ENABLED",
        "ORKET_PROTOCOL_GOVERNED",
        process_rules=_org_process_rules(self.org),
        process_key="protocol_governed_enabled",
        user_key="protocol_governed_enabled",
        user_settings=user_settings,
        default=False,
    ))


def _resolve_protocol_max_response_bytes(self: Any) -> int:
    user_settings = _user_settings(self)
    raw = resolve_str(
        "ORKET_PROTOCOL_MAX_RESPONSE_BYTES",
        process_rules=_org_process_rules(self.org),
        process_key="protocol_max_response_bytes",
        user_key="protocol_max_response_bytes",
        user_settings=user_settings,
    )
    if raw:
        try:
            return max(256, int(raw))
        except (TypeError, ValueError):
            pass
    return 8192


def _resolve_protocol_max_tool_calls(self: Any) -> int:
    user_settings = _user_settings(self)
    raw = resolve_str(
        "ORKET_PROTOCOL_MAX_TOOL_CALLS",
        process_rules=_org_process_rules(self.org),
        process_key="protocol_max_tool_calls",
        user_key="protocol_max_tool_calls",
        user_settings=user_settings,
    )
    if raw:
        try:
            return max(1, int(raw))
        except (TypeError, ValueError):
            pass
    return 8


def _resolve_protocol_determinism_context(self: Any) -> dict[str, Any]:
    process_rules = _org_process_rules(self.org)
    user_settings = _user_settings(self)
    controls = resolve_protocol_determinism_controls(
        timezone_values=[
            resolve_str(
                "ORKET_PROTOCOL_TIMEZONE",
                process_rules=process_rules,
                process_key="protocol_timezone",
                user_key="protocol_timezone",
                user_settings=user_settings,
            )
        ],
        locale_values=[
            resolve_str(
                "ORKET_PROTOCOL_LOCALE",
                process_rules=process_rules,
                process_key="protocol_locale",
                user_key="protocol_locale",
                user_settings=user_settings,
            )
        ],
        network_mode_values=[
            resolve_str(
                "ORKET_PROTOCOL_NETWORK_MODE",
                process_rules=process_rules,
                process_key="protocol_network_mode",
                user_key="protocol_network_mode",
                user_settings=user_settings,
            )
        ],
        network_allowlist_values=[
            resolve_str(
                "ORKET_PROTOCOL_NETWORK_ALLOWLIST",
                process_rules=process_rules,
                process_key="protocol_network_allowlist",
                user_key="protocol_network_allowlist",
                user_settings=user_settings,
            )
        ],
        clock_mode_values=[
            resolve_str(
                "ORKET_PROTOCOL_CLOCK_MODE",
                process_rules=process_rules,
                process_key="protocol_clock_mode",
                user_key="protocol_clock_mode",
                user_settings=user_settings,
            )
        ],
        clock_artifact_ref_values=[
            resolve_str(
                "ORKET_PROTOCOL_CLOCK_ARTIFACT_REF",
                process_rules=process_rules,
                process_key="protocol_clock_artifact_ref",
                user_key="protocol_clock_artifact_ref",
                user_settings=user_settings,
            )
        ],
        env_allowlist_values=[
            resolve_str(
                "ORKET_PROTOCOL_ENV_ALLOWLIST",
                process_rules=process_rules,
                process_key="protocol_env_allowlist",
                user_key="protocol_env_allowlist",
                user_settings=user_settings,
            )
        ],
    )
    return {
        "timezone": str(controls.get("timezone") or "UTC"),
        "locale": str(controls.get("locale") or "C.UTF-8"),
        "network_mode": str(controls.get("network_mode") or "off"),
        "network_allowlist_values": list(controls.get("network_allowlist") or []),
        "network_allowlist_hash": str(controls.get("network_allowlist_hash") or ""),
        "clock_mode": str(controls.get("clock_mode") or "wall"),
        "clock_artifact_ref": str(controls.get("clock_artifact_ref") or ""),
        "clock_artifact_hash": str(controls.get("clock_artifact_hash") or ""),
        "env_allowlist": dict(controls.get("env_snapshot") or {}),
        "env_allowlist_values": list(controls.get("env_allowlist") or []),
        "env_allowlist_hash": str(controls.get("env_allowlist_hash") or ""),
    }


def _resolve_local_prompting_mode(self: Any) -> str:
    process_rules = _org_process_rules(self.org)
    user_settings = _user_settings(self)
    return str(resolve_local_prompting_mode(
        resolve_str(
            "ORKET_LOCAL_PROMPTING_MODE",
            process_rules=process_rules,
            process_key="local_prompting_mode",
            user_key="local_prompting_mode",
            user_settings=user_settings,
        ),
        "",
        "",
    ))


def _resolve_local_prompting_allow_fallback(self: Any) -> bool:
    process_rules = _org_process_rules(self.org)
    user_settings = _user_settings(self)
    return bool(
        resolve_local_prompting_allow_fallback(
            resolve_str(
                "ORKET_LOCAL_PROMPTING_ALLOW_FALLBACK",
                process_rules=process_rules,
                process_key="local_prompting_allow_fallback",
                user_key="local_prompting_allow_fallback",
                user_settings=user_settings,
            ),
            "",
            "",
        )
    )


def _resolve_local_prompting_fallback_profile_id(self: Any) -> str:
    process_rules = _org_process_rules(self.org)
    user_settings = _user_settings(self)
    return str(resolve_local_prompting_fallback_profile_id(
        resolve_str(
            "ORKET_LOCAL_PROMPTING_FALLBACK_PROFILE_ID",
            process_rules=process_rules,
            process_key="local_prompting_fallback_profile_id",
            user_key="local_prompting_fallback_profile_id",
            user_settings=user_settings,
        ),
        "",
        "",
    ))


def _resolve_workflow_profile(self: Any) -> str:
    process_rules = _org_process_rules(self.org)
    raw = resolve_str(
        "ORKET_WORKFLOW_PROFILE",
        process_rules=process_rules,
        process_key="workflow_profile",
    ).lower()
    if raw in {"legacy_cards_v1", "project_task_v1"}:
        return raw
    default_raw = resolve_str(
        "ORKET_WORKFLOW_PROFILE_DEFAULT",
        process_rules=process_rules,
        process_key="workflow_profile_default",
    ).lower()
    if default_raw in {"legacy_cards_v1", "project_task_v1"}:
        return default_raw
    return "legacy_cards_v1"


async def _request_issue_transition(
    self: Any,
    *,
    issue: IssueConfig,
    target_status: CardStatus,
    reason: str,
    assignee: str | None = None,
    metadata: dict[str, Any] | None = None,
    roles: list[str] | None = None,
    allow_policy_override: bool = True,
) -> None:
    current_status = (
        issue.status if isinstance(issue.status, CardStatus) else CardStatus(str(issue.status).strip().lower())
    )
    wait_reason = _resolve_transition_wait_reason(
        target_status=target_status,
        reason=reason,
        metadata=metadata,
    )
    metadata_payload = dict(metadata or {})
    if wait_reason is not None and "wait_reason" not in metadata_payload:
        metadata_payload["wait_reason"] = wait_reason

    if current_status == target_status:
        await self.async_cards.update_status(
            issue.id,
            target_status,
            assignee=assignee,
            reason=reason,
            metadata=metadata_payload or None,
        )
        _apply_issue_transition_locally(
            issue=issue,
            target_status=target_status,
            assignee=assignee,
            wait_reason=wait_reason,
        )
        await _publish_issue_control_plane_transition(
            self,
            issue=issue,
            current_status=current_status,
            target_status=target_status,
            reason=reason,
            assignee=assignee,
            metadata_payload=metadata_payload,
        )
        return

    transition_service = WorkItemTransitionService(
        workflow_profile=self._resolve_workflow_profile(),
    )
    payload = {"status": target_status.value, "wait_reason": wait_reason}
    transition = transition_service.request_transition(
        action="set_status",
        current_status=current_status,
        payload=payload,
        roles=roles or ["system"],
    )
    if not transition.ok and allow_policy_override:
        transition = transition_service.request_transition(
            action="system_set_status",
            current_status=current_status,
            payload={"status": target_status.value, "reason": reason, "wait_reason": wait_reason},
            roles=["system"],
        )
    if not transition.ok:
        raise ExecutionFailed(
            "Transition rejected for issue "
            f"{issue.id}: {transition.error_code.value if transition.error_code else 'UNKNOWN'} "
            f"{transition.error or ''}".strip()
        )

    await self.async_cards.update_status(
        issue.id,
        target_status,
        assignee=assignee,
        reason=reason,
        metadata=metadata_payload or None,
    )
    _apply_issue_transition_locally(
        issue=issue,
        target_status=target_status,
        assignee=assignee,
        wait_reason=wait_reason,
    )
    await _publish_issue_control_plane_transition(
        self,
        issue=issue,
        current_status=current_status,
        target_status=target_status,
        reason=reason,
        assignee=assignee,
        metadata_payload=metadata_payload,
    )
    issue.status = target_status


async def _publish_issue_control_plane_transition(
    self: Any,
    *,
    issue: IssueConfig,
    current_status: CardStatus,
    target_status: CardStatus,
    reason: str,
    assignee: str | None,
    metadata_payload: dict[str, Any],
) -> None:
    session_id = str(metadata_payload.get("run_id") or "").strip()
    if not session_id:
        return
    handled_by_dispatch = False
    issue_control_plane = getattr(self, "issue_control_plane", None)
    if issue_control_plane is not None:
        handled_by_dispatch = await issue_control_plane.publish_issue_transition(
            session_id=session_id,
            issue_id=issue.id,
            current_status=current_status,
            target_status=target_status,
            reason=reason,
            assignee=assignee,
            turn_index=metadata_payload.get("turn_index"),
            review_turn=bool(metadata_payload.get("review_turn", False)),
        )
    scheduler_control_plane = getattr(self, "scheduler_control_plane", None)
    if scheduler_control_plane is None or handled_by_dispatch or str(reason or "").strip().lower() == "turn_dispatch":
        return
    await scheduler_control_plane.publish_scheduler_transition(
        session_id=session_id,
        issue_id=issue.id,
        current_status=current_status,
        target_status=target_status,
        reason=reason,
        assignee=assignee,
        metadata=metadata_payload,
    )


def _small_project_issue_threshold(self: Any) -> int:
    raw = 3
    if self.org and isinstance(getattr(self.org, "process_rules", None), dict):
        raw = self.org.process_rules.get("small_project_issue_threshold", 3)
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 3


def _should_auto_inject_small_project_reviewer(self: Any) -> bool:
    return bool(resolve_bool(
        "ORKET_SMALL_PROJECT_AUTO_INJECT_REVIEWER",
        process_rules=_org_process_rules(self.org),
        process_key="small_project_auto_inject_code_reviewer",
        default=False,
    ))


def _small_project_reviewer_seat_name(self: Any) -> str:
    if self.org and isinstance(getattr(self.org, "process_rules", None), dict):
        configured = str(
            self.org.process_rules.get(
                "small_project_auto_inject_reviewer_seat_name",
                "auto_code_reviewer",
            )
            or ""
        ).strip()
        if configured:
            return configured
    return "auto_code_reviewer"


def _auto_inject_small_project_reviewer_seat(self: Any, team: TeamConfig) -> str:
    seat_name = self._small_project_reviewer_seat_name()
    seats = getattr(team, "seats", {}) or {}
    existing = seats.get(seat_name)
    if existing is None:
        seats[seat_name] = SeatConfig(
            name="Auto Injected Code Reviewer",
            roles=["code_reviewer"],
        )
        return str(seat_name)

    existing_roles = list(getattr(existing, "roles", []) or [])
    normalized_roles = {str(role).strip().lower() for role in existing_roles if str(role).strip()}
    if "code_reviewer" not in normalized_roles:
        existing.roles = existing_roles + ["code_reviewer"]
    return str(seat_name)


def _resolve_small_project_team_policy(self: Any, epic: Any, team: Any) -> dict[str, Any]:
    issue_count = len(list(getattr(epic, "issues", []) or []))
    threshold = self._small_project_issue_threshold()
    active = 0 < issue_count <= threshold
    variant = self._resolve_small_project_builder_variant()
    builder_role = variant if variant in {"coder", "architect"} else "coder"

    reviewer_seat = next(
        (
            seat_name
            for seat_name, seat_obj in (getattr(team, "seats", {}) or {}).items()
            if "code_reviewer" in list(getattr(seat_obj, "roles", []) or [])
        ),
        None,
    )
    builder_role_aliases = {builder_role}
    if builder_role == "architect":
        builder_role_aliases.add("lead_architect")
    builder_seat = next(
        (
            seat_name
            for seat_name, seat_obj in (getattr(team, "seats", {}) or {}).items()
            if builder_role_aliases.intersection(
                {str(role).strip() for role in list(getattr(seat_obj, "roles", []) or []) if str(role).strip()}
            )
        ),
        builder_role,
    )

    return {
        "active": bool(active),
        "issue_count": issue_count,
        "threshold": threshold,
        "variant": variant,
        "builder_role": builder_role,
        "builder_seat": builder_seat,
        "reviewer_seat": reviewer_seat,
    }


def _resolve_bool_flag(self: Any, env_key: str, org_key: str, default: bool = False) -> bool:
    return bool(resolve_bool(
        env_key,
        process_rules=_org_process_rules(self.org),
        process_key=org_key,
        default=default,
    ))


def _is_sandbox_disabled(self: Any) -> bool:
    return bool(self._resolve_bool_flag("ORKET_DISABLE_SANDBOX", "disable_sandbox"))


def _is_scaffolder_disabled(self: Any) -> bool:
    return bool(self._resolve_bool_flag("ORKET_DISABLE_SCAFFOLDER", "disable_scaffolder"))


def _is_dependency_manager_disabled(self: Any) -> bool:
    return bool(self._resolve_bool_flag("ORKET_DISABLE_DEPENDENCY_MANAGER", "disable_dependency_manager"))


def _is_runtime_verifier_disabled(self: Any) -> bool:
    return bool(self._resolve_bool_flag("ORKET_DISABLE_RUNTIME_VERIFIER", "disable_runtime_verifier"))


def _is_deployment_planner_disabled(self: Any) -> bool:
    return bool(self._resolve_bool_flag("ORKET_DISABLE_DEPLOYMENT_PLANNER", "disable_deployment_planner"))


def _resolve_prompt_resolver_mode(self: Any) -> str:
    value = resolve_str(
        "ORKET_PROMPT_RESOLVER_MODE",
        process_rules=_org_process_rules(self.org),
        process_key="prompt_resolver_mode",
    ).lower()
    if value in {"resolver", "compiler"}:
        return value
    return "compiler"


def _resolve_prompt_selection_policy(self: Any) -> str:
    value = resolve_str(
        "ORKET_PROMPT_SELECTION_POLICY",
        process_rules=_org_process_rules(self.org),
        process_key="prompt_selection_policy",
    ).lower()
    if value in {"stable", "canary", "exact"}:
        return value
    return "stable"


def _resolve_prompt_selection_strict(self: Any) -> bool:
    return bool(resolve_bool(
        "ORKET_PROMPT_SELECTION_STRICT",
        process_rules=_org_process_rules(self.org),
        process_key="prompt_selection_strict",
        default=True,
    ))


def _resolve_prompt_version_exact(self: Any) -> str:
    return str(resolve_str(
        "ORKET_PROMPT_VERSION_EXACT",
        process_rules=_org_process_rules(self.org),
        process_key="prompt_version_exact",
    ))


def _resolve_prompt_patch(self: Any) -> str:
    return str(resolve_str(
        "ORKET_PROMPT_PATCH",
        process_rules=_org_process_rules(self.org),
        process_key="prompt_patch",
    ))


def _resolve_prompt_patch_label(self: Any) -> str:
    return str(resolve_str(
        "ORKET_PROMPT_PATCH_LABEL",
        process_rules=_org_process_rules(self.org),
        process_key="prompt_patch_label",
    ))


def _resolve_verification_scope_limits(self: Any) -> dict[str, int | None]:
    defaults: dict[str, int | None] = {
        "max_workspace_items": None,
        "max_active_context_items": None,
        "max_passive_context_items": None,
        "max_archived_context_items": None,
        "max_total_context_items": None,
    }
    if not (self.org and isinstance(getattr(self.org, "process_rules", None), dict)):
        return defaults
    raw = self.org.process_rules.get("verification_scope_limits")
    if not isinstance(raw, dict):
        return defaults

    resolved = dict(defaults)
    for key in list(defaults.keys()):
        value = raw.get(key)
        if value is None:
            continue
        try:
            resolved[key] = max(0, int(value))
        except (TypeError, ValueError):
            resolved[key] = None
    return resolved


def _history_context(self: Any, seat_name: str | None = None) -> list[dict[str, str]]:
    history_rows = self.transcript[-self.context_window :]
    normalized_seat = str(seat_name or "").strip().lower()
    if normalized_seat:
        history_rows = [
            row for row in history_rows if str(getattr(row, "role", "") or "").strip().lower() == normalized_seat
        ]
    return [
        {
            "role": str(getattr(row, "role", "") or "").strip(),
            "content": str(getattr(row, "content", "") or ""),
        }
        for row in history_rows
    ]


async def verify_issue(self: Any, issue_id: str, run_id: str | None = None) -> Any:
    """
    Runs empirical verification for a specific issue.
    """
    from orket.core.domain.sandbox import SandboxStatus
    from orket.core.domain.verification import VerificationEngine

    # 1. Load the latest IssueConfig from DB
    issue_data = await self.async_cards.get_by_id(issue_id)
    if not issue_data:
        from orket.exceptions import CardNotFound

        raise CardNotFound(f"Cannot verify non-existent issue {issue_id}")

    if hasattr(issue_data, "model_dump"):
        issue_payload = issue_data.model_dump()
    elif isinstance(issue_data, dict):
        issue_payload = dict(issue_data)
    else:
        issue_payload = dict(getattr(issue_data, "__dict__", {}))
    issue = IssueConfig.model_validate(issue_payload)

    # 2. Execute Verification (Fixtures)
    verification_event = {"issue_id": issue_id}
    if run_id:
        verification_event["run_id"] = run_id
    log_event("verification_started", verification_event, self.workspace)
    result = await asyncio.to_thread(VerificationEngine.verify, issue.verification, self.workspace)

    # 3. Optional: Execute Sandbox Verification (HTTP)
    rock_id = issue.build_id
    sandbox = self.sandbox_orchestrator.registry.get(f"sandbox-{rock_id}")
    if sandbox and sandbox.status == SandboxStatus.RUNNING:
        sandbox_event = {"issue_id": issue_id}
        if run_id:
            sandbox_event["run_id"] = run_id
        log_event("verification_sandbox_started", sandbox_event, self.workspace)
        sb_result = await VerificationEngine.verify_sandbox(sandbox, issue.verification)
        # Merge results
        result.passed += sb_result.passed
        result.failed += sb_result.failed
        result.total_scenarios += sb_result.total_scenarios
        result.logs.extend(sb_result.logs)

    # 4. Update the Issue with the new verification state
    issue.verification.last_run = result
    await self.async_cards.save(issue.model_dump())
    return result


async def _trigger_sandbox(self: Any, epic: EpicConfig, run_id: str | None = None) -> None:
    """Helper to trigger sandbox deployment with per-epic locking."""
    from orket.core.domain.sandbox import SandboxStatus, TechStack

    rock_id = epic.parent_id or epic.id
    if rock_id in self._sandbox_failed_rocks:
        return

    async with self._sandbox_locks[rock_id]:
        if rock_id in self._sandbox_failed_rocks:
            return
        # Double-check if already running under the lock
        existing = self.sandbox_orchestrator.registry.get(f"sandbox-{rock_id}")
        if existing and existing.status == SandboxStatus.RUNNING:
            return

        deploy_start = {"rock_id": rock_id}
        if run_id:
            deploy_start["run_id"] = run_id
        log_event("sandbox_deploy_started", deploy_start, self.workspace)
        try:
            await self.sandbox_orchestrator.create_sandbox(
                rock_id=rock_id,
                project_name=epic.name,
                tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
                workspace_path=str(self.workspace),
            )
        except (RuntimeError, ValueError, OSError) as e:
            self._sandbox_failed_rocks.add(rock_id)
            deploy_failed = {"rock_id": rock_id, "error": str(e)}
            if run_id:
                deploy_failed["run_id"] = run_id
            log_event("sandbox_deploy_failed", deploy_failed, self.workspace)


async def execute_epic(
    self: Any,
    active_build: str,
    run_id: str,
    epic: EpicConfig,
    team: TeamConfig,
    env: EnvironmentConfig,
    target_issue_id: str | None = None,
    resume_mode: bool = False,
    model_override: str | None = None,
) -> None:
    """
    Main execution loop for an Epic.
    Executes independent issues in parallel using a TAG-based DAG.
    """
    user_settings = await load_user_settings_async()
    preferences = await load_user_preferences_async()
    set_runtime_settings_context(user_settings=user_settings, user_preferences=preferences)

    small_policy = self._resolve_small_project_team_policy(epic, team)
    if (
        small_policy["active"]
        and not small_policy["reviewer_seat"]
        and self._should_auto_inject_small_project_reviewer()
    ):
        injected_seat = self._auto_inject_small_project_reviewer_seat(team)
        log_event(
            "team_policy_auto_injected_code_reviewer",
            {
                "run_id": run_id,
                "epic": epic.name,
                "injected_seat": injected_seat,
                "reason": "small_project_missing_code_reviewer",
            },
            self.workspace,
        )
        small_policy = self._resolve_small_project_team_policy(epic, team)
    if small_policy["active"] and not small_policy["reviewer_seat"]:
        available_seats = sorted((getattr(team, "seats", {}) or {}).keys())
        log_event(
            "team_policy_preflight_failed",
            {
                "run_id": run_id,
                "epic": epic.name,
                "reason": "missing_code_reviewer_seat",
                "small_project_policy": small_policy,
                "available_seats": available_seats,
            },
            self.workspace,
        )
        raise ExecutionFailed(
            "Small-project policy preflight failed: missing code_reviewer seat. "
            f"Available seats={available_seats}. Add a seat with role 'code_reviewer' "
            "or increase small_project_issue_threshold to disable small-team mode for this epic."
        )
    log_event(
        "team_selection_decision",
        {
            "run_id": run_id,
            "epic": epic.name,
            "active": small_policy["active"],
            "variant": small_policy["variant"],
            "builder_role": small_policy["builder_role"],
            "builder_seat": small_policy["builder_seat"],
            "reviewer_seat": small_policy["reviewer_seat"],
            "issue_count": small_policy["issue_count"],
            "issue_threshold": small_policy["threshold"],
        },
        self.workspace,
    )
    if self._is_scaffolder_disabled():
        log_event("scaffolder_skipped_policy", {"run_id": run_id, "epic": epic.name}, self.workspace)
    else:
        log_event("scaffolder_started", {"run_id": run_id, "epic": epic.name}, self.workspace)
        project_surface_profile = self._resolve_project_surface_profile()
        architecture_pattern = self._resolve_architecture_pattern()
        scaffolder = self.support_services.create_scaffolder(
            workspace_root=self.workspace,
            organization=self.org,
            project_surface_profile=project_surface_profile,
            architecture_pattern=architecture_pattern,
        )
        try:
            scaffold_result = await scaffolder.ensure()
        except ScaffoldValidationError as exc:
            log_event(
                "scaffolder_failed",
                {"run_id": run_id, "epic": epic.name, "error": str(exc)},
                self.workspace,
            )
            raise ExecutionFailed(f"Scaffolder validation failed: {exc}") from exc
        log_event(
            "scaffolder_completed",
            {
                "run_id": run_id,
                "epic": epic.name,
                "created_directories": len(scaffold_result.get("created_directories", [])),
                "created_files": len(scaffold_result.get("created_files", [])),
            },
            self.workspace,
        )

    if self._is_dependency_manager_disabled():
        log_event("dependency_manager_skipped_policy", {"run_id": run_id, "epic": epic.name}, self.workspace)
    else:
        log_event("dependency_manager_started", {"run_id": run_id, "epic": epic.name}, self.workspace)
        project_surface_profile = self._resolve_project_surface_profile()
        architecture_pattern = self._resolve_architecture_pattern()
        dependency_manager = self.support_services.create_dependency_manager(
            workspace_root=self.workspace,
            organization=self.org,
            project_surface_profile=project_surface_profile,
            architecture_pattern=architecture_pattern,
        )
        try:
            dependency_result = await dependency_manager.ensure()
        except DependencyValidationError as exc:
            log_event(
                "dependency_manager_failed",
                {"run_id": run_id, "epic": epic.name, "error": str(exc)},
                self.workspace,
            )
            raise ExecutionFailed(f"Dependency manager validation failed: {exc}") from exc
        log_event(
            "dependency_manager_completed",
            {
                "run_id": run_id,
                "epic": epic.name,
                "created_files": len(dependency_result.get("created_files", [])),
            },
            self.workspace,
        )

    if self._is_deployment_planner_disabled():
        log_event("deployment_planner_skipped_policy", {"run_id": run_id, "epic": epic.name}, self.workspace)
    else:
        log_event("deployment_planner_started", {"run_id": run_id, "epic": epic.name}, self.workspace)
        project_surface_profile = self._resolve_project_surface_profile()
        architecture_pattern = self._resolve_architecture_pattern()
        deployment_planner = self.support_services.create_deployment_planner(
            workspace_root=self.workspace,
            organization=self.org,
            project_surface_profile=project_surface_profile,
            architecture_pattern=architecture_pattern,
        )
        try:
            deployment_result = await deployment_planner.ensure()
        except DeploymentValidationError as exc:
            log_event(
                "deployment_planner_failed",
                {"run_id": run_id, "epic": epic.name, "error": str(exc)},
                self.workspace,
            )
            raise ExecutionFailed(f"Deployment planner validation failed: {exc}") from exc
        log_event(
            "deployment_planner_completed",
            {
                "run_id": run_id,
                "epic": epic.name,
                "created_files": len(deployment_result.get("created_files", [])),
            },
            self.workspace,
        )

    # 1. Setup Execution Environment
    model_selector = ModelSelector(
        organization=self.org,
        preferences=preferences,
        user_settings=user_settings,
    )
    prompt_strategy_node = self.decision_nodes.resolve_prompt_strategy(model_selector, self.org)

    tool_gate = ToolGate(organization=self.org, workspace_root=self.workspace)
    from orket.application.services.turn_tool_control_plane_service import build_turn_tool_control_plane_service
    runtime_db_path = Path(self.db_path)
    if not runtime_db_path.is_absolute():
        runtime_db_path = Path(self.workspace) / runtime_db_path
    turn_tool_control_plane_db_path = resolve_control_plane_db_path(
        runtime_db_path.with_name("control_plane_records.sqlite3")
    )

    executor = TurnExecutor(
        StateMachine(),
        tool_gate,
        self.workspace,
        control_plane_service=build_turn_tool_control_plane_service(turn_tool_control_plane_db_path),
    )

    from orket.policy import create_session_policy

    policy = create_session_policy(str(self.workspace), epic.references)
    toolbox = ToolBox(
        policy,
        str(self.workspace),
        epic.references,
        db_path=self.db_path,
        cards_repo=self.async_cards,
        tool_gate=tool_gate,
        organization=self.org,
        decision_nodes=self.decision_nodes,
    )

    # Concurrency/loop control via loop policy node.
    concurrency_limit = self.loop_policy_node.concurrency_limit(self.org)
    semaphore = asyncio.Semaphore(concurrency_limit)

    log_event(
        "orchestrator_hyper_loop_start",
        {"epic": epic.name, "run_id": run_id, "concurrency": concurrency_limit},
        self.workspace,
    )

    iteration_count = 0
    max_iterations = self.loop_policy_node.max_iterations(self.org)

    while iteration_count < max_iterations:
        iteration_count += 1

        backlog = await self.async_cards.get_by_build(active_build)
        if await self._maybe_schedule_team_replan(backlog, run_id, active_build, team):
            continue
        independent_ready = await self.async_cards.get_independent_ready_issues(active_build)
        candidates = self.planner_node.plan(
            PlanningInput(
                backlog=backlog,
                independent_ready=independent_ready,
                target_issue_id=target_issue_id,
            )
        )

        if not candidates:
            propagated_count = await self._propagate_dependency_blocks(backlog, run_id)
            if propagated_count:
                continue

            # Empty-candidate policy (seam) with backward-compatible fallback.
            outcome_fn = getattr(self.loop_policy_node, "no_candidate_outcome", None)
            if callable(outcome_fn):
                outcome = outcome_fn(backlog)
            else:
                is_done = self.loop_policy_node.is_backlog_done(backlog)
                outcome = {"is_done": is_done, "event_name": "orchestrator_epic_complete" if is_done else None}

            if outcome.get("is_done"):
                event_name = outcome.get("event_name")
                if event_name:
                    log_event(event_name, {"epic": epic.name, "run_id": run_id}, self.workspace)
                break

            backlog_snapshot = [
                {
                    "id": getattr(item, "id", "unknown"),
                    "status": (
                        getattr(item.status, "value", str(item.status)) if hasattr(item, "status") else "unknown"
                    ),
                }
                for item in backlog
            ]
            reason = outcome.get("reason") or "No executable candidates while backlog incomplete."
            log_event(
                "orchestrator_stalled",
                {
                    "run_id": run_id,
                    "epic": epic.name,
                    "iteration": iteration_count,
                    "reason": reason,
                    "backlog": backlog_snapshot,
                },
                self.workspace,
            )
            raise ExecutionFailed(reason)

        log_event(
            "orchestrator_tick",
            {"run_id": run_id, "candidate_count": len(candidates), "iteration": iteration_count},
            self.workspace,
        )

        # 2. Parallel Dispatch with Semaphore
        async def semaphore_wrapper(issue_data: Any) -> None:
            async with semaphore:
                await self._execute_issue_turn(
                    issue_data,
                    epic,
                    team,
                    env,
                    run_id,
                    active_build,
                    prompt_strategy_node,
                    executor,
                    toolbox,
                    resume_mode=resume_mode,
                    model_override=model_override,
                )

        await asyncio.gather(*(semaphore_wrapper(c) for c in candidates))

    if iteration_count >= max_iterations:
        final_backlog = await self.async_cards.get_by_build(active_build)
        exhaustion_fn = getattr(self.loop_policy_node, "should_raise_exhaustion", None)
        if callable(exhaustion_fn):
            should_raise = exhaustion_fn(iteration_count, max_iterations, final_backlog)
        else:
            should_raise = not self.loop_policy_node.is_backlog_done(final_backlog)
        if should_raise:
            raise ExecutionFailed(f"Hyper-Loop exhausted iterations ({max_iterations})")


async def _propagate_dependency_blocks(self: Any, backlog: list[Any], run_id: str) -> int:
    blocker_statuses = {CardStatus.BLOCKED, CardStatus.CANCELED, CardStatus.GUARD_REJECTED}
    status_by_id = {getattr(issue, "id", ""): getattr(issue, "status", None) for issue in backlog}
    propagated = []

    for issue in backlog:
        if getattr(issue, "status", None) != CardStatus.READY:
            continue
        depends_on = list(getattr(issue, "depends_on", []) or [])
        if not depends_on:
            continue
        blocked_by = [dep_id for dep_id in depends_on if status_by_id.get(dep_id) in blocker_statuses]
        if not blocked_by:
            continue

        await self._request_issue_transition(
            issue=issue,
            target_status=CardStatus.BLOCKED,
            reason="dependency_blocked",
            metadata={"run_id": run_id, "blocked_by": blocked_by},
        )
        propagated.append({"issue_id": issue.id, "blocked_by": blocked_by})

    if propagated:
        log_event(
            "dependency_block_propagated",
            {"run_id": run_id, "updates": propagated},
            self.workspace,
        )
    return len(propagated)


async def _maybe_schedule_team_replan(
    self: Any,
    backlog: list[Any],
    run_id: str,
    active_build: str,
    team: Any,
) -> bool:
    triggering_issues: list[Any] = []
    for issue in backlog:
        seat = str(getattr(issue, "seat", "") or "").strip().lower()
        if seat != "requirements_analyst":
            continue
        params = getattr(issue, "params", None)
        if isinstance(params, dict) and bool(params.get("replan_requested")):
            triggering_issues.append(issue)

    if not triggering_issues:
        return False

    current_count = int(self._team_replan_counts.get(run_id, 0))
    next_count = current_count + 1
    if next_count > 3:
        for issue in backlog:
            issue_id = getattr(issue, "id", None)
            if not issue_id:
                continue
            try:
                await self._request_issue_transition(
                    issue=issue,
                    target_status=CardStatus.BLOCKED,
                    reason="team_replan_limit_exceeded",
                    metadata={"run_id": run_id, "replan_count": current_count},
                )
            except (CardNotFound, ExecutionFailed, ValueError, TypeError, RuntimeError, OSError):
                continue
        log_event(
            "team_replan_terminal_failure",
            {
                "run_id": run_id,
                "active_build": active_build,
                "replan_count": current_count,
                "limit": 3,
            },
            self.workspace,
        )
        raise ExecutionFailed("TEAM_REPLAN_LIMIT_EXCEEDED: requirements changed too many times (limit=3).")

    self._team_replan_counts[run_id] = next_count
    run_prefix = sanitize_name(str(run_id or "run"))[:6].upper() or "RUN"
    replan_issue_id = f"REPLAN-{run_prefix}-{next_count}"
    small_policy = self._resolve_small_project_team_policy(
        SimpleNamespace(issues=backlog),
        team,
    )
    replan_seat = str(small_policy.get("builder_seat") or "architect")
    await self.async_cards.save(
        {
            "id": replan_issue_id,
            "summary": "Re-evaluate team composition after requirement change",
            "seat": replan_seat,
            "type": "issue",
            "status": CardStatus.READY,
            "priority": 3.0,
            "build_id": active_build,
            "session_id": run_id,
            "params": {
                "card_kind": "team_replan",
                "replan_count": next_count,
            },
        }
    )
    scheduler_control_plane = getattr(self, "scheduler_control_plane", None)
    if scheduler_control_plane is not None:
        await scheduler_control_plane.publish_child_issue_creation(
            session_id=run_id,
            issue_id=replan_issue_id,
            active_build=active_build,
            seat_name=replan_seat,
            relationship_class="team_replan",
            trigger_issue_ids=[str(getattr(item, "id", "") or "").strip() for item in triggering_issues],
            metadata={"replan_count": next_count},
        )
    for issue in triggering_issues:
        params = getattr(issue, "params", None)
        if isinstance(params, dict):
            params["replan_requested"] = False
        try:
            if hasattr(issue, "model_dump"):
                await self.async_cards.save(issue.model_dump())
            else:
                await self.async_cards.save(dict(issue.__dict__))
        except (CardNotFound, ExecutionFailed, ValueError, TypeError, RuntimeError, OSError):
            continue
    log_event(
        "team_replan_scheduled",
        {
            "run_id": run_id,
            "active_build": active_build,
            "replan_issue_id": replan_issue_id,
            "replan_count": next_count,
            "seat": replan_seat,
            "trigger_issue_ids": [getattr(item, "id", "") for item in triggering_issues],
        },
        self.workspace,
    )
    return True


async def _execute_issue_turn(
    self: Any,
    issue_data: Any,
    epic: EpicConfig,
    team: TeamConfig,
    env: EnvironmentConfig,
    run_id: str,
    active_build: str,
    prompt_strategy_node: Any,
    executor: TurnExecutor,
    toolbox: ToolBox,
    resume_mode: bool = False,
    model_override: str | None = None,
) -> None:
    """Executes a single turn for one issue."""
    issue = IssueConfig.model_validate(issue_data.model_dump())
    issue.params = apply_epic_cards_runtime_defaults(
        issue_params=getattr(issue, "params", None),
        epic_params=getattr(epic, "params", None),
    )
    cards_runtime = resolve_cards_runtime(issue=issue)
    is_review_turn = self.loop_policy_node.is_review_turn(issue.status)
    dependency_context = await self._build_dependency_context(issue)
    preflight = OrchestratorReviewPreflightService(
        workspace_root=self.workspace,
        organization=self.org,
        support_services=self.support_services,
        async_cards=self.async_cards,
        notes=self.notes,
        transcript=self.transcript,
        request_issue_transition=self._request_issue_transition,
        verify_issue=self.verify_issue,
        resolve_project_surface_profile=self._resolve_project_surface_profile,
        resolve_architecture_pattern=self._resolve_architecture_pattern,
        is_runtime_verifier_disabled=self._is_runtime_verifier_disabled,
        set_issue_runtime_retry_note=_set_issue_runtime_retry_note,
        clear_issue_runtime_retry_note=_clear_issue_runtime_retry_note,
    )
    preflight_result = await preflight.run(
        issue=issue,
        run_id=run_id,
        is_review_turn=is_review_turn,
        cards_runtime=cards_runtime,
    )
    runtime_result = preflight_result.runtime_result
    if preflight_result.stop_execution:
        return

    preparation_service = OrchestratorTurnPreparationService(
        workspace_root=self.workspace,
        organization=self.org,
        loader=self.loader,
        async_cards=self.async_cards,
        memory=self.memory,
        transcript=self.transcript,
        router_node=self.router_node,
        loop_policy_node=self.loop_policy_node,
        model_client_node=self.model_client_node,
        support_services=self.support_services,
        request_issue_transition=self._request_issue_transition,
        resolve_small_project_team_policy=self._resolve_small_project_team_policy,
        build_turn_context=self._build_turn_context,
        resolve_prompt_resolver_mode=self._resolve_prompt_resolver_mode,
        resolve_prompt_selection_policy=self._resolve_prompt_selection_policy,
        resolve_prompt_selection_strict=self._resolve_prompt_selection_strict,
        resolve_prompt_version_exact=self._resolve_prompt_version_exact,
        resolve_prompt_patch=self._resolve_prompt_patch,
        resolve_prompt_patch_label=self._resolve_prompt_patch_label,
        close_provider_transport=_close_provider_transport,
        select_prompt_strategy_model=_select_prompt_strategy_model,
        should_suppress_reference_context_for_cards_runtime=_should_suppress_reference_context_for_cards_runtime,
    )
    preparation = await preparation_service.prepare(
        data=TurnPreparationInput(
            issue=issue,
            epic=epic,
            team=team,
            env=env,
            run_id=run_id,
            prompt_strategy_node=prompt_strategy_node,
            dependency_context=dependency_context,
            runtime_result=runtime_result,
            resume_mode=resume_mode,
            model_override=model_override,
        )
    )
    if preparation.stop_execution:
        return
    seat_name = str(preparation.seat_name)
    roles_to_load = list(preparation.roles_to_load or [])
    turn_status = preparation.turn_status or CardStatus.IN_PROGRESS
    turn_index = int(preparation.turn_index or 1)
    is_guard_turn = bool(preparation.is_guard_turn)
    role_config = preparation.role_config
    provider = preparation.provider
    client = preparation.client
    context = dict(preparation.context or {})
    system_desc = str(preparation.system_prompt or "")
    try:
        log_event(
            "orchestrator_dispatch",
            {"run_id": run_id, "seat": seat_name, "issue_id": issue.id, "status": issue.status.value},
            self.workspace,
        )
        result = await self._dispatch_turn(
            executor=executor,
            issue=issue,
            role_config=role_config,
            client=client,
            toolbox=toolbox,
            context=context,
            system_prompt=system_desc,
        )

        if result.success:
            success_handler = OrchestratorTurnSuccessHandler(
                workspace_root=self.workspace,
                transcript=self.transcript,
                async_cards=self.async_cards,
                memory=self.memory,
                evaluator_node=self.evaluator_node,
                issue_control_plane=getattr(self, "issue_control_plane", None),
                request_issue_transition=self._request_issue_transition,
                trigger_sandbox=self._trigger_sandbox,
                is_sandbox_disabled=self._is_sandbox_disabled,
                save_checkpoint=self._save_checkpoint,
                create_pending_gate_request=self._create_pending_gate_request,
                validate_guard_rejection_payload=self._validate_guard_rejection_payload,
                extract_guard_review_payload=self._extract_guard_review_payload,
                resolve_guard_event=self._resolve_guard_event,
                handle_failure=self._handle_failure,
            )
            await success_handler.handle(
                issue=issue,
                result=result,
                provider=provider,
                run_id=run_id,
                seat_name=seat_name,
                roles_to_load=roles_to_load,
                turn_index=turn_index,
                turn_status=turn_status,
                is_guard_turn=is_guard_turn,
                is_review_turn=is_review_turn,
                epic=epic,
                team=team,
                env=env,
                active_build=active_build,
            )
        else:
            await self._handle_failure(
                issue,
                result,
                run_id,
                roles_to_load,
                turn_index=turn_index,
            )
    finally:
        await _close_provider_transport(provider)


def _validate_guard_rejection_payload(self: Any, payload: GuardReviewPayload) -> dict[str, Any]:
    validate_fn = getattr(self.loop_policy_node, "validate_guard_rejection_payload", None)
    if callable(validate_fn):
        try:
            return dict(validate_fn(payload=payload))
        except TypeError:
            return dict(validate_fn(payload))

    rationale = (payload.rationale or "").strip()
    actions = [item.strip() for item in (payload.remediation_actions or []) if item and item.strip()]
    if not rationale:
        return {"valid": False, "reason": "missing_rationale"}
    if not actions:
        return {"valid": False, "reason": "missing_remediation_actions"}
    return {"valid": True, "reason": None}


async def _create_pending_gate_request(
    self: Any,
    *,
    run_id: str,
    issue_id: str,
    seat_name: str,
    reason: str,
    payload: dict[str, Any],
    issue: IssueConfig,
    turn_status: CardStatus,
) -> str:
    gate_mode = "auto"
    gate_mode_fn = getattr(self.loop_policy_node, "gate_mode_for_seat", None)
    if callable(gate_mode_fn):
        try:
            gate_mode = str(
                gate_mode_fn(
                    seat_name=seat_name,
                    issue=issue,
                    turn_status=turn_status,
                )
            )
        except TypeError:
            gate_mode = str(gate_mode_fn(seat_name))

    request_created_at = datetime.now(UTC).isoformat()
    request_id = str(await self.pending_gates.create_request(
        session_id=run_id,
        issue_id=issue_id,
        seat_name=seat_name,
        gate_mode=gate_mode,
        request_type="guard_rejection_payload",
        reason=reason,
        created_at=request_created_at,
        payload=payload,
    ))
    publisher = getattr(self, "tool_approval_control_plane_reservation", None)
    if publisher is not None:
        await publisher.publish_pending_guard_review_hold(
            request_id=request_id,
            session_id=run_id,
            issue_id=issue_id,
            seat_name=seat_name,
            reason=reason,
            gate_mode=gate_mode,
            created_at=request_created_at,
        )
    return request_id


async def _create_pending_tool_approval_request(
    self: Any,
    *,
    run_id: str,
    issue: IssueConfig,
    seat_name: str,
    gate_mode: str,
    turn_index: int,
    tool_name: str,
    tool_args: dict[str, Any],
) -> str:
    from orket.application.services.turn_tool_control_plane_support import run_id_for as turn_tool_run_id_for

    request_created_at = datetime.now(UTC).isoformat()
    control_plane_target_ref = turn_tool_run_id_for(
        session_id=run_id,
        issue_id=issue.id,
        role_name=seat_name,
        turn_index=int(turn_index),
    )
    request_id = str(await self.pending_gates.create_request(
        session_id=run_id,
        issue_id=issue.id,
        seat_name=seat_name,
        gate_mode=gate_mode,
        request_type="tool_approval",
        reason=f"approval_required_tool:{tool_name}",
        created_at=request_created_at,
        payload={
            "tool": tool_name,
            "args": tool_args,
            "role": seat_name,
            "turn_index": int(turn_index),
            "control_plane_target_ref": control_plane_target_ref,
            "issue_status": str(issue.status.value if hasattr(issue.status, "value") else issue.status),
        },
    ))
    publisher = getattr(self, "tool_approval_control_plane_reservation", None)
    if publisher is not None:
        await publisher.publish_pending_tool_approval_hold(
            approval_id=request_id,
            session_id=run_id,
            issue_id=issue.id,
            seat_name=seat_name,
            tool_name=tool_name,
            turn_index=int(turn_index),
            created_at=request_created_at,
            control_plane_target_ref=control_plane_target_ref,
        )
    return request_id


def _build_turn_context(
    self: Any,
    run_id: str,
    issue: IssueConfig,
    seat_name: str,
    roles_to_load: list[str],
    turn_status: CardStatus,
    selected_model: str,
    dependency_context: dict[str, Any] | None = None,
    runtime_verifier_ok: bool | None = None,
    prompt_metadata: dict[str, Any] | None = None,
    prompt_layers: dict[str, Any] | None = None,
    idesign_enabled: bool = False,
    resume_mode: bool = False,
    skill_tool_bindings: dict[str, dict[str, Any]] | None = None,
    cards_runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    turn_index = len(self.transcript) + 1
    builder = OrchestratorTurnContextBuilder(
        workspace_root=self.workspace,
        org=self.org,
        loop_policy_node=self.loop_policy_node,
        pending_gates=self.pending_gates,
        history_context_getter=lambda current_seat: self._history_context(seat_name=current_seat),
        create_pending_tool_approval_request=self._create_pending_tool_approval_request,
        resolve_architecture_mode=self._resolve_architecture_mode,
        resolve_frontend_framework_mode=self._resolve_frontend_framework_mode,
        resolve_project_surface_profile=self._resolve_project_surface_profile,
        resolve_small_project_builder_variant=self._resolve_small_project_builder_variant,
        resolve_workflow_profile=self._resolve_workflow_profile,
        resolve_verification_scope_limits=self._resolve_verification_scope_limits,
        resolve_protocol_governed_enabled=self._resolve_protocol_governed_enabled,
        resolve_protocol_max_response_bytes=self._resolve_protocol_max_response_bytes,
        resolve_protocol_max_tool_calls=self._resolve_protocol_max_tool_calls,
        resolve_protocol_determinism_context=self._resolve_protocol_determinism_context,
        resolve_local_prompting_mode=self._resolve_local_prompting_mode,
        resolve_local_prompting_allow_fallback=self._resolve_local_prompting_allow_fallback,
        resolve_local_prompting_fallback_profile_id=self._resolve_local_prompting_fallback_profile_id,
        active_capabilities_allowed=getattr(self, "active_capabilities_allowed", None),
        active_run_determinism_class=getattr(self, "active_run_determinism_class", None),
        active_compatibility_mappings=getattr(self, "active_compatibility_mappings", None),
    )
    return builder.build(
        TurnContextBuildInput(
            run_id=run_id,
            issue=issue,
            seat_name=seat_name,
            roles_to_load=roles_to_load,
            turn_status=turn_status,
            selected_model=selected_model,
            turn_index=turn_index,
            dependency_context=dependency_context,
            runtime_verifier_ok=runtime_verifier_ok,
            prompt_metadata=prompt_metadata,
            prompt_layers=prompt_layers,
            idesign_enabled=idesign_enabled,
            resume_mode=resume_mode,
            skill_tool_bindings=skill_tool_bindings,
            cards_runtime=cards_runtime,
        )
    )


async def _build_dependency_context(self: Any, issue: IssueConfig) -> dict[str, Any]:
    depends_on = list(issue.depends_on or [])
    dependency_statuses: dict[str, str] = {}
    unresolved_dependencies: list[str] = []
    terminal_ok = {
        CardStatus.DONE,
        CardStatus.GUARD_APPROVED,
        CardStatus.ARCHIVED,
    }

    for dep_id in depends_on:
        dep = await self.async_cards.get_by_id(dep_id)
        if not dep:
            dependency_statuses[dep_id] = "missing"
            unresolved_dependencies.append(dep_id)
            continue
        status_val = getattr(dep, "status", None)
        status_text_value = getattr(status_val, "value", status_val)
        status_text = str(status_text_value or "")
        dependency_statuses[dep_id] = status_text
        if status_val not in terminal_ok:
            unresolved_dependencies.append(dep_id)

    return {
        "depends_on": depends_on,
        "dependency_count": len(depends_on),
        "dependency_statuses": dependency_statuses,
        "unresolved_dependencies": unresolved_dependencies,
    }


def _extract_guard_review_payload(self: Any, content: str) -> GuardReviewPayload:
    blob = content or ""
    decoder = json.JSONDecoder()
    candidates: list[dict[str, Any]] = []

    fenced_matches = re.findall(r"```json\s*([\s\S]*?)```", blob, flags=re.IGNORECASE)
    for chunk in fenced_matches:
        try:
            parsed = json.loads(chunk.strip())
            if isinstance(parsed, dict):
                candidates.append(parsed)
        except (json.JSONDecodeError, ValueError, TypeError):
            continue

    start = 0
    while True:
        brace_index = blob.find("{", start)
        if brace_index == -1:
            break
        try:
            parsed, end_pos = decoder.raw_decode(blob[brace_index:])
            if isinstance(parsed, dict):
                candidates.append(parsed)
            start = brace_index + max(end_pos, 1)
        except json.JSONDecodeError:
            start = brace_index + 1

    for parsed in candidates:
        if {"rationale", "violations", "remediation_actions"} & set(parsed.keys()):
            try:
                return GuardReviewPayload.model_validate(parsed)
            except (ValueError, TypeError):
                continue
    return GuardReviewPayload(
        rationale=(blob.strip()[:500] if blob else "No rationale provided."),
        violations=[],
        remediation_actions=[],
    )


def _resolve_guard_event(self: Any, status: Any) -> str | None:
    if status == CardStatus.DONE:
        return "guard_approved"
    if status in {CardStatus.BLOCKED, CardStatus.GUARD_REJECTED}:
        return "guard_rejected"
    if status in {CardStatus.IN_PROGRESS, CardStatus.GUARD_REQUESTED_CHANGES, CardStatus.READY_FOR_TESTING}:
        return "guard_requested_changes"
    return None


async def _dispatch_turn(
    self: Any,
    executor: TurnExecutor,
    issue: IssueConfig,
    role_config: RoleConfig,
    client: Any,
    toolbox: ToolBox,
    context: dict[str, Any],
    system_prompt: str,
) -> Any:
    return await executor.execute_turn(
        issue,
        role_config,
        client,
        toolbox,
        context,
        system_prompt=system_prompt,
    )


async def _save_checkpoint(
    self: Any, run_id: str, epic: EpicConfig, team: TeamConfig, env: EnvironmentConfig, active_build: str
) -> None:
    snapshot_data = {
        "epic": epic.model_dump(),
        "team": team.model_dump(),
        "env": env.model_dump(),
        "build_id": active_build,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    legacy_transcript = [{"role": t.role, "issue": t.issue_id, "content": t.content} for t in self.transcript]
    await self.snapshots.record(run_id, snapshot_data, legacy_transcript)


async def _handle_failure(
    self: Any,
    issue: IssueConfig,
    result: Any,
    run_id: str,
    roles: list[str],
    *,
    turn_index: int | None = None,
) -> None:
    handler = OrchestratorFailureHandler(
        workspace_root=self.workspace,
        transcript=self.transcript,
        async_cards=self.async_cards,
        evaluator_node=self.evaluator_node,
        request_issue_transition=self._request_issue_transition,
        is_issue_idesign_enabled=lambda current_issue: self._is_issue_idesign_enabled(current_issue),
        normalize_governance_violation_message=lambda message: self._normalize_governance_violation_message(message),
    )
    await handler.handle(
        issue=issue,
        result=result,
        run_id=run_id,
        roles=roles,
        turn_index=turn_index,
    )


def _is_issue_idesign_enabled(self: Any, issue: IssueConfig) -> bool:
    params = getattr(issue, "params", None)
    if not isinstance(params, dict):
        return False
    return bool(params.get("idesign_enabled", False))


def _normalize_governance_violation_message(self: Any, message: str | None) -> str:
    normalized = str(message or "")
    normalized = normalized.replace("iDesign Violation:", "Governance Violation:")
    normalized = normalized.replace("iDesign AST Violation", "Governance AST Violation")
    return normalized
