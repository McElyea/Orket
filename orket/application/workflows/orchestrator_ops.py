
import inspect
from typing import Any

from orket.application.services import (
    orchestrator_prompt_policy,
    orchestrator_protocol_policy,
    orchestrator_team_policy,
)
from orket.application.services import orchestrator_runtime_policy as orchestrator_policy
from orket.application.services.card_completion_turn_service import prepare_card_completion_turn
from orket.application.services.card_dependency_service import (
    build_card_dependency_context,
    read_card_dispatch_snapshot,
)
from orket.application.services.epic_setup_service import prepare_epic_workspace
from orket.application.services.guard_review_payload import guard_review_for_turn
from orket.application.services.loop_decision_service import (
    capture_seat_policy_input,
    validate_guard_review,
)
from orket.application.services.model_selection_service import ModelSelectionService
from orket.application.services.orchestrator_failure_handler import OrchestratorFailureHandler
from orket.application.services.orchestrator_issue_transitions import (
    clear_issue_runtime_retry_note,
    set_issue_runtime_retry_note,
)
from orket.application.services.orchestrator_review_preflight_service import (
    OrchestratorReviewPreflightService,
)
from orket.application.services.orchestrator_team_replan import propagate_dependency_blocks
from orket.application.services.orchestrator_turn_context_builder import (
    OrchestratorTurnContextBuilder,
    TurnContextBuildInput,
)
from orket.application.services.orchestrator_turn_context_policy import resolve_policy_token
from orket.application.services.orchestrator_turn_preparation_service import (
    OrchestratorTurnPreparationService,
    TurnPreparationInput,
)
from orket.application.services.orchestrator_turn_success_handler import (
    OrchestratorTurnSuccessHandler,
)
from orket.application.services.tool_gate_service import ToolGate
from orket.application.services.toolbox import ToolBox
from orket.application.workflows.orchestrator_epic_workflow import preflight_epic_team, run_epic_loop
from orket.application.workflows.orchestrator_turn_workflow import run_issue_turn_phases, run_prepared_issue_turn
from orket.application.workflows.turn_executor import TurnExecutor
from orket.core.cards_runtime_contract import apply_epic_cards_runtime_defaults, resolve_cards_runtime
from orket.core.domain.execution import ExecutionTurn
from orket.core.domain.guard_review import GuardReviewPayload
from orket.core.domain.state_machine import StateMachine
from orket.exceptions import ExecutionFailed
from orket.logging import log_event
from orket.runtime_paths import control_plane_db_for_runtime
from orket.schema import (
    CardStatus,
    EnvironmentConfig,
    EpicConfig,
    IssueConfig,
    RoleConfig,
    TeamConfig,
)
from orket.settings import (
    load_user_preferences_async,
    load_user_settings_async,
    set_runtime_settings_context,
)


async def _close_provider_transport(provider: Any) -> None:
    close_method = getattr(provider, "close", None)
    if not callable(close_method):
        return
    maybe_awaitable = close_method()
    if inspect.isawaitable(maybe_awaitable):
        await maybe_awaitable


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
    approval_resume_turns: dict[str, int] | None = None,
) -> None:
    """Compose epic phases while selecting replaceable effects at their use point."""
    loop_node = self.loop_policy_node
    user_settings = await load_user_settings_async()
    preferences = await load_user_preferences_async()
    set_runtime_settings_context(user_settings=user_settings, user_preferences=preferences)
    preflight_epic_team(
        epic, team, run_id, select_team=lambda: self._resolve_small_project_team_policy(epic, team),
        should_inject=lambda: orchestrator_team_policy.should_auto_inject_small_project_reviewer(self.org),
        inject_reviewer=lambda: orchestrator_team_policy.auto_inject_small_project_reviewer_seat(self.org, team),
        emit=lambda event, fields: log_event(event, fields, self.workspace),
    )
    if approval_resume_turns is None:
        await prepare_epic_workspace(self, epic, run_id)
    model_selection = await ModelSelectionService(environment=self.decision_environment).prepare(
        self.org, preferences, user_settings, strategy=self.decision_nodes.resolve_prompt_strategy(self.org),
    )
    tool_gate = ToolGate(organization=self.org, workspace_root=self.workspace)
    from orket.application.services.turn_tool_control_plane_service import build_turn_tool_control_plane_service
    turn_tool_control_plane_db_path = control_plane_db_for_runtime(runtime_db=self.db_path)
    executor = TurnExecutor(
        StateMachine(), tool_gate, self.workspace, utc_now=self.turn_clock,
        control_plane_service=build_turn_tool_control_plane_service(turn_tool_control_plane_db_path),
    )
    from orket.policy import create_session_policy
    policy = create_session_policy(str(self.workspace), epic.references)
    toolbox = ToolBox(
        policy, str(self.workspace), epic.references, db_path=self.db_path, cards_repo=self.async_cards,
        tool_gate=tool_gate, organization=self.org, decision_nodes=self.decision_nodes, card_completion=self.card_completion,
    )
    await run_epic_loop(
        epic=epic, run_id=run_id, approval_resume_turns=approval_resume_turns, loop_node=loop_node,
        loop_inputs=lambda: self.loop_inputs,
        read_dispatch=lambda: read_card_dispatch_snapshot(cards=self.async_cards, build_id=active_build),
        maybe_replan=lambda backlog: self.team_replan.maybe_schedule(
            backlog, run_id, active_build, team,
            request_transition=lambda **fields: self._request_issue_transition(**fields), cards=lambda: self.async_cards,
            select_team=lambda current_epic, current_team: self._resolve_small_project_team_policy(current_epic, current_team),
            child_publication=lambda: getattr(self, "scheduler_control_plane", None),
            emit=lambda event, fields: log_event(event, fields, self.workspace),
        ),
        plan_dispatch=lambda dispatch: dispatch.plan(self.planner_node, target_issue_id),
        propagate_blocks=lambda backlog: propagate_dependency_blocks(
            backlog, run_id, request_transition=lambda **fields: self._request_issue_transition(**fields),
            emit=lambda event, fields: log_event(event, fields, self.workspace),
        ),
        dispatch_turn=lambda issue_data: self._execute_issue_turn(
            issue_data, epic, team, env, run_id, active_build, model_selection, executor, toolbox,
            resume_mode=resume_mode, model_override=model_override,
            **({"approval_turn_index": approval_resume_turns.pop(issue_data.id, None)}
               if approval_resume_turns is not None else {}),
        ),
        read_final_backlog=lambda: self.async_cards.get_by_build(active_build),
        emit=lambda event, fields: log_event(event, fields, self.workspace),
    )


