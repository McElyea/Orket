from __future__ import annotations

from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orket.application.services.loop_decision_service import capture_seat_policy_input
from orket.application.services.orchestrator_turn_context_gate_service import OrchestratorTurnContextGateService
from orket.application.services.orchestrator_turn_context_policy import (
    normalize_turn_contract_override_list,
    resolve_policy_list,
    resolve_policy_token,
)
from orket.application.services.runtime_policy import allowed_architecture_patterns
from orket.application.services.runtime_policy_inputs import ArchitecturePolicySnapshot
from orket.application.workflows.turn_read_context import observe_available_required_read_paths
from orket.core.cards_runtime_contract import DEFAULT_RUNTIME_VERIFICATION_PATH, resolve_cards_runtime
from orket.core.domain.verification_scope import build_verification_scope
from orket.runtime.config.contract_assets import DEFAULT_PROMPT_BUDGET_PATH
from orket.schema import CardStatus, IssueConfig


@dataclass
class TurnContextBuildInput:
    run_id: str
    issue: IssueConfig
    seat_name: str
    roles_to_load: list[str]
    turn_status: CardStatus
    selected_model: str
    turn_index: int
    dependency_context: dict[str, Any] | None = None
    runtime_verifier_ok: bool | None = None
    runtime_verifier_enabled: bool = True
    prompt_metadata: dict[str, Any] | None = None
    prompt_layers: dict[str, Any] | None = None
    idesign_enabled: bool = False
    resume_mode: bool = False
    skill_tool_bindings: dict[str, dict[str, Any]] | None = None
    cards_runtime: dict[str, Any] | None = None


