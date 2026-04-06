import asyncio
import inspect
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.services.cards_odr_stage import run_cards_odr_prebuild
from orket.application.services.dependency_manager import (
    DependencyManager,
    DependencyValidationError,
)
from orket.application.services.deployment_planner import (
    DeploymentPlanner,
    DeploymentValidationError,
)
from orket.application.services.guard_agent import GuardAgent
from orket.application.services.prompt_compiler import PromptCompiler
from orket.application.services.prompt_resolver import PromptResolver
from orket.application.services.runtime_policy import (
    allowed_architecture_patterns,
    resolve_architecture_mode,
    resolve_frontend_framework_mode,
    resolve_local_prompting_allow_fallback,
    resolve_local_prompting_fallback_profile_id,
    resolve_local_prompting_mode,
    resolve_project_surface_profile,
    resolve_protocol_determinism_controls,
    resolve_small_project_builder_variant,
)
from orket.application.services.runtime_verifier import RuntimeVerifier, build_runtime_guard_contract
from orket.application.services.scaffolder import Scaffolder, ScaffoldValidationError
from orket.application.services.skill_adapter import synthesize_role_tool_profile_bindings
from orket.application.workflows.turn_executor import TurnExecutor
from orket.core.cards_runtime_contract import apply_epic_cards_runtime_defaults, resolve_cards_runtime
from orket.core.domain.guard_review import GuardReviewPayload
from orket.core.domain.guard_rule_catalog import resolve_runtime_guard_rule_ids
from orket.core.domain.state_machine import StateMachine
from orket.core.domain.verification_scope import build_verification_scope
from orket.core.domain.workitem_transition import WorkItemTransitionService
from orket.core.policies.tool_gate import ToolGate
from orket.decision_nodes.contracts import PlanningInput
from orket.exceptions import CardNotFound, ExecutionFailed
from orket.logging import log_event
from orket.orchestration.models import ModelSelector
from orket.orchestration.notes import Note
from orket.runtime.settings import resolve_bool, resolve_str
from orket.runtime.truthful_memory_policy import render_reference_context_rows
from orket.runtime_paths import resolve_control_plane_db_path
from orket.schema import (
    CardStatus,
    DialectConfig,
    EnvironmentConfig,
    EpicConfig,
    IssueConfig,
    RoleConfig,
    SeatConfig,
    SkillConfig,
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
        return select_model(role=role, asset_config=asset_config)
    try:
        signature = inspect.signature(select_model)
    except (TypeError, ValueError):
        signature = None
    if signature is not None:
        parameters = signature.parameters
        if "override" in parameters or any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
        ):
            return select_model(role=role, asset_config=asset_config, override=override_token)
    return select_model(role=role, asset_config=asset_config)


def _normalize_turn_contract_override_list(value: Any, *, lowercase: bool = False) -> list[str] | None:
    if not isinstance(value, list):
        return None
    normalized: list[str] = []
    for item in value:
        token = str(item).strip()
        if not token:
            continue
        normalized.append(token.lower() if lowercase else token)
    return normalized


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


def _user_settings() -> dict[str, Any]:
    settings = load_user_settings()
    return settings if isinstance(settings, dict) else {}


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


def _resolve_architecture_mode(self) -> str:
    user_settings = _user_settings()
    raw = resolve_str(
        "ORKET_ARCHITECTURE_MODE",
        process_rules=_org_process_rules(self.org),
        process_key="architecture_mode",
        user_key="architecture_mode",
        user_settings=user_settings,
    )
    return resolve_architecture_mode(raw, "", "")


def _resolve_frontend_framework_mode(self) -> str:
    user_settings = _user_settings()
    raw = resolve_str(
        "ORKET_FRONTEND_FRAMEWORK_MODE",
        process_rules=_org_process_rules(self.org),
        process_key="frontend_framework_mode",
        user_key="frontend_framework_mode",
        user_settings=user_settings,
    )
    return resolve_frontend_framework_mode(raw, "", "")


def _resolve_architecture_pattern(self) -> str | None:
    mode = self._resolve_architecture_mode()
    if mode == "force_microservices":
        return "microservices"
    if mode == "force_monolith":
        return "monolith"
    return None


def _resolve_project_surface_profile(self) -> str:
    user_settings = _user_settings()
    raw = resolve_str(
        "ORKET_PROJECT_SURFACE_PROFILE",
        process_rules=_org_process_rules(self.org),
        process_key="project_surface_profile",
        user_key="project_surface_profile",
        user_settings=user_settings,
    )
    return resolve_project_surface_profile(raw, "", "")


def _resolve_small_project_builder_variant(self) -> str:
    user_settings = _user_settings()
    raw = resolve_str(
        "ORKET_SMALL_PROJECT_BUILDER_VARIANT",
        process_rules=_org_process_rules(self.org),
        process_key="small_project_builder_variant",
        user_key="small_project_builder_variant",
        user_settings=user_settings,
    )
    return resolve_small_project_builder_variant(raw, "", "")


def _resolve_protocol_governed_enabled(self) -> bool:
    user_settings = _user_settings()
    return resolve_bool(
        "ORKET_PROTOCOL_GOVERNED_ENABLED",
        "ORKET_PROTOCOL_GOVERNED",
        process_rules=_org_process_rules(self.org),
        process_key="protocol_governed_enabled",
        user_key="protocol_governed_enabled",
        user_settings=user_settings,
        default=False,
    )


def _resolve_protocol_max_response_bytes(self) -> int:
    user_settings = _user_settings()
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


def _resolve_protocol_max_tool_calls(self) -> int:
    user_settings = _user_settings()
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


def _resolve_protocol_determinism_context(self) -> dict[str, Any]:
    process_rules = _org_process_rules(self.org)
    user_settings = _user_settings()
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


def _resolve_local_prompting_mode(self) -> str:
    process_rules = _org_process_rules(self.org)
    user_settings = _user_settings()
    return resolve_local_prompting_mode(
        resolve_str(
            "ORKET_LOCAL_PROMPTING_MODE",
            process_rules=process_rules,
            process_key="local_prompting_mode",
            user_key="local_prompting_mode",
            user_settings=user_settings,
        ),
        "",
        "",
    )


def _resolve_local_prompting_allow_fallback(self) -> bool:
    process_rules = _org_process_rules(self.org)
    user_settings = _user_settings()
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


def _resolve_local_prompting_fallback_profile_id(self) -> str:
    process_rules = _org_process_rules(self.org)
    user_settings = _user_settings()
    return resolve_local_prompting_fallback_profile_id(
        resolve_str(
            "ORKET_LOCAL_PROMPTING_FALLBACK_PROFILE_ID",
            process_rules=process_rules,
            process_key="local_prompting_fallback_profile_id",
            user_key="local_prompting_fallback_profile_id",
            user_settings=user_settings,
        ),
        "",
        "",
    )


def _resolve_workflow_profile(self) -> str:
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
    self,
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
    self,
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


def _small_project_issue_threshold(self) -> int:
    raw = 3
    if self.org and isinstance(getattr(self.org, "process_rules", None), dict):
        raw = self.org.process_rules.get("small_project_issue_threshold", 3)
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 3


def _should_auto_inject_small_project_reviewer(self) -> bool:
    return resolve_bool(
        "ORKET_SMALL_PROJECT_AUTO_INJECT_REVIEWER",
        process_rules=_org_process_rules(self.org),
        process_key="small_project_auto_inject_code_reviewer",
        default=False,
    )


def _small_project_reviewer_seat_name(self) -> str:
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


def _auto_inject_small_project_reviewer_seat(self, team: TeamConfig) -> str:
    seat_name = self._small_project_reviewer_seat_name()
    seats = getattr(team, "seats", {}) or {}
    existing = seats.get(seat_name)
    if existing is None:
        seats[seat_name] = SeatConfig(
            name="Auto Injected Code Reviewer",
            roles=["code_reviewer"],
        )
        return seat_name

    existing_roles = list(getattr(existing, "roles", []) or [])
    normalized_roles = {str(role).strip().lower() for role in existing_roles if str(role).strip()}
    if "code_reviewer" not in normalized_roles:
        existing.roles = existing_roles + ["code_reviewer"]
    return seat_name