async def _execute_issue_turn(
    self: Any, issue_data: Any, epic: EpicConfig, team: TeamConfig, env: EnvironmentConfig,
    run_id: str, active_build: str, model_selection: Any, executor: TurnExecutor, toolbox: ToolBox,
    resume_mode: bool = False, model_override: str | None = None, approval_turn_index: int | None = None,
) -> None:
    """Admit the issue and compose each turn phase at its original selection point."""
    issue = IssueConfig.model_validate(issue_data.model_dump())
    issue.params = apply_epic_cards_runtime_defaults(
        issue_params=getattr(issue, "params", None), epic_params=getattr(epic, "params", None),
    )
    cards_runtime = resolve_cards_runtime(issue=issue)
    is_review_turn = self.loop_policy_node.is_review_turn(issue.status)
    dependency_context = await self._build_dependency_context(issue)
    if dependency_context["unresolved_dependencies"]:
        raise ExecutionFailed("E_CARD_DEPENDENCY_UNSATISFIED:" + ",".join(dependency_context["unresolved_dependencies"]))
    await run_issue_turn_phases(
        issue=issue, run_id=run_id, is_review_turn=is_review_turn, cards_runtime=cards_runtime,
        build_preflight=lambda: OrchestratorReviewPreflightService(
            workspace_root=self.workspace, utc_now=self.turn_clock, organization=self.org,
            support_services=self.support_services, async_cards=self.async_cards, notes=self.notes, transcript=self.transcript,
            request_issue_transition=self._request_issue_transition, verify_issue=self.verify_issue,
            resolve_project_surface_profile=lambda: orchestrator_policy.select_project_surface_profile(user_settings=self.support_services.load_user_settings(), process_rules=orchestrator_policy.organization_process_rules(self.org)),
            resolve_architecture_pattern=lambda: orchestrator_policy.select_architecture_pattern(orchestrator_policy.select_architecture_mode(user_settings=self.support_services.load_user_settings(), process_rules=orchestrator_policy.organization_process_rules(self.org), environment=self.decision_environment, architecture_policy=self.architecture_policy)),
            is_runtime_verifier_disabled=lambda: orchestrator_policy.select_bool_flag('ORKET_DISABLE_RUNTIME_VERIFIER', 'disable_runtime_verifier', process_rules=orchestrator_policy.organization_process_rules(self.org)),
            set_issue_runtime_retry_note=set_issue_runtime_retry_note, clear_issue_runtime_retry_note=clear_issue_runtime_retry_note,
        ),
        build_preparation=lambda: OrchestratorTurnPreparationService(
            workspace_root=self.workspace, organization=self.org, loader=self.loader, async_cards=self.async_cards,
            memory=self.memory, transcript=self.transcript, router_node=self.router_node, loop_policy_node=self.loop_policy_node,
            model_clients=self.model_clients, environment=self.decision_environment, support_services=self.support_services,
            request_issue_transition=self._request_issue_transition, resolve_small_project_team_policy=self._resolve_small_project_team_policy,
            build_turn_context=self._build_turn_context,
            resolve_prompt_resolver_mode=lambda: orchestrator_prompt_policy.select_prompt_resolver_mode(process_rules=orchestrator_policy.organization_process_rules(self.org)),
            resolve_prompt_selection_policy=lambda: orchestrator_prompt_policy.select_prompt_selection_policy(process_rules=orchestrator_policy.organization_process_rules(self.org)),
            resolve_prompt_selection_strict=lambda: orchestrator_prompt_policy.select_prompt_selection_strict(process_rules=orchestrator_policy.organization_process_rules(self.org)),
            resolve_prompt_version_exact=lambda: orchestrator_prompt_policy.select_prompt_version_exact(process_rules=orchestrator_policy.organization_process_rules(self.org)),
            resolve_prompt_patch=lambda: orchestrator_prompt_policy.select_prompt_patch(process_rules=orchestrator_policy.organization_process_rules(self.org)),
            resolve_prompt_patch_label=lambda: orchestrator_prompt_policy.select_prompt_patch_label(process_rules=orchestrator_policy.organization_process_rules(self.org)),
            close_provider_transport=_close_provider_transport,
            should_suppress_reference_context_for_cards_runtime=_should_suppress_reference_context_for_cards_runtime,
        ),
        preparation_input=lambda runtime_result: TurnPreparationInput(
            issue=issue, epic=epic, team=team, env=env, run_id=run_id, model_selection=model_selection,
            dependency_context=dependency_context, runtime_result=runtime_result, resume_mode=resume_mode,
            model_override=model_override, approval_turn_index=approval_turn_index,
        ),
        execute_prepared=lambda preparation: run_prepared_issue_turn(
            preparation, issue=issue, epic=epic, team=team, env=env, run_id=run_id, active_build=active_build, is_review_turn=is_review_turn,
            prepare_card=lambda context, seat_name, turn_index: prepare_card_completion_turn(
                service=self.card_completion, cards=self.async_cards, context=context,
                card_id=issue.id, session_id=run_id, seat_name=seat_name, turn_index=turn_index),
            emit=lambda event, fields: log_event(event, fields, self.workspace),
            dispatch=lambda role_config, client, context, system_desc: self._dispatch_turn(
                executor=executor, issue=issue, role_config=role_config, client=client, toolbox=toolbox, context=context, system_prompt=system_desc),
            build_success_handler=lambda: OrchestratorTurnSuccessHandler(
                workspace_root=self.workspace, transcript=self.transcript, async_cards=self.async_cards, memory=self.memory,
                evaluator_node=self.evaluator_node, issue_control_plane=getattr(self, "issue_control_plane", None),
                request_issue_transition=self._request_issue_transition, trigger_sandbox=self._trigger_sandbox,
                is_sandbox_disabled=lambda: orchestrator_policy.select_bool_flag('ORKET_DISABLE_SANDBOX', 'disable_sandbox', process_rules=orchestrator_policy.organization_process_rules(self.org)),
                save_checkpoint=self._save_checkpoint, create_pending_gate_request=self._create_pending_gate_request,
                validate_guard_rejection_payload=self._validate_guard_rejection_payload, extract_guard_review_payload=self._extract_guard_review_payload,
                resolve_guard_event=self._resolve_guard_event, handle_failure=self._handle_failure,
            ),
            handle_failure=lambda result, roles_to_load, turn_index: self._handle_failure(issue, result, run_id, roles_to_load, turn_index=turn_index),
            close_provider=lambda provider: _close_provider_transport(provider),
        ),
    )


def _validate_guard_rejection_payload(self: Any, payload: GuardReviewPayload) -> dict[str, Any]:
    return dict(validate_guard_review(self.loop_policy_node, payload))


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
    gate_mode = resolve_policy_token(loop_policy_node=self.loop_policy_node, attribute="gate_mode_for_seat",
        inputs=capture_seat_policy_input(seat_name, issue, turn_status), default="auto")
    request_created_at = self.turn_clock().isoformat()
    publisher = getattr(self, "tool_approval_control_plane_reservation", None)
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


async def _build_dependency_context(self: Any, issue: IssueConfig) -> dict[str, Any]:
    return await build_card_dependency_context(cards=self.async_cards, issue=issue)


def _extract_guard_review_payload(self: Any, turn: ExecutionTurn) -> GuardReviewPayload:
    return guard_review_for_turn(turn)

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
        "timestamp": self.turn_clock().isoformat(),
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
        report_timestamp=self.failure_report_clock(),
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
