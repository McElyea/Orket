"""Compose captured turn-context inputs at the orchestrator's existing use point."""
from typing import Any

from orket.application.services import orchestrator_prompt_policy, orchestrator_protocol_policy
from orket.application.services import orchestrator_runtime_policy as orchestrator_policy
from orket.application.services.orchestrator_turn_context_builder import (
    OrchestratorTurnContextBuilder,
    TurnContextBuildInput,
)
from orket.schema import CardStatus, IssueConfig


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


async def _build_turn_context(
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
        architecture_policy=self.architecture_policy,
        workspace_root=self.workspace,
        org=self.org,
        loop_policy_node=self.loop_policy_node,
        pending_gates=self.pending_gates,
        history_context_getter=lambda current_seat: self._history_context(seat_name=current_seat),
        create_pending_tool_approval_request=self._create_pending_tool_approval_request,
        resolve_architecture_mode=lambda: orchestrator_policy.select_architecture_mode(user_settings=self.support_services.load_user_settings(), process_rules=orchestrator_policy.organization_process_rules(self.org), environment=self.decision_environment, architecture_policy=self.architecture_policy),
        resolve_frontend_framework_mode=lambda: orchestrator_policy.select_frontend_framework_mode(user_settings=self.support_services.load_user_settings(), process_rules=orchestrator_policy.organization_process_rules(self.org)),
        resolve_project_surface_profile=lambda: orchestrator_policy.select_project_surface_profile(user_settings=self.support_services.load_user_settings(), process_rules=orchestrator_policy.organization_process_rules(self.org)),
        resolve_small_project_builder_variant=lambda: orchestrator_policy.select_small_project_builder_variant(user_settings=self.support_services.load_user_settings(), process_rules=orchestrator_policy.organization_process_rules(self.org)),
        resolve_workflow_profile=lambda: orchestrator_policy.select_workflow_profile(process_rules=orchestrator_policy.organization_process_rules(self.org)),
        resolve_verification_scope_limits=lambda: orchestrator_policy.select_verification_scope_limits(org=self.org),
        resolve_protocol_governed_enabled=lambda: orchestrator_protocol_policy.select_protocol_governed_enabled(user_settings=self.support_services.load_user_settings(), process_rules=orchestrator_policy.organization_process_rules(self.org)),
        resolve_protocol_max_response_bytes=lambda: orchestrator_protocol_policy.select_protocol_max_response_bytes(user_settings=self.support_services.load_user_settings(), process_rules=orchestrator_policy.organization_process_rules(self.org)),
        resolve_protocol_max_tool_calls=lambda: orchestrator_protocol_policy.select_protocol_max_tool_calls(user_settings=self.support_services.load_user_settings(), process_rules=orchestrator_policy.organization_process_rules(self.org)),
        resolve_protocol_determinism_context=lambda: orchestrator_protocol_policy.select_protocol_determinism_context(process_rules=orchestrator_policy.organization_process_rules(self.org), user_settings=self.support_services.load_user_settings()),
        resolve_local_prompting_mode=lambda: orchestrator_prompt_policy.select_local_prompting_mode(process_rules=orchestrator_policy.organization_process_rules(self.org), user_settings=self.support_services.load_user_settings()),
        resolve_local_prompting_allow_fallback=lambda: orchestrator_prompt_policy.select_local_prompting_allow_fallback(process_rules=orchestrator_policy.organization_process_rules(self.org), user_settings=self.support_services.load_user_settings()),
        resolve_local_prompting_fallback_profile_id=lambda: orchestrator_prompt_policy.select_local_prompting_fallback_profile_id(process_rules=orchestrator_policy.organization_process_rules(self.org), user_settings=self.support_services.load_user_settings()),
        active_capabilities_allowed=getattr(self, "active_capabilities_allowed", None),
        active_run_determinism_class=getattr(self, "active_run_determinism_class", None),
        active_compatibility_mappings=getattr(self, "active_compatibility_mappings", None),
    )
    return await builder.build(
        TurnContextBuildInput(
            run_id=run_id,
            issue=issue,
            seat_name=seat_name,
            roles_to_load=roles_to_load,
            turn_status=turn_status,
            selected_model=selected_model,
            turn_index=turn_index,
            dependency_context=dependency_context,
            runtime_verifier_ok=runtime_verifier_ok, runtime_verifier_enabled=not orchestrator_policy.select_bool_flag('ORKET_DISABLE_RUNTIME_VERIFIER', 'disable_runtime_verifier', process_rules=orchestrator_policy.organization_process_rules(self.org)),
            prompt_metadata=prompt_metadata,
            prompt_layers=prompt_layers,
            idesign_enabled=idesign_enabled,
            resume_mode=resume_mode,
            skill_tool_bindings=skill_tool_bindings,
            cards_runtime=cards_runtime,
        )
    )