def _resolve_small_project_team_policy(self, epic: Any, team: Any) -> dict[str, Any]:
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


def _resolve_bool_flag(self, env_key: str, org_key: str, default: bool = False) -> bool:
    return resolve_bool(
        env_key,
        process_rules=_org_process_rules(self.org),
        process_key=org_key,
        default=default,
    )


def _is_sandbox_disabled(self) -> bool:
    return self._resolve_bool_flag("ORKET_DISABLE_SANDBOX", "disable_sandbox")


def _is_scaffolder_disabled(self) -> bool:
    return self._resolve_bool_flag("ORKET_DISABLE_SCAFFOLDER", "disable_scaffolder")


def _is_dependency_manager_disabled(self) -> bool:
    return self._resolve_bool_flag("ORKET_DISABLE_DEPENDENCY_MANAGER", "disable_dependency_manager")


def _is_runtime_verifier_disabled(self) -> bool:
    return self._resolve_bool_flag("ORKET_DISABLE_RUNTIME_VERIFIER", "disable_runtime_verifier")


def _is_deployment_planner_disabled(self) -> bool:
    return self._resolve_bool_flag("ORKET_DISABLE_DEPLOYMENT_PLANNER", "disable_deployment_planner")


def _resolve_prompt_resolver_mode(self) -> str:
    value = resolve_str(
        "ORKET_PROMPT_RESOLVER_MODE",
        process_rules=_org_process_rules(self.org),
        process_key="prompt_resolver_mode",
    ).lower()
    if value in {"resolver", "compiler"}:
        return value
    return "compiler"


def _resolve_prompt_selection_policy(self) -> str:
    value = resolve_str(
        "ORKET_PROMPT_SELECTION_POLICY",
        process_rules=_org_process_rules(self.org),
        process_key="prompt_selection_policy",
    ).lower()
    if value in {"stable", "canary", "exact"}:
        return value
    return "stable"


def _resolve_prompt_selection_strict(self) -> bool:
    return resolve_bool(
        "ORKET_PROMPT_SELECTION_STRICT",
        process_rules=_org_process_rules(self.org),
        process_key="prompt_selection_strict",
        default=True,
    )


def _resolve_prompt_version_exact(self) -> str:
    return resolve_str(
        "ORKET_PROMPT_VERSION_EXACT",
        process_rules=_org_process_rules(self.org),
        process_key="prompt_version_exact",
    )


def _resolve_prompt_patch(self) -> str:
    return resolve_str(
        "ORKET_PROMPT_PATCH",
        process_rules=_org_process_rules(self.org),
        process_key="prompt_patch",
    )


def _resolve_prompt_patch_label(self) -> str:
    return resolve_str(
        "ORKET_PROMPT_PATCH_LABEL",
        process_rules=_org_process_rules(self.org),
        process_key="prompt_patch_label",
    )


def _resolve_verification_scope_limits(self) -> dict[str, int | None]:
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


def _history_context(self, seat_name: str | None = None) -> list[dict[str, str]]:
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


async def verify_issue(self, issue_id: str, run_id: str | None = None) -> Any:
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