class OrchestratorTurnContextBuilder:
    def __init__(
        self,
        *,
        architecture_policy: ArchitecturePolicySnapshot,
        workspace_root: Path,
        org: Any,
        loop_policy_node: Any,
        pending_gates: Any,
        history_context_getter: Callable[[str | None], list[dict[str, str]]],
        create_pending_tool_approval_request: Callable[..., Awaitable[str]],
        resolve_architecture_mode: Callable[[], str],
        resolve_frontend_framework_mode: Callable[[], str],
        resolve_project_surface_profile: Callable[[], str],
        resolve_small_project_builder_variant: Callable[[], str],
        resolve_workflow_profile: Callable[[], str],
        resolve_verification_scope_limits: Callable[[], dict[str, int | None]],
        resolve_protocol_governed_enabled: Callable[[], bool],
        resolve_protocol_max_response_bytes: Callable[[], int],
        resolve_protocol_max_tool_calls: Callable[[], int],
        resolve_protocol_determinism_context: Callable[[], dict[str, Any]],
        resolve_local_prompting_mode: Callable[[], str],
        resolve_local_prompting_allow_fallback: Callable[[], bool],
        resolve_local_prompting_fallback_profile_id: Callable[[], str],
        active_capabilities_allowed: Any,
        active_run_determinism_class: Any,
        active_compatibility_mappings: Any,
    ) -> None:
        self.architecture_policy = architecture_policy
        self.workspace_root = workspace_root
        self.org = org
        self.loop_policy_node = loop_policy_node
        self.pending_gates = pending_gates
        self.history_context_getter = history_context_getter
        self.create_pending_tool_approval_request = create_pending_tool_approval_request
        self.resolve_architecture_mode = resolve_architecture_mode
        self.resolve_frontend_framework_mode = resolve_frontend_framework_mode
        self.resolve_project_surface_profile = resolve_project_surface_profile
        self.resolve_small_project_builder_variant = resolve_small_project_builder_variant
        self.resolve_workflow_profile = resolve_workflow_profile
        self.resolve_verification_scope_limits = resolve_verification_scope_limits
        self.resolve_protocol_governed_enabled = resolve_protocol_governed_enabled
        self.resolve_protocol_max_response_bytes = resolve_protocol_max_response_bytes
        self.resolve_protocol_max_tool_calls = resolve_protocol_max_tool_calls
        self.resolve_protocol_determinism_context = resolve_protocol_determinism_context
        self.resolve_local_prompting_mode = resolve_local_prompting_mode
        self.resolve_local_prompting_allow_fallback = resolve_local_prompting_allow_fallback
        self.resolve_local_prompting_fallback_profile_id = resolve_local_prompting_fallback_profile_id
        self.active_capabilities_allowed = active_capabilities_allowed
        self.active_run_determinism_class = active_run_determinism_class
        self.active_compatibility_mappings = active_compatibility_mappings

    @staticmethod
    def _resolve_optional_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    async def build(self, data: TurnContextBuildInput) -> dict[str, Any]:
        workspace_root = self.workspace_root
        cards_runtime = dict(data.cards_runtime or resolve_cards_runtime(issue=data.issue))
        policy_inputs = capture_seat_policy_input(data.seat_name, data.issue, data.turn_status)
        required_action_tools = resolve_policy_list(
            loop_policy_node=self.loop_policy_node,
            attribute="required_action_tools_for_seat",
            inputs=policy_inputs,
        )
        required_statuses = resolve_policy_list(
            loop_policy_node=self.loop_policy_node,
            attribute="required_statuses_for_seat",
            inputs=policy_inputs,
        )
        required_read_paths = resolve_policy_list(
            loop_policy_node=self.loop_policy_node,
            attribute="required_read_paths_for_seat",
            inputs=policy_inputs,
        )
        if not data.runtime_verifier_enabled:
            required_read_paths = [path for path in required_read_paths if path != DEFAULT_RUNTIME_VERIFICATION_PATH]
        required_write_paths = resolve_policy_list(
            loop_policy_node=self.loop_policy_node,
            attribute="required_write_paths_for_seat",
            inputs=policy_inputs,
        )
        params = getattr(data.issue, "params", None)
        normalized_issue_seat = str(getattr(data.issue, "seat", "") or "").strip().lower()
        normalized_seat_name = str(data.seat_name or "").strip().lower()
        raw_turn_contract = params.get("turn_contract") if isinstance(params, dict) else None
        turn_contract = (
            dict(raw_turn_contract)
            if isinstance(raw_turn_contract, dict) and normalized_issue_seat == normalized_seat_name and normalized_issue_seat
            else {}
        )
        override_action_tools = normalize_turn_contract_override_list(turn_contract.get("required_action_tools"))
        if override_action_tools is not None:
            required_action_tools = override_action_tools
        override_statuses = normalize_turn_contract_override_list(
            turn_contract.get("required_statuses"),
            lowercase=True,
        )
        if override_statuses is not None:
            required_statuses = override_statuses
        override_read_paths = normalize_turn_contract_override_list(turn_contract.get("required_read_paths"))
        if override_read_paths is not None:
            required_read_paths = override_read_paths
        override_write_paths = normalize_turn_contract_override_list(turn_contract.get("required_write_paths"))
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
            normalize_turn_contract_override_list(turn_contract.get("required_comment_contains")) or []
        )
        runtime_verifier_contract = (
            deepcopy(dict(params.get("runtime_verifier") or {}))
            if isinstance(params, dict)
            and isinstance(params.get("runtime_verifier"), dict)
            and normalized_issue_seat == normalized_seat_name
            and normalized_issue_seat
            else {}
        )
        profile_traits = deepcopy(dict(cards_runtime.get("profile_traits") or {}))
        profile_intent = str(profile_traits.get("intent") or "").strip().lower()
        runtime_verifier_issue_override = bool(runtime_verifier_contract) and profile_intent in {"write_artifact", "build_app"}
        if not bool(profile_traits.get("runtime_verifier_allowed", True)) and not runtime_verifier_issue_override:
            runtime_verifier_contract = {}
        gate_mode = resolve_policy_token(
            loop_policy_node=self.loop_policy_node,
            attribute="gate_mode_for_seat",
            inputs=policy_inputs,
            default="auto",
        )
        approval_required_tools = resolve_policy_list(
            loop_policy_node=self.loop_policy_node,
            attribute="approval_required_tools_for_seat",
            inputs=policy_inputs,
        )
        if approval_required_tools and gate_mode == "auto":
            gate_mode = "approval_required"
        gate_service = OrchestratorTurnContextGateService(
            pending_gates=self.pending_gates,
            create_pending_tool_approval_request=self.create_pending_tool_approval_request,
        )
        _pending_gate_request_writer, _approved_tool_request_lookup = gate_service.build_callbacks(
            run_id=data.run_id,
            issue=data.issue,
            seat_name=data.seat_name,
            gate_mode=gate_mode,
            turn_index=data.turn_index,
        )

        architecture_mode = self.resolve_architecture_mode()
        frontend_framework_mode = self.resolve_frontend_framework_mode()
        forced_pattern = "microservices" if architecture_mode == "force_microservices" else None
        if architecture_mode == "force_monolith":
            forced_pattern = "monolith"
        forced_frontend_framework = {"force_vue": "vue", "force_react": "react", "force_angular": "angular"}.get(
            frontend_framework_mode
        )
        process_rules = self.org.process_rules if self.org and isinstance(getattr(self.org, "process_rules", None), dict) else {}
        allowed_tool_rings = [str(token).strip().lower() for token in (process_rules.get("allowed_tool_rings") or ["core"]) if str(token).strip()] or ["core"]
        if isinstance(self.active_capabilities_allowed, list) and self.active_capabilities_allowed:
            allowed_capability_profiles = [str(token).strip().lower() for token in self.active_capabilities_allowed if str(token).strip()]
        else:
            allowed_capability_profiles = [
                str(token).strip().lower()
                for token in (process_rules.get("allowed_capability_profiles") or ["workspace"])
                if str(token).strip()
            ] or ["workspace"]
        run_determinism_class = str(self.active_run_determinism_class or process_rules.get("run_determinism_class") or "workspace").strip().lower()
        if run_determinism_class not in {"pure", "workspace", "external"}:
            run_determinism_class = "workspace"
        compatibility_mappings = (
            {
                str(tool_name).strip(): deepcopy(dict(mapping or {}))
                for tool_name, mapping in self.active_compatibility_mappings.items()
                if str(tool_name).strip() and isinstance(mapping, dict)
            }
            if isinstance(self.active_compatibility_mappings, dict)
            else {}
        )
        resolved_skill_tool_bindings = {
            str(key).strip(): deepcopy(dict(value or {}))
            for key, value in (data.skill_tool_bindings or {}).items()
            if str(key).strip()
        }
        verification_scope_limits = dict(self.resolve_verification_scope_limits())
        protocol_governed_enabled = self.resolve_protocol_governed_enabled()
        max_tool_execution_time = self._resolve_optional_float(process_rules.get("skill_max_execution_time"))
        max_tool_memory = self._resolve_optional_float(process_rules.get("skill_max_memory"))
        project_surface_profile = self.resolve_project_surface_profile()
        small_project_builder_variant = self.resolve_small_project_builder_variant()
        workflow_profile = self.resolve_workflow_profile()
        local_prompting_mode = self.resolve_local_prompting_mode()
        local_prompting_allow_fallback = self.resolve_local_prompting_allow_fallback()
        local_prompting_fallback_profile_id = self.resolve_local_prompting_fallback_profile_id()
        profile_versions = sorted(
            {
                str((row or {}).get("tool_profile_version") or "").strip()
                for row in resolved_skill_tool_bindings.values()
                if str((row or {}).get("tool_profile_version") or "").strip()
            }
        )
        tool_profile_version = profile_versions[0] if len(profile_versions) == 1 else "unknown-v1"
        determinism_controls = deepcopy(self.resolve_protocol_determinism_context())
        context = {
            "session_id": data.run_id,
            "issue_id": data.issue.id,
            "workspace": str(self.workspace_root),
            "role": data.seat_name,
            "roles": list(data.roles_to_load),
            "current_status": data.turn_status.value,
            "selected_model": data.selected_model,
            "turn_index": data.turn_index,
            "dependency_context": deepcopy(data.dependency_context) if data.dependency_context else {"depends_on": list(data.issue.depends_on), "dependency_count": len(data.issue.depends_on), "dependency_statuses": {}, "unresolved_dependencies": []},
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
            "seat_coercion": deepcopy(dict(cards_runtime.get("seat_coercion") or {})),
            "artifact_contract": deepcopy(dict(cards_runtime.get("artifact_contract") or {})),
            "scenario_truth": deepcopy(dict(cards_runtime.get("scenario_truth") or {})),
            "odr_active": bool(cards_runtime.get("odr_active")),
            "audit_mode": str(cards_runtime.get("audit_mode") or ""),
            "odr_valid": deepcopy(cards_runtime.get("odr_valid")),
            "odr_pending_decisions": deepcopy(cards_runtime.get("odr_pending_decisions")),
            "odr_stop_reason": deepcopy(cards_runtime.get("odr_stop_reason")),
            "odr_termination_reason": deepcopy(cards_runtime.get("odr_termination_reason")),
            "odr_final_auditor_verdict": deepcopy(cards_runtime.get("odr_final_auditor_verdict")),
            "odr_artifact_path": str(cards_runtime.get("odr_artifact_path") or ""),
            "odr_requirement": str(cards_runtime.get("odr_requirement") or ""),
            "last_valid_round_index": int(cards_runtime.get("last_valid_round_index") or 0),
            "last_emitted_round_index": int(cards_runtime.get("last_emitted_round_index") or 0),
            "verification_scope": {},
            "stage_gate_mode": gate_mode,
            "approval_required_tools": approval_required_tools,
            "runtime_verifier_ok": data.runtime_verifier_ok,
            "runtime_verifier_enabled": data.runtime_verifier_enabled,
            "runtime_verifier_contract": runtime_verifier_contract,
            "runtime_retry_note": str(params.get("runtime_retry_note") or "") if isinstance(params, dict) else "",
            "prompt_metadata": data.prompt_metadata if data.prompt_metadata is not None else {},
            "prompt_layers": data.prompt_layers if data.prompt_layers is not None else {},
            "architecture_mode": architecture_mode,
            "frontend_framework_mode": frontend_framework_mode,
            "project_surface_profile": project_surface_profile,
            "small_project_builder_variant": small_project_builder_variant,
            "workflow_profile": workflow_profile,
            "architecture_decision_required": str(data.seat_name).strip().lower() == "architect",
            "architecture_decision_path": "agent_output/design.txt",
            "architecture_allowed_patterns": allowed_architecture_patterns(self.architecture_policy),
            "architecture_forced_pattern": forced_pattern,
            "frontend_framework_allowed": ["vue", "react", "angular"],
            "frontend_framework_forced": forced_frontend_framework,
            "idesign_enabled": bool(data.idesign_enabled),
            "create_pending_gate_request": _pending_gate_request_writer,
            "resolve_granted_tool_approval": _approved_tool_request_lookup,
            "resume_mode": bool(data.resume_mode),
            "history": deepcopy(self.history_context_getter(data.seat_name)),
            "skill_contract_enforced": bool(resolved_skill_tool_bindings),
            "skill_tool_bindings": resolved_skill_tool_bindings,
            "tool_profile_version": tool_profile_version,
            "allowed_tool_rings": allowed_tool_rings,
            "allowed_capability_profiles": allowed_capability_profiles,
            "allowed_namespace_scopes": [f"issue:{data.issue.id}"],
            "capabilities_allowed": allowed_capability_profiles,
            "run_namespace_scope": f"issue:{data.issue.id}",
            "run_determinism_class": run_determinism_class,
            "run_determinism_policy": run_determinism_class,
            "compatibility_mappings": compatibility_mappings,
            "max_tool_execution_time": max_tool_execution_time,
            "max_tool_memory": max_tool_memory,
            "protocol_governed_enabled": protocol_governed_enabled,
            "max_response_bytes": self.resolve_protocol_max_response_bytes(),
            "max_tool_calls": self.resolve_protocol_max_tool_calls(),
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
            "prompt_budget_enabled": str(process_rules.get("prompt_budget_enabled") or protocol_governed_enabled).strip().lower() in {"1", "true", "yes", "on", "enabled"} if isinstance(process_rules.get("prompt_budget_enabled"), str) else bool(process_rules.get("prompt_budget_enabled", protocol_governed_enabled)),
            "prompt_budget_require_backend_tokenizer": str(process_rules.get("prompt_budget_require_backend_tokenizer") or "").strip().lower() in {"1", "true", "yes", "on", "enabled"} if isinstance(process_rules.get("prompt_budget_require_backend_tokenizer"), str) else bool(process_rules.get("prompt_budget_require_backend_tokenizer", False)),
            "prompt_budget_policy_path": str(process_rules.get("prompt_budget_policy_path") or "").strip() or str(DEFAULT_PROMPT_BUDGET_PATH),
        }
        available_read_paths = list(await observe_available_required_read_paths(
            required_paths=required_read_paths, workspace=workspace_root,
        ))
        declared_interfaces = list(required_action_tools) + list(approval_required_tools)
        if not required_action_tools:
            defaults = ["read_file", "write_file", "update_issue_status"]
            for interface_name in list(resolved_skill_tool_bindings) or defaults:
                if interface_name not in declared_interfaces:
                    declared_interfaces.append(interface_name)
        for interface_name, enabled in (("read_file", available_read_paths),
                                        ("write_file", required_write_paths),
                                        ("update_issue_status", required_statuses)):
            if enabled and interface_name not in declared_interfaces:
                declared_interfaces.append(interface_name)
        context["verification_scope"] = build_verification_scope(
            workspace=available_read_paths + list(required_write_paths),
            active_context=available_read_paths, passive_context=[], archived_context=[],
            declared_interfaces=declared_interfaces, strict_grounding=True, forbidden_phrases=[],
            enforce_path_hardening=True, consistency_tool_calls_only=True,
            max_workspace_items=verification_scope_limits.get("max_workspace_items"),
            max_active_context_items=verification_scope_limits.get("max_active_context_items"),
            max_passive_context_items=verification_scope_limits.get("max_passive_context_items"),
            max_archived_context_items=verification_scope_limits.get("max_archived_context_items"),
            max_total_context_items=verification_scope_limits.get("max_total_context_items"),
        )
        return context