async def _trigger_sandbox(self, epic: EpicConfig, run_id: str | None = None):
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
    self,
    active_build: str,
    run_id: str,
    epic: EpicConfig,
    team: TeamConfig,
    env: EnvironmentConfig,
    target_issue_id: str = None,
    resume_mode: bool = False,
    model_override: str | None = None,
):
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
        try:
            scaffolder = Scaffolder(
                workspace_root=self.workspace,
                file_tools=AsyncFileTools(self.workspace),
                organization=self.org,
                project_surface_profile=project_surface_profile,
                architecture_pattern=architecture_pattern,
            )
        except TypeError:
            scaffolder = Scaffolder(
                workspace_root=self.workspace,
                file_tools=AsyncFileTools(self.workspace),
                organization=self.org,
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
        try:
            dependency_manager = DependencyManager(
                workspace_root=self.workspace,
                file_tools=AsyncFileTools(self.workspace),
                organization=self.org,
                project_surface_profile=project_surface_profile,
                architecture_pattern=architecture_pattern,
            )
        except TypeError:
            dependency_manager = DependencyManager(
                workspace_root=self.workspace,
                file_tools=AsyncFileTools(self.workspace),
                organization=self.org,
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
        try:
            deployment_planner = DeploymentPlanner(
                workspace_root=self.workspace,
                file_tools=AsyncFileTools(self.workspace),
                organization=self.org,
                project_surface_profile=project_surface_profile,
                architecture_pattern=architecture_pattern,
            )
        except TypeError:
            deployment_planner = DeploymentPlanner(
                workspace_root=self.workspace,
                file_tools=AsyncFileTools(self.workspace),
                organization=self.org,
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
        async def semaphore_wrapper(issue_data):
            async with semaphore:
                return await self._execute_issue_turn(
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


async def _propagate_dependency_blocks(self, backlog: list[Any], run_id: str) -> int:
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
    self,
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
    self,
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
):
    """Executes a single turn for one issue."""
    issue = IssueConfig.model_validate(issue_data.model_dump())
    issue.params = apply_epic_cards_runtime_defaults(
        issue_params=getattr(issue, "params", None),
        epic_params=getattr(epic, "params", None),
    )
    cards_runtime = resolve_cards_runtime(issue=issue)
    is_review_turn = self.loop_policy_node.is_review_turn(issue.status)
    dependency_context = await self._build_dependency_context(issue)
    runtime_result = None

    if is_review_turn and not self._is_runtime_verifier_disabled():
        log_event(
            "runtime_verifier_started",
            {"run_id": run_id, "issue_id": issue.id},
            self.workspace,
        )
        try:
            runtime_verifier = RuntimeVerifier(
                self.workspace,
                organization=self.org,
                project_surface_profile=self._resolve_project_surface_profile(),
                architecture_pattern=self._resolve_architecture_pattern(),
                artifact_contract=dict(cards_runtime.get("artifact_contract") or {}),
                issue_params=dict(getattr(issue, "params", {}) or {}),
            )
        except TypeError:
            runtime_verifier = RuntimeVerifier(
                self.workspace,
                organization=self.org,
            )
        runtime_result = await runtime_verifier.verify()
        guard_contract = getattr(runtime_result, "guard_contract", None)
        if guard_contract is None:
            guard_contract = build_runtime_guard_contract(
                ok=bool(getattr(runtime_result, "ok", False)),
                errors=list(getattr(runtime_result, "errors", []) or []),
            )
        existing_fingerprints = []
        if isinstance(getattr(issue, "params", None), dict):
            raw = issue.params.get("guard_retry_fingerprints", [])
            if isinstance(raw, list):
                existing_fingerprints = [str(item).strip() for item in raw if str(item).strip()]
        guard_decision = GuardAgent(self.org).evaluate(
            contract=guard_contract,
            retry_count=int(getattr(issue, "retry_count", 0) or 0),
            max_retries=int(getattr(issue, "max_retries", 0) or 0),
            output_text="\n".join(list(getattr(runtime_result, "errors", []) or [])),
            seen_fingerprints=existing_fingerprints,
        )
        if not isinstance(getattr(issue, "params", None), dict):
            issue.params = {}
        issue.params["guard_retry_fingerprints"] = existing_fingerprints[-10:]
        runtime_report = {
            "run_id": run_id,
            "issue_id": issue.id,
            "ok": bool(runtime_result.ok),
            "checked_files": list(runtime_result.checked_files),
            "errors": list(runtime_result.errors),
            "command_results": list(getattr(runtime_result, "command_results", []) or []),
            "failure_breakdown": dict(getattr(runtime_result, "failure_breakdown", {}) or {}),
            "guard_contract": guard_contract.model_dump(),
            "guard_decision": guard_decision.as_dict(),
            "timestamp": datetime.now(UTC).isoformat(),
        }
        await AsyncFileTools(self.workspace).write_file(
            "agent_output/verification/runtime_verification.json",
            json.dumps(runtime_report, indent=2),
        )
        log_event(
            "runtime_verifier_completed",
            {
                "run_id": run_id,
                "issue_id": issue.id,
                "ok": runtime_result.ok,
                "checked_files": len(runtime_result.checked_files),
                "errors": len(runtime_result.errors),
                "failure_breakdown": dict(getattr(runtime_result, "failure_breakdown", {}) or {}),
            },
            self.workspace,
        )
        if not runtime_result.ok:
            if guard_decision.action == "retry":
                issue.retry_count = guard_decision.next_retry_count
                _set_issue_runtime_retry_note(
                    issue,
                    "runtime_guard_retry_scheduled: " + " | ".join(runtime_result.errors[:3]),
                )
                await self._request_issue_transition(
                    issue=issue,
                    target_status=CardStatus.READY,
                    reason="runtime_guard_retry_scheduled",
                    metadata={"run_id": run_id, "retry_count": issue.retry_count},
                )
                await self.async_cards.save(issue.model_dump())
                log_event(
                    "guard_retry_scheduled",
                    {
                        "run_id": run_id,
                        "issue_id": issue.id,
                        "retry_count": issue.retry_count,
                        "max_retries": issue.max_retries,
                        "reason": "runtime_verification_failed",
                        "guard_contract": guard_contract.model_dump(),
                        "guard_decision": guard_decision.as_dict(),
                    },
                    self.workspace,
                )
                self.notes.add(
                    Note(
                        from_role="system",
                        content="RUNTIME VERIFIER FAILED (RETRY): " + " | ".join(runtime_result.errors[:2]),
                        step_index=len(self.transcript),
                    )
                )
            else:
                _clear_issue_runtime_retry_note(issue)
                issue.note = "runtime_guard_terminal_failure: " + (
                    guard_decision.terminal_reason.code if guard_decision.terminal_reason else "unknown"
                )
                await self._request_issue_transition(
                    issue=issue,
                    target_status=CardStatus.BLOCKED,
                    reason="runtime_guard_terminal_failure",
                    metadata={"run_id": run_id},
                )
                await self.async_cards.save(issue.model_dump())
                log_event(
                    "guard_terminal_failure",
                    {
                        "run_id": run_id,
                        "issue_id": issue.id,
                        "retry_count": issue.retry_count,
                        "max_retries": issue.max_retries,
                        "reason": "runtime_verification_failed",
                        "guard_contract": guard_contract.model_dump(),
                        "guard_decision": guard_decision.as_dict(),
                    },
                    self.workspace,
                )
                self.notes.add(
                    Note(
                        from_role="system",
                        content="RUNTIME VERIFIER TERMINAL FAILURE: " + " | ".join(runtime_result.errors[:2]),
                        step_index=len(self.transcript),
                    )
                )
            return
        _clear_issue_runtime_retry_note(issue)

    # RUN EMPIRICAL VERIFICATION (FIT) for review turns when a contract exists.
    if is_review_turn:
        verification_contract = getattr(issue, "verification", None)
        fixture_path = str(getattr(verification_contract, "fixture_path", "") or "").strip()
        scenarios = getattr(verification_contract, "scenarios", None) or []
        if fixture_path or scenarios:
            verification_result = await self.verify_issue(issue.id, run_id=run_id)
            v_msg = (
                f"EMPIRICAL VERIFICATION RESULT: {verification_result.passed}/{verification_result.total_scenarios} Passed."
            )
            self.notes.add(Note(from_role="system", content=v_msg, step_index=len(self.transcript)))

    # Select Seat via router decision node
    seat_name = self.router_node.route(issue, team, is_review_turn)
    small_policy = self._resolve_small_project_team_policy(epic, team)
    if small_policy["active"] and not is_review_turn:
        normalized_seat = str(seat_name or "").strip().lower()
        if normalized_seat not in {"code_reviewer", "reviewer", "integrity_guard"}:
            seat_name = str(small_policy["builder_seat"])
    runtime_builder_seat = str(issue.seat or "").strip() or "coder"
    runtime_reviewer_seat = "integrity_guard"
    if small_policy.get("active"):
        runtime_builder_seat = str(small_policy.get("builder_seat") or runtime_builder_seat)
        runtime_reviewer_seat = str(small_policy.get("reviewer_seat") or runtime_reviewer_seat)
    cards_runtime = resolve_cards_runtime(
        issue=issue,
        builder_seat=runtime_builder_seat,
        reviewer_seat=runtime_reviewer_seat,
    )
    invalid_profile_reason = str(cards_runtime.get("invalid_profile_reason") or "").strip()
    if invalid_profile_reason:
        await self._request_issue_transition(
            issue=issue,
            target_status=CardStatus.BLOCKED,
            reason="governance_violation",
            metadata={
                "run_id": run_id,
                "error": invalid_profile_reason,
                "execution_profile": cards_runtime.get("execution_profile"),
            },
        )
        log_event(
            "cards_runtime_preflight_failed",
            {
                "run_id": run_id,
                "issue_id": issue.id,
                "execution_profile": cards_runtime.get("execution_profile"),
                "artifact_contract": cards_runtime.get("artifact_contract"),
                "error": invalid_profile_reason,
            },
            self.workspace,
        )
        return

    seat_obj = team.seats.get(sanitize_name(seat_name))
    if not seat_obj:
        await self._request_issue_transition(
            issue=issue,
            target_status=self.loop_policy_node.missing_seat_status(),
            reason="missing_seat",
            metadata={"seat": seat_name, "run_id": run_id},
        )
        return

    is_guard_turn = is_review_turn and ("integrity_guard" in list(seat_obj.roles))
    turn_status = self.loop_policy_node.turn_status_for_issue(is_review_turn)
    turn_index = len(self.transcript) + 1
    if is_guard_turn:
        turn_status = CardStatus.AWAITING_GUARD_REVIEW
    current_issue_status = getattr(issue, "status", None)
    if not (resume_mode and current_issue_status == turn_status):
        await self._request_issue_transition(
            issue=issue,
            target_status=turn_status,
            assignee=seat_name,
            reason="turn_dispatch",
            metadata={"run_id": run_id, "review_turn": is_review_turn, "turn_index": turn_index},
            roles=list(seat_obj.roles),
        )
    elif hasattr(issue, "assignee") and getattr(issue, "assignee", None) is None:
        issue.assignee = seat_name
        await self.async_cards.save(issue.model_dump())
        log_event(
            "resume_turn_dispatch_preserved",
            {
                "run_id": run_id,
                "issue_id": issue.id,
                "seat": seat_name,
                "status": turn_status.value if hasattr(turn_status, "value") else str(turn_status),
                "turn_index": turn_index,
            },
            self.workspace,
        )

    # Prepare Role & Model
    roles_to_load = self.loop_policy_node.role_order_for_turn(list(seat_obj.roles), is_review_turn)

    async def _load_asset(category: str, name: str, model_type: Any) -> Any:
        async_loader = getattr(self.loader, "load_asset_async", None)
        if callable(async_loader):
            try:
                return await async_loader(category, name, model_type)
            except TypeError:
                # Backward compatibility for legacy loader stubs used in focused tests.
                pass
        return self.loader.load_asset(category, name, model_type)

    try:
        role_config = await _load_asset("roles", roles_to_load[0], RoleConfig)
    except CardNotFound:
        await self._request_issue_transition(
            issue=issue,
            target_status=CardStatus.IN_PROGRESS,
            reason="missing_role_asset",
            metadata={"role": roles_to_load[0], "run_id": run_id, "turn_index": turn_index},
            roles=roles_to_load,
        )
        log_event(
            "missing_role_asset",
            {"run_id": run_id, "issue_id": issue.id, "role": roles_to_load[0]},
            self.workspace,
        )
        return
    selected_model = _select_prompt_strategy_model(
        prompt_strategy_node=prompt_strategy_node,
        role=roles_to_load[0],
        asset_config=epic,
        override=model_override,
    )
    model_selection_decision = {}
    if hasattr(prompt_strategy_node, "model_selector"):
        selector = prompt_strategy_node.model_selector
        if hasattr(selector, "get_last_selection_decision"):
            model_selection_decision = dict(selector.get_last_selection_decision() or {})
    if model_selection_decision:
        log_event(
            "model_selection_decision",
            {
                "run_id": run_id,
                "issue_id": issue.id,
                "role": roles_to_load[0],
                "decision": model_selection_decision,
            },
            self.workspace,
        )
    dialect_name = prompt_strategy_node.select_dialect(selected_model)
    dialect = await _load_asset("dialects", dialect_name, DialectConfig)
    provider = self.model_client_node.create_provider(selected_model, env)
    client = self.model_client_node.create_client(provider)
    if bool(cards_runtime.get("odr_active")) and not is_review_turn:
        odr_auditor_model = (
            str(cards_runtime.get("odr_auditor_model") or "").strip()
            or str(os.environ.get("ORKET_ODR_AUDITOR_MODEL") or "").strip()
            or selected_model
        )
        odr_auditor_provider = None
        try:
            odr_auditor_provider = self.model_client_node.create_provider(odr_auditor_model, env)
            odr_auditor_client = self.model_client_node.create_client(odr_auditor_provider)
            odr_result = await run_cards_odr_prebuild(
                workspace=self.workspace,
                issue=issue,
                run_id=run_id,
                selected_model=selected_model,
                cards_runtime=cards_runtime,
                model_client=client,
                auditor_client=odr_auditor_client,
                async_cards=self.async_cards,
            )
        except (RuntimeError, ValueError, TypeError, OSError, AttributeError):
            await _close_provider_transport(provider)
            raise
        finally:
            if odr_auditor_provider is not None:
                await _close_provider_transport(odr_auditor_provider)
        cards_runtime = resolve_cards_runtime(
            issue=issue,
            builder_seat=runtime_builder_seat,
            reviewer_seat=runtime_reviewer_seat,
        )
        await provider.clear_context()
        if not bool(odr_result.get("odr_accepted")):
            await self._request_issue_transition(
                issue=issue,
                target_status=CardStatus.BLOCKED,
                reason="odr_prebuild_failed",
                metadata={
                    "run_id": run_id,
                    "odr_stop_reason": odr_result.get("odr_stop_reason"),
                    "execution_profile": cards_runtime.get("execution_profile"),
                },
            )
            await _close_provider_transport(provider)
            return

    # Compile Prompt
    skill = SkillConfig(
        name=role_config.name or seat_name,
        intent=role_config.description,
        responsibilities=[ro.description for ro in [role_config]],
        tools=role_config.tools,
        prompt_metadata=dict(getattr(role_config, "prompt_metadata", {}) or {}),
    )
    skill_tool_bindings = synthesize_role_tool_profile_bindings(role_config.tools)
    # Phase 6.4: RAG (Memory Context)
    search_query = (issue.name or "") + " " + (issue.note or "")
    memories = await self.memory.search(search_query.strip())
    memory_context = render_reference_context_rows(memories)

    prompt_mode = self._resolve_prompt_resolver_mode()
    selection_policy = self._resolve_prompt_selection_policy()
    selection_strict = self._resolve_prompt_selection_strict()
    exact_version = self._resolve_prompt_version_exact()
    prompt_patch = self._resolve_prompt_patch()
    prompt_patch_label = self._resolve_prompt_patch_label()
    architecture_governance = getattr(epic, "architecture_governance", None)
    idesign_enabled = bool(getattr(architecture_governance, "idesign", False))
    if not isinstance(getattr(issue, "params", None), dict):
        issue.params = {}
    issue.params["idesign_enabled"] = idesign_enabled
    provisional_context = self._build_turn_context(
        run_id=run_id,
        issue=issue,
        seat_name=seat_name,
        roles_to_load=roles_to_load,
        turn_status=turn_status,
        selected_model=selected_model,
        dependency_context=dependency_context,
        runtime_verifier_ok=(None if runtime_result is None else bool(runtime_result.ok)),
        prompt_metadata={},
        prompt_layers={},
        idesign_enabled=idesign_enabled,
        resume_mode=resume_mode,
        skill_tool_bindings=skill_tool_bindings,
        cards_runtime=cards_runtime,
    )
    prompt_metadata: dict[str, Any] = {
        "prompt_id": "legacy.prompt_compiler",
        "prompt_version": "legacy",
        "prompt_checksum": "",
        "resolver_policy": "compiler",
        "selection_policy": selection_policy,
        "role_status": "legacy",
        "dialect_status": "legacy",
    }
    prompt_layers: dict[str, Any] = {
        "role_base": {"name": str(skill.name or "").strip().lower(), "version": "legacy"},
        "dialect_adapter": {"name": str(dialect.model_family or "").strip().lower(), "version": "legacy"},
        "guards": [],
        "context_profile": "default",
    }
    if prompt_mode == "resolver":
        role_rule_ids = list((getattr(role_config, "prompt_metadata", {}) or {}).get("owned_rule_ids", []) or [])
        dialect_rule_ids = list((getattr(dialect, "prompt_metadata", {}) or {}).get("owned_rule_ids", []) or [])
        runtime_guard_rule_ids: list[str] = resolve_runtime_guard_rule_ids(None)
        guard_layers: list[str] = ["hallucination"]
        if self.org and isinstance(getattr(self.org, "process_rules", None), dict):
            configured_rule_ids = self.org.process_rules.get("runtime_guard_rule_ids")
            if isinstance(configured_rule_ids, list):
                runtime_guard_rule_ids = resolve_runtime_guard_rule_ids(configured_rule_ids)
            configured_layers = self.org.process_rules.get("prompt_guard_layers")
            if isinstance(configured_layers, list) and configured_layers:
                guard_layers = [str(item) for item in configured_layers if str(item).strip()]
        resolution = PromptResolver.resolve(
            skill=skill,
            dialect=dialect,
            context={
                "prompt_context_profile": "long_project" if memory_context else "default",
                "prompt_resolver_policy": "resolver_v1",
                "prompt_selection_policy": selection_policy,
                "prompt_selection_strict": selection_strict,
                "prompt_version_exact": exact_version,
                "stage_gate_mode": provisional_context.get("stage_gate_mode"),
                "required_action_tools": provisional_context.get("required_action_tools", []),
                "required_statuses": provisional_context.get("required_statuses", []),
                "required_read_paths": provisional_context.get("required_read_paths", []),
                "required_write_paths": provisional_context.get("required_write_paths", []),
                "protocol_governed_enabled": provisional_context.get("protocol_governed_enabled", False),
                "prompt_rule_ids": role_rule_ids + dialect_rule_ids,
                "runtime_guard_rule_ids": runtime_guard_rule_ids,
            },
            guards=guard_layers,
            selection_policy=selection_policy,
            patch=(prompt_patch or None),
        )
        system_desc = resolution.system_prompt
        prompt_metadata = dict(resolution.metadata)
        prompt_layers = dict(resolution.layers)
    else:
        system_desc = PromptCompiler.compile(
            skill,
            dialect,
            protocol_governed_enabled=bool(provisional_context.get("protocol_governed_enabled", False)),
            patch=(prompt_patch or None),
        )
    suppress_reference_context = _should_suppress_reference_context_for_cards_runtime(cards_runtime)
    if memory_context and not suppress_reference_context:
        system_desc += f"\n\nPROJECT CONTEXT (PAST DECISIONS):\n{memory_context}"

    import hashlib

    prompt_metadata["prompt_checksum"] = hashlib.sha256(system_desc.encode("utf-8")).hexdigest()[:16]
    if prompt_patch:
        prompt_patch_checksum = hashlib.sha256(prompt_patch.encode("utf-8")).hexdigest()[:16]
        prompt_metadata["prompt_patch_applied"] = True
        prompt_metadata["prompt_patch_label"] = prompt_patch_label or "runtime_patch"
        prompt_metadata["prompt_patch_checksum"] = prompt_patch_checksum
        prompt_layers["patch"] = {
            "applied": True,
            "label": prompt_patch_label or "runtime_patch",
            "checksum": prompt_patch_checksum,
        }

    context = self._build_turn_context(
        run_id=run_id,
        issue=issue,
        seat_name=seat_name,
        roles_to_load=roles_to_load,
        turn_status=turn_status,
        selected_model=selected_model,
        dependency_context=dependency_context,
        runtime_verifier_ok=(None if runtime_result is None else bool(runtime_result.ok)),
        prompt_metadata=prompt_metadata,
        prompt_layers=prompt_layers,
        idesign_enabled=idesign_enabled,
        resume_mode=resume_mode,
        skill_tool_bindings=skill_tool_bindings,
        cards_runtime=cards_runtime,
    )
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
            self.transcript.append(result.turn)
            updated_issue = await self.async_cards.get_by_id(issue.id)
            if is_guard_turn:
                guard_payload = self._extract_guard_review_payload(result.turn.content or "")
                guard_event = self._resolve_guard_event(updated_issue.status)
                if guard_event == "guard_rejected":
                    guard_validation = self._validate_guard_rejection_payload(guard_payload)
                    if not guard_validation.get("valid", False):
                        request_id = await self._create_pending_gate_request(
                            run_id=run_id,
                            issue_id=issue.id,
                            seat_name=seat_name,
                            reason=str(guard_validation.get("reason") or "invalid_guard_payload"),
                            payload=guard_payload.model_dump(),
                            issue=issue,
                            turn_status=turn_status,
                        )
                        log_event(
                            "gate_request_created",
                            {
                                "run_id": run_id,
                                "request_id": request_id,
                                "issue_id": issue.id,
                                "seat": seat_name,
                                "request_type": "guard_rejection_payload",
                            },
                            self.workspace,
                        )
                        log_event(
                            "guard_payload_invalid",
                            {
                                "run_id": run_id,
                                "issue_id": issue.id,
                                "seat": seat_name,
                                "request_id": request_id,
                                "reason": guard_validation.get("reason"),
                                "payload": guard_payload.model_dump(),
                            },
                            self.workspace,
                        )
                        failure_result = SimpleNamespace(
                            error=(
                                "Deterministic failure: invalid guard rejection payload "
                                f"({guard_validation.get('reason')})."
                            ),
                            violations=[],
                        )
                        await self._handle_failure(
                            issue,
                            failure_result,
                            run_id,
                            roles_to_load,
                            turn_index=turn_index,
                        )
                        return
                if guard_event:
                    log_event(
                        guard_event,
                        {
                            "run_id": run_id,
                            "issue_id": issue.id,
                            "seat": seat_name,
                            "review_payload": guard_payload.model_dump(),
                        },
                        self.workspace,
                    )
                    log_event(
                        "guard_review_payload",
                        {
                            "run_id": run_id,
                            "issue_id": issue.id,
                            "payload": guard_payload.model_dump(),
                        },
                        self.workspace,
                    )

            success_eval = self.evaluator_node.evaluate_success(
                issue=issue,
                updated_issue=updated_issue,
                turn=result.turn,
                seat_name=seat_name,
                is_review_turn=is_review_turn,
            )

            # Record significant turns in memory
            if success_eval.get("remember_decision"):
                await self.memory.remember(
                    content=f"Decision by {seat_name} on {issue.id}: {result.turn.content[:200]}...",
                    metadata={
                        "issue_id": issue.id,
                        "role": seat_name,
                        "type": "decision",
                        "write_rationale": "successful_turn_decision_summary",
                    },
                )

            # Sandbox triggering
            success_actions = self.evaluator_node.success_post_actions(success_eval)
            if self.evaluator_node.should_trigger_sandbox(success_actions):
                if self._is_sandbox_disabled():
                    log_event(
                        "sandbox_trigger_skipped_policy",
                        {"run_id": run_id, "issue_id": issue.id, "seat": seat_name},
                        self.workspace,
                    )
                else:
                    await self._trigger_sandbox(epic, run_id=run_id)
                next_status = self.evaluator_node.next_status_after_success(success_actions)
                if next_status is not None:
                    await self._request_issue_transition(
                        issue=issue,
                        target_status=next_status,
                        reason="post_success_evaluator",
                        metadata={"run_id": run_id, "seat": seat_name, "turn_index": turn_index},
                        roles=roles_to_load,
                    )

            await provider.clear_context()
            await self._save_checkpoint(run_id, epic, team, env, active_build)
            issue_control_plane = getattr(self, "issue_control_plane", None)
            if issue_control_plane is not None:
                latest_issue = await self.async_cards.get_by_id(issue.id)
                observed_status = issue.status
                if isinstance(latest_issue, dict):
                    observed_status = latest_issue.get("status", observed_status)
                elif latest_issue is not None:
                    observed_status = getattr(latest_issue, "status", observed_status)
                await issue_control_plane.close_from_observed_status(
                    session_id=run_id,
                    issue_id=issue.id,
                    observed_status=observed_status,
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


def _validate_guard_rejection_payload(self, payload: GuardReviewPayload) -> dict[str, Any]:
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
    self,
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
    request_id = await self.pending_gates.create_request(
        session_id=run_id,
        issue_id=issue_id,
        seat_name=seat_name,
        gate_mode=gate_mode,
        request_type="guard_rejection_payload",
        reason=reason,
        created_at=request_created_at,
        payload=payload,
    )
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
    self,
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
    request_id = await self.pending_gates.create_request(
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
    )
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
    self,
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
    cards_runtime = dict(cards_runtime or resolve_cards_runtime(issue=issue))
    required_action_tools = []
    required_tools_fn = getattr(self.loop_policy_node, "required_action_tools_for_seat", None)
    if callable(required_tools_fn):
        try:
            required_action_tools = list(
                required_tools_fn(
                    seat_name=seat_name,
                    issue=issue,
                    turn_status=turn_status,
                )
                or []
            )
        except TypeError:
            required_action_tools = list(required_tools_fn(seat_name) or [])

    required_statuses = []
    required_statuses_fn = getattr(self.loop_policy_node, "required_statuses_for_seat", None)
    if callable(required_statuses_fn):
        try:
            required_statuses = list(
                required_statuses_fn(
                    seat_name=seat_name,
                    issue=issue,
                    turn_status=turn_status,
                )
                or []
            )
        except TypeError:
            required_statuses = list(required_statuses_fn(seat_name) or [])

    required_read_paths = []
    required_read_paths_fn = getattr(self.loop_policy_node, "required_read_paths_for_seat", None)
    if callable(required_read_paths_fn):
        try:
            required_read_paths = list(
                required_read_paths_fn(
                    seat_name=seat_name,
                    issue=issue,
                    turn_status=turn_status,
                )
                or []
            )
        except TypeError:
            required_read_paths = list(required_read_paths_fn(seat_name) or [])

    required_write_paths = []
    required_write_paths_fn = getattr(self.loop_policy_node, "required_write_paths_for_seat", None)
    if callable(required_write_paths_fn):
        try:
            required_write_paths = list(
                required_write_paths_fn(
                    seat_name=seat_name,
                    issue=issue,
                    turn_status=turn_status,
                )
                or []
            )
        except TypeError:
            required_write_paths = list(required_write_paths_fn(seat_name) or [])

    params = getattr(issue, "params", None)
    normalized_issue_seat = str(getattr(issue, "seat", "") or "").strip().lower()
    normalized_seat_name = str(seat_name or "").strip().lower()
    turn_contract = (
        params.get("turn_contract")
        if (
            isinstance(params, dict)
            and isinstance(params.get("turn_contract"), dict)
            and normalized_issue_seat
            and normalized_issue_seat == normalized_seat_name
        )
        else {}
    )
    override_action_tools = _normalize_turn_contract_override_list(turn_contract.get("required_action_tools"))
    if override_action_tools is not None:
        required_action_tools = override_action_tools
    override_statuses = _normalize_turn_contract_override_list(turn_contract.get("required_statuses"), lowercase=True)
    if override_statuses is not None:
        required_statuses = override_statuses
    override_read_paths = _normalize_turn_contract_override_list(turn_contract.get("required_read_paths"))
    if override_read_paths is not None:
        required_read_paths = override_read_paths
    override_write_paths = _normalize_turn_contract_override_list(turn_contract.get("required_write_paths"))
    if override_write_paths is not None:
        required_write_paths = override_write_paths
    raw_required_comment_min_length = turn_contract.get("required_comment_min_length")
    required_comment_min_length = None
    if raw_required_comment_min_length is not None:
        try:
            required_comment_min_length = max(1, int(raw_required_comment_min_length))
        except (TypeError, ValueError):
            required_comment_min_length = None
    required_comment_contains = (
        _normalize_turn_contract_override_list(turn_contract.get("required_comment_contains")) or []
    )
    runtime_verifier_contract = (
        dict(params.get("runtime_verifier") or {})
        if (
            isinstance(params, dict)
            and isinstance(params.get("runtime_verifier"), dict)
            and normalized_issue_seat
            and normalized_issue_seat == normalized_seat_name
        )
        else {}
    )
    profile_traits = dict(cards_runtime.get("profile_traits") or {})
    profile_intent = str(profile_traits.get("intent") or "").strip().lower()
    runtime_verifier_issue_override = bool(runtime_verifier_contract) and profile_intent in {"write_artifact", "build_app"}
    if not bool(profile_traits.get("runtime_verifier_allowed", True)) and not runtime_verifier_issue_override:
        runtime_verifier_contract = {}

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

    approval_required_tools = []
    approval_tools_fn = getattr(self.loop_policy_node, "approval_required_tools_for_seat", None)
    if callable(approval_tools_fn):
        try:
            approval_required_tools = list(
                approval_tools_fn(
                    seat_name=seat_name,
                    issue=issue,
                    turn_status=turn_status,
                )
                or []
            )
        except TypeError:
            approval_required_tools = list(approval_tools_fn(seat_name) or [])

    if approval_required_tools and gate_mode == "auto":
        gate_mode = "approval_required"

    async def _find_existing_tool_approval_request(
        *,
        tool_name: str,
        tool_args: dict[str, Any],
        allowed_statuses: set[str],
    ) -> dict[str, Any] | None:
        list_requests = getattr(self.pending_gates, "list_requests", None)
        if not callable(list_requests):
            return None
        from orket.application.services.turn_tool_control_plane_support import run_id_for as turn_tool_run_id_for

        expected_target_ref = turn_tool_run_id_for(
            session_id=run_id,
            issue_id=issue.id,
            role_name=seat_name,
            turn_index=int(turn_index),
        )
        rows = await list_requests(session_id=run_id, limit=1000)
        for row in rows:
            status_token = str(row.get("status") or "").strip().lower()
            if status_token not in allowed_statuses:
                continue
            if str(row.get("issue_id") or "").strip() != issue.id:
                continue
            if str(row.get("seat_name") or "").strip() != seat_name:
                continue
            if str(row.get("request_type") or "").strip() != "tool_approval":
                continue
            if str(row.get("reason") or "").strip() != f"approval_required_tool:{tool_name}":
                continue
            payload = row.get("payload_json")
            if not isinstance(payload, dict):
                continue
            if str(payload.get("tool") or "").strip() != tool_name:
                continue
            if dict(payload.get("args") or {}) != dict(tool_args or {}):
                continue
            if payload.get("turn_index") != int(turn_index):
                continue
            target_ref = str(payload.get("control_plane_target_ref") or "").strip()
            if target_ref != expected_target_ref:
                raise RuntimeError(
                    "approved governed turn-tool approval drifted from the admitted governed turn target"
                )
            return dict(row)
        return None

    async def _pending_gate_request_writer(*, tool_name: str, tool_args: dict[str, Any]) -> str:
        existing = await _find_existing_tool_approval_request(
            tool_name=tool_name,
            tool_args=tool_args,
            allowed_statuses={"pending"},
        )
        if existing is not None:
            return str(existing.get("request_id") or "")
        return await self._create_pending_tool_approval_request(
            run_id=run_id,
            issue=issue,
            seat_name=seat_name,
            gate_mode=gate_mode,
            turn_index=turn_index,
            tool_name=tool_name,
            tool_args=tool_args,
        )

    async def _approved_tool_request_lookup(*, tool_name: str, tool_args: dict[str, Any]) -> str | None:
        existing = await _find_existing_tool_approval_request(
            tool_name=tool_name,
            tool_args=tool_args,
            allowed_statuses={"approved"},
        )
        if existing is None:
            return None
        resolution = existing.get("resolution_json")
        if isinstance(resolution, dict) and str(resolution.get("decision") or "").strip().lower() != "approve":
            return None
        return str(existing.get("request_id") or "").strip() or None

    architecture_mode = self._resolve_architecture_mode()
    frontend_framework_mode = self._resolve_frontend_framework_mode()
    project_surface_profile = self._resolve_project_surface_profile()
    small_project_builder_variant = self._resolve_small_project_builder_variant()
    is_architect_seat = str(seat_name).strip().lower() == "architect"
    forced_pattern = None
    if architecture_mode == "force_monolith":
        forced_pattern = "monolith"
    elif architecture_mode == "force_microservices":
        forced_pattern = "microservices"
    forced_frontend_framework = None
    if frontend_framework_mode == "force_vue":
        forced_frontend_framework = "vue"
    elif frontend_framework_mode == "force_react":
        forced_frontend_framework = "react"
    elif frontend_framework_mode == "force_angular":
        forced_frontend_framework = "angular"
    scope_limits = self._resolve_verification_scope_limits()
    architecture_patterns = allowed_architecture_patterns()
    process_rules = (
        self.org.process_rules if self.org and isinstance(getattr(self.org, "process_rules", None), dict) else {}
    )
    allowed_tool_rings = [
        str(token).strip().lower()
        for token in (process_rules.get("allowed_tool_rings") or ["core"])
        if str(token).strip()
    ]
    if not allowed_tool_rings:
        allowed_tool_rings = ["core"]

    raw_active_capabilities = getattr(self, "active_capabilities_allowed", None)
    if isinstance(raw_active_capabilities, list) and raw_active_capabilities:
        allowed_capability_profiles = [
            str(token).strip().lower() for token in raw_active_capabilities if str(token).strip()
        ]
    else:
        allowed_capability_profiles = [
            str(token).strip().lower()
            for token in (process_rules.get("allowed_capability_profiles") or ["workspace"])
            if str(token).strip()
        ]
    if not allowed_capability_profiles:
        allowed_capability_profiles = ["workspace"]
    run_namespace_scope = f"issue:{issue.id}"

    run_determinism_class = (
        str(
            getattr(self, "active_run_determinism_class", None)
            or process_rules.get("run_determinism_class")
            or "workspace"
        )
        .strip()
        .lower()
    )
    if run_determinism_class not in {"pure", "workspace", "external"}:
        run_determinism_class = "workspace"
    raw_compatibility_mappings = getattr(self, "active_compatibility_mappings", None)
    if isinstance(raw_compatibility_mappings, dict):
        compatibility_mappings = {
            str(tool_name).strip(): dict(mapping or {})
            for tool_name, mapping in raw_compatibility_mappings.items()
            if str(tool_name).strip() and isinstance(mapping, dict)
        }
    else:
        compatibility_mappings = {}

    raw_max_tool_execution_time = process_rules.get("skill_max_execution_time")
    raw_max_tool_memory = process_rules.get("skill_max_memory")
    try:
        max_tool_execution_time = (
            float(raw_max_tool_execution_time) if raw_max_tool_execution_time is not None else None
        )
    except (TypeError, ValueError):
        max_tool_execution_time = None
    try:
        max_tool_memory = float(raw_max_tool_memory) if raw_max_tool_memory is not None else None
    except (TypeError, ValueError):
        max_tool_memory = None
    resolved_skill_tool_bindings = {
        str(key).strip(): dict(value or {}) for key, value in (skill_tool_bindings or {}).items() if str(key).strip()
    }
    profile_versions = sorted(
        {
            str((row or {}).get("tool_profile_version") or "").strip()
            for row in resolved_skill_tool_bindings.values()
            if str((row or {}).get("tool_profile_version") or "").strip()
        }
    )
    tool_profile_version = profile_versions[0] if len(profile_versions) == 1 else "unknown-v1"
    protocol_governed_enabled = self._resolve_protocol_governed_enabled()
    max_response_bytes = self._resolve_protocol_max_response_bytes()
    max_tool_calls = self._resolve_protocol_max_tool_calls()
    determinism_controls = self._resolve_protocol_determinism_context()
    local_prompting_mode = self._resolve_local_prompting_mode()
    local_prompting_allow_fallback = self._resolve_local_prompting_allow_fallback()
    local_prompting_fallback_profile_id = self._resolve_local_prompting_fallback_profile_id()
    prompt_budget_enabled = bool(protocol_governed_enabled)
    prompt_budget_enabled_raw = process_rules.get("prompt_budget_enabled")
    if isinstance(prompt_budget_enabled_raw, bool):
        prompt_budget_enabled = prompt_budget_enabled_raw
    elif isinstance(prompt_budget_enabled_raw, str):
        prompt_budget_enabled = prompt_budget_enabled_raw.strip().lower() in {"1", "true", "yes", "on", "enabled"}

    prompt_budget_require_backend_tokenizer = False
    prompt_budget_require_backend_tokenizer_raw = process_rules.get("prompt_budget_require_backend_tokenizer")
    if isinstance(prompt_budget_require_backend_tokenizer_raw, bool):
        prompt_budget_require_backend_tokenizer = prompt_budget_require_backend_tokenizer_raw
    elif isinstance(prompt_budget_require_backend_tokenizer_raw, str):
        prompt_budget_require_backend_tokenizer = prompt_budget_require_backend_tokenizer_raw.strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
            "enabled",
        }
    prompt_budget_policy_path = (
        str(process_rules.get("prompt_budget_policy_path") or "core/policies/prompt_budget.yaml").strip()
        or "core/policies/prompt_budget.yaml"
    )
    available_required_read_paths: list[str] = []
    for raw_path in required_read_paths:
        path_token = str(raw_path).strip()
        if not path_token:
            continue
        candidate = (self.workspace / path_token).resolve()
        if candidate.exists():
            available_required_read_paths.append(path_token)

    declared_interfaces = list(required_action_tools) + list(approval_required_tools)
    if not required_action_tools:
        fallback_interfaces = list(resolved_skill_tool_bindings.keys()) or [
            "read_file",
            "write_file",
            "update_issue_status",
        ]
        for fallback_interface in fallback_interfaces:
            if fallback_interface not in declared_interfaces:
                declared_interfaces.append(fallback_interface)
    if available_required_read_paths and "read_file" not in declared_interfaces:
        declared_interfaces.append("read_file")
    if required_write_paths and "write_file" not in declared_interfaces:
        declared_interfaces.append("write_file")
    if required_statuses and "update_issue_status" not in declared_interfaces:
        declared_interfaces.append("update_issue_status")

    return {
        "session_id": run_id,
        "issue_id": issue.id,
        "workspace": str(self.workspace),
        "role": seat_name,
        "roles": roles_to_load,
        "current_status": turn_status.value,
        "selected_model": selected_model,
        "turn_index": turn_index,
        "dependency_context": dependency_context
        or {
            "depends_on": issue.depends_on,
            "dependency_count": len(issue.depends_on),
            "dependency_statuses": {},
            "unresolved_dependencies": [],
        },
        "required_action_tools": required_action_tools,
        "required_statuses": required_statuses,
        "required_read_paths": required_read_paths,
        "required_write_paths": required_write_paths,
        "required_comment_min_length": required_comment_min_length,
        "required_comment_contains": required_comment_contains,
        "execution_profile": str(cards_runtime.get("execution_profile") or ""),
        "base_execution_profile": str(cards_runtime.get("base_execution_profile") or ""),
        "builder_seat_choice": str(cards_runtime.get("builder_seat_choice") or ""),
        "reviewer_seat_choice": str(cards_runtime.get("reviewer_seat_choice") or ""),
        "profile_traits": profile_traits,
        "seat_coercion": dict(cards_runtime.get("seat_coercion") or {}),
        "artifact_contract": dict(cards_runtime.get("artifact_contract") or {}),
        "scenario_truth": dict(cards_runtime.get("scenario_truth") or {}),
        "odr_active": bool(cards_runtime.get("odr_active")),
        "odr_valid": cards_runtime.get("odr_valid"),
        "odr_pending_decisions": cards_runtime.get("odr_pending_decisions"),
        "odr_stop_reason": cards_runtime.get("odr_stop_reason"),
        "odr_artifact_path": str(cards_runtime.get("odr_artifact_path") or ""),
        "odr_requirement": str(cards_runtime.get("odr_requirement") or ""),
        "verification_scope": build_verification_scope(
            workspace=list(available_required_read_paths) + list(required_write_paths),
            active_context=list(available_required_read_paths),
            passive_context=[],
            archived_context=[],
            declared_interfaces=declared_interfaces,
            strict_grounding=True,
            forbidden_phrases=[],
            enforce_path_hardening=True,
            consistency_tool_calls_only=True,
            max_workspace_items=scope_limits.get("max_workspace_items"),
            max_active_context_items=scope_limits.get("max_active_context_items"),
            max_passive_context_items=scope_limits.get("max_passive_context_items"),
            max_archived_context_items=scope_limits.get("max_archived_context_items"),
            max_total_context_items=scope_limits.get("max_total_context_items"),
        ),
        "stage_gate_mode": gate_mode,
        "approval_required_tools": approval_required_tools,
        "runtime_verifier_ok": runtime_verifier_ok,
        "runtime_verifier_contract": runtime_verifier_contract,
        "runtime_retry_note": str(params.get("runtime_retry_note") or "") if isinstance(params, dict) else "",
        "prompt_metadata": prompt_metadata or {},
        "prompt_layers": prompt_layers or {},
        "architecture_mode": architecture_mode,
        "frontend_framework_mode": frontend_framework_mode,
        "project_surface_profile": project_surface_profile,
        "small_project_builder_variant": small_project_builder_variant,
        "workflow_profile": self._resolve_workflow_profile(),
        "architecture_decision_required": bool(is_architect_seat),
        "architecture_decision_path": "agent_output/design.txt",
        "architecture_allowed_patterns": architecture_patterns,
        "architecture_forced_pattern": forced_pattern,
        "frontend_framework_allowed": ["vue", "react", "angular"],
        "frontend_framework_forced": forced_frontend_framework,
        "idesign_enabled": bool(idesign_enabled),
        "create_pending_gate_request": _pending_gate_request_writer,
        "resolve_granted_tool_approval": _approved_tool_request_lookup,
        "resume_mode": bool(resume_mode),
        "history": self._history_context(seat_name=seat_name),
        "skill_contract_enforced": bool(resolved_skill_tool_bindings),
        "skill_tool_bindings": resolved_skill_tool_bindings,
        "tool_profile_version": tool_profile_version,
        "allowed_tool_rings": allowed_tool_rings,
        "allowed_capability_profiles": allowed_capability_profiles,
        "allowed_namespace_scopes": [run_namespace_scope],
        "capabilities_allowed": allowed_capability_profiles,
        "run_namespace_scope": run_namespace_scope,
        "run_determinism_class": run_determinism_class,
        "run_determinism_policy": run_determinism_class,
        "compatibility_mappings": compatibility_mappings,
        "max_tool_execution_time": max_tool_execution_time,
        "max_tool_memory": max_tool_memory,
        "protocol_governed_enabled": protocol_governed_enabled,
        "max_response_bytes": max_response_bytes,
        "max_tool_calls": max_tool_calls,
        "timezone": determinism_controls["timezone"],
        "locale": determinism_controls["locale"],
        "network_mode": determinism_controls["network_mode"],
        "network_allowlist_values": determinism_controls["network_allowlist_values"],
        "network_allowlist_hash": determinism_controls["network_allowlist_hash"],
        "clock_mode": determinism_controls["clock_mode"],
        "clock_artifact_ref": determinism_controls["clock_artifact_ref"],
        "clock_artifact_hash": determinism_controls["clock_artifact_hash"],
        "env_allowlist": determinism_controls["env_allowlist"],
        "env_allowlist_values": determinism_controls["env_allowlist_values"],
        "env_allowlist_hash": determinism_controls["env_allowlist_hash"],
        "local_prompting_mode": local_prompting_mode,
        "local_prompting_allow_fallback": local_prompting_allow_fallback,
        "local_prompting_fallback_profile_id": local_prompting_fallback_profile_id,
        "prompt_budget_enabled": prompt_budget_enabled,
        "prompt_budget_require_backend_tokenizer": prompt_budget_require_backend_tokenizer,
        "prompt_budget_policy_path": prompt_budget_policy_path,
    }


async def _build_dependency_context(self, issue: IssueConfig) -> dict[str, Any]:
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
        status_text = status_val.value if hasattr(status_val, "value") else str(status_val)
        dependency_statuses[dep_id] = status_text
        if status_val not in terminal_ok:
            unresolved_dependencies.append(dep_id)

    return {
        "depends_on": depends_on,
        "dependency_count": len(depends_on),
        "dependency_statuses": dependency_statuses,
        "unresolved_dependencies": unresolved_dependencies,
    }


def _extract_guard_review_payload(self, content: str) -> GuardReviewPayload:
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


def _resolve_guard_event(self, status: Any) -> str | None:
    if status == CardStatus.DONE:
        return "guard_approved"
    if status in {CardStatus.BLOCKED, CardStatus.GUARD_REJECTED}:
        return "guard_rejected"
    if status in {CardStatus.IN_PROGRESS, CardStatus.GUARD_REQUESTED_CHANGES, CardStatus.READY_FOR_TESTING}:
        return "guard_requested_changes"
    return None


async def _dispatch_turn(
    self,
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
    self, run_id: str, epic: EpicConfig, team: TeamConfig, env: EnvironmentConfig, active_build: str
):
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
    self,
    issue: IssueConfig,
    result: Any,
    run_id: str,
    roles: list[str],
    *,
    turn_index: int | None = None,
):
    from orket.core.domain.failure_reporter import FailureReporter

    await FailureReporter.generate_report(
        workspace=self.workspace,
        session_id=run_id,
        card_id=issue.id,
        violation=result.error or "Unknown failure",
        transcript=self.transcript,
        roles=roles,
    )

    eval_decision = self.evaluator_node.evaluate_failure(issue, result)
    issue.retry_count = eval_decision.get("next_retry_count", issue.retry_count)
    action = eval_decision.get("action")
    failure_exception_class = self.evaluator_node.failure_exception_class(action)

    # Mechanical governance violations are terminal for the issue.
    if action == "governance_violation":
        failure_status = self.evaluator_node.status_for_failure_action(action)
        metadata = {"run_id": run_id, "error": result.error}
        if turn_index is not None:
            metadata["turn_index"] = turn_index
        await self._request_issue_transition(
            issue=issue,
            target_status=failure_status,
            reason="governance_violation",
            metadata=metadata,
            roles=roles,
        )
        await self.async_cards.save(issue.model_dump())
        message = self.evaluator_node.governance_violation_message(result.error)
        if not self._is_issue_idesign_enabled(issue):
            message = self._normalize_governance_violation_message(message)
        raise failure_exception_class(message)

    if action == "approval_pending":
        event_name = self.evaluator_node.failure_event_name(action)
        if event_name:
            log_event(
                event_name,
                {"run_id": run_id, "issue_id": issue.id, "error": result.error},
                self.workspace,
            )
        await self.async_cards.save(issue.model_dump())
        raise failure_exception_class(str(result.error or "Approval required before execution."))

    if action == "catastrophic":
        event_name = self.evaluator_node.failure_event_name(action)
        if event_name:
            log_event(
                event_name,
                {"run_id": run_id, "issue_id": issue.id, "retry_count": issue.retry_count, "error": result.error},
                self.workspace,
            )
        failure_status = self.evaluator_node.status_for_failure_action(action)
        metadata = {"run_id": run_id, "error": result.error}
        if turn_index is not None:
            metadata["turn_index"] = turn_index
        await self._request_issue_transition(
            issue=issue,
            target_status=failure_status,
            reason="catastrophic_failure",
            metadata=metadata,
            roles=roles,
        )
        await self.async_cards.save(issue.model_dump())

        # Catastrophic failure shuts down the session
        from orket.state import runtime_state

        if self.evaluator_node.should_cancel_session(action):
            tasks = await runtime_state.get_tasks(run_id)
            for task in tasks:
                if task.done():
                    continue
                cancel_result = task.cancel()
                if asyncio.iscoroutine(cancel_result):
                    await cancel_result

        raise failure_exception_class(self.evaluator_node.catastrophic_failure_message(issue.id, issue.max_retries))

    if action != "retry":
        raise failure_exception_class(self.evaluator_node.unexpected_failure_action_message(action, issue.id))

    # Log retry and reset to READY
    event_name = self.evaluator_node.failure_event_name(action)
    if event_name:
        log_event(
            event_name,
            {
                "run_id": run_id,
                "issue_id": issue.id,
                "retry_count": issue.retry_count,
                "max_retries": issue.max_retries,
                "error": result.error,
            },
            self.workspace,
        )

    metadata = {
        "run_id": run_id,
        "retry_count": issue.retry_count,
        "max_retries": issue.max_retries,
        "error": result.error,
    }
    if turn_index is not None:
        metadata["turn_index"] = turn_index
    await self._request_issue_transition(
        issue=issue,
        target_status=self.evaluator_node.status_for_failure_action(action),
        reason="retry_scheduled",
        metadata=metadata,
        roles=roles,
    )
    await self.async_cards.save(issue.model_dump())

    raise failure_exception_class(
        self.evaluator_node.retry_failure_message(
            issue.id,
            issue.retry_count,
            issue.max_retries,
            result.error,
        )
    )


def _is_issue_idesign_enabled(self, issue: IssueConfig) -> bool:
    params = getattr(issue, "params", None)
    if not isinstance(params, dict):
        return False
    return bool(params.get("idesign_enabled", False))


def _normalize_governance_violation_message(self, message: str | None) -> str:
    normalized = str(message or "")
    normalized = normalized.replace("iDesign Violation:", "Governance Violation:")
    normalized = normalized.replace("iDesign AST Violation", "Governance AST Violation")
    return normalized
