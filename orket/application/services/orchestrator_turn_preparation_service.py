from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orket.application.services.cards_odr_stage import run_cards_odr_prebuild
from orket.application.services.orchestrator_prompt_preparation_service import (
    OrchestratorPromptPreparationService,
)
from orket.core.cards_runtime_contract import resolve_cards_runtime
from orket.exceptions import CardNotFound
from orket.logging import log_event
from orket.schema import CardStatus, IssueConfig, RoleConfig
from orket.utils import sanitize_name


@dataclass
class TurnPreparationInput:
    issue: IssueConfig
    epic: Any
    team: Any
    env: Any
    run_id: str
    prompt_strategy_node: Any
    dependency_context: dict[str, Any]
    runtime_result: Any | None
    resume_mode: bool
    model_override: str | None


@dataclass
class TurnPreparationResult:
    stop_execution: bool
    seat_name: str | None = None
    roles_to_load: list[str] | None = None
    turn_status: CardStatus | None = None
    turn_index: int | None = None
    is_guard_turn: bool = False
    role_config: Any | None = None
    provider: Any | None = None
    client: Any | None = None
    context: dict[str, Any] | None = None
    system_prompt: str | None = None


class OrchestratorTurnPreparationService:
    """Owns issue-turn preparation before dispatch reaches the executor."""

    def __init__(
        self,
        *,
        workspace_root: Path,
        organization: Any,
        loader: Any,
        async_cards: Any,
        memory: Any,
        transcript: list[Any],
        router_node: Any,
        loop_policy_node: Any,
        model_client_node: Any,
        support_services: Any,
        request_issue_transition: Callable[..., Awaitable[None]],
        resolve_small_project_team_policy: Callable[[Any, Any], dict[str, Any]],
        build_turn_context: Callable[..., dict[str, Any]],
        resolve_prompt_resolver_mode: Callable[[], str],
        resolve_prompt_selection_policy: Callable[[], str],
        resolve_prompt_selection_strict: Callable[[], bool],
        resolve_prompt_version_exact: Callable[[], str],
        resolve_prompt_patch: Callable[[], str],
        resolve_prompt_patch_label: Callable[[], str],
        close_provider_transport: Callable[[Any], Awaitable[None]],
        select_prompt_strategy_model: Callable[..., str],
        should_suppress_reference_context_for_cards_runtime: Callable[[dict[str, Any] | None], bool],
    ) -> None:
        self.workspace_root = workspace_root
        self.organization = organization
        self.loader = loader
        self.async_cards = async_cards
        self.memory = memory
        self.transcript = transcript
        self.router_node = router_node
        self.loop_policy_node = loop_policy_node
        self.model_client_node = model_client_node
        self.support_services = support_services
        self.request_issue_transition = request_issue_transition
        self.resolve_small_project_team_policy = resolve_small_project_team_policy
        self.build_turn_context = build_turn_context
        self.resolve_prompt_resolver_mode = resolve_prompt_resolver_mode
        self.resolve_prompt_selection_policy = resolve_prompt_selection_policy
        self.resolve_prompt_selection_strict = resolve_prompt_selection_strict
        self.resolve_prompt_version_exact = resolve_prompt_version_exact
        self.resolve_prompt_patch = resolve_prompt_patch
        self.resolve_prompt_patch_label = resolve_prompt_patch_label
        self.close_provider_transport = close_provider_transport
        self.select_prompt_strategy_model = select_prompt_strategy_model
        self.should_suppress_reference_context_for_cards_runtime = (
            should_suppress_reference_context_for_cards_runtime
        )

    async def _load_asset(self, category: str, name: str, model_type: Any) -> Any:
        async_loader = getattr(self.loader, "load_asset_async", None)
        if callable(async_loader):
            try:
                return await async_loader(category, name, model_type)
            except TypeError:
                pass
        return self.loader.load_asset(category, name, model_type)

    async def _resolve_dispatch_target(
        self,
        *,
        data: TurnPreparationInput,
        is_review_turn: bool,
    ) -> tuple[str, dict[str, Any], Any, str, str] | None:
        seat_name = self.router_node.route(data.issue, data.team, is_review_turn)
        small_policy = self.resolve_small_project_team_policy(data.epic, data.team)
        if small_policy["active"] and not is_review_turn:
            normalized_seat = str(seat_name or "").strip().lower()
            if normalized_seat not in {"code_reviewer", "reviewer", "integrity_guard"}:
                seat_name = str(small_policy["builder_seat"])
        runtime_builder_seat = str(data.issue.seat or "").strip() or "coder"
        runtime_reviewer_seat = "integrity_guard"
        if small_policy.get("active"):
            runtime_builder_seat = str(small_policy.get("builder_seat") or runtime_builder_seat)
            runtime_reviewer_seat = str(small_policy.get("reviewer_seat") or runtime_reviewer_seat)
        cards_runtime = resolve_cards_runtime(
            issue=data.issue,
            builder_seat=runtime_builder_seat,
            reviewer_seat=runtime_reviewer_seat,
        )
        invalid_profile_reason = str(cards_runtime.get("invalid_profile_reason") or "").strip()
        if invalid_profile_reason:
            await self.request_issue_transition(
                issue=data.issue,
                target_status=CardStatus.BLOCKED,
                reason="governance_violation",
                metadata={
                    "run_id": data.run_id,
                    "error": invalid_profile_reason,
                    "execution_profile": cards_runtime.get("execution_profile"),
                },
            )
            log_event(
                "cards_runtime_preflight_failed",
                {
                    "run_id": data.run_id,
                    "issue_id": data.issue.id,
                    "execution_profile": cards_runtime.get("execution_profile"),
                    "artifact_contract": cards_runtime.get("artifact_contract"),
                    "error": invalid_profile_reason,
                },
                self.workspace_root,
            )
            return None
        seat_obj = data.team.seats.get(sanitize_name(seat_name))
        if not seat_obj:
            await self.request_issue_transition(
                issue=data.issue,
                target_status=self.loop_policy_node.missing_seat_status(),
                reason="missing_seat",
                metadata={"seat": seat_name, "run_id": data.run_id},
            )
            return None
        return str(seat_name), cards_runtime, seat_obj, runtime_builder_seat, runtime_reviewer_seat

    async def prepare(
        self,
        *,
        data: TurnPreparationInput,
    ) -> TurnPreparationResult:
        is_review_turn = self.loop_policy_node.is_review_turn(data.issue.status)
        dispatch_target = await self._resolve_dispatch_target(data=data, is_review_turn=is_review_turn)
        if dispatch_target is None:
            return TurnPreparationResult(stop_execution=True)
        seat_name, cards_runtime, seat_obj, runtime_builder_seat, runtime_reviewer_seat = dispatch_target
        is_guard_turn = is_review_turn and ("integrity_guard" in list(seat_obj.roles))
        turn_status = self.loop_policy_node.turn_status_for_issue(is_review_turn)
        turn_index = len(self.transcript) + 1
        if is_guard_turn:
            turn_status = CardStatus.AWAITING_GUARD_REVIEW
        current_issue_status = getattr(data.issue, "status", None)
        if not (data.resume_mode and current_issue_status == turn_status):
            await self.request_issue_transition(
                issue=data.issue,
                target_status=turn_status,
                assignee=seat_name,
                reason="turn_dispatch",
                metadata={"run_id": data.run_id, "review_turn": is_review_turn, "turn_index": turn_index},
                roles=list(seat_obj.roles),
            )
        elif hasattr(data.issue, "assignee") and getattr(data.issue, "assignee", None) is None:
            data.issue.assignee = seat_name
            await self.async_cards.save(data.issue.model_dump())
            log_event(
                "resume_turn_dispatch_preserved",
                {
                    "run_id": data.run_id,
                    "issue_id": data.issue.id,
                    "seat": seat_name,
                    "status": turn_status.value if hasattr(turn_status, "value") else str(turn_status),
                    "turn_index": turn_index,
                },
                self.workspace_root,
            )

        roles_to_load = self.loop_policy_node.role_order_for_turn(list(seat_obj.roles), is_review_turn)
        try:
            role_config = await self._load_asset("roles", roles_to_load[0], RoleConfig)
        except CardNotFound:
            await self.request_issue_transition(
                issue=data.issue,
                target_status=CardStatus.IN_PROGRESS,
                reason="missing_role_asset",
                metadata={"role": roles_to_load[0], "run_id": data.run_id, "turn_index": turn_index},
                roles=roles_to_load,
            )
            log_event(
                "missing_role_asset",
                {"run_id": data.run_id, "issue_id": data.issue.id, "role": roles_to_load[0]},
                self.workspace_root,
            )
            return TurnPreparationResult(stop_execution=True)

        selected_model = self.select_prompt_strategy_model(
            prompt_strategy_node=data.prompt_strategy_node,
            role=roles_to_load[0],
            asset_config=data.epic,
            override=data.model_override,
        )
        model_selection_decision = {}
        if hasattr(data.prompt_strategy_node, "model_selector"):
            selector = data.prompt_strategy_node.model_selector
            if hasattr(selector, "get_last_selection_decision"):
                model_selection_decision = dict(selector.get_last_selection_decision() or {})
        if model_selection_decision:
            log_event(
                "model_selection_decision",
                {
                    "run_id": data.run_id,
                    "issue_id": data.issue.id,
                    "role": roles_to_load[0],
                    "decision": model_selection_decision,
                },
                self.workspace_root,
            )

        provider = self.model_client_node.create_provider(selected_model, data.env)
        client = self.model_client_node.create_client(provider)
        if bool(cards_runtime.get("odr_active")) and not is_review_turn:
            odr_auditor_model = (
                str(cards_runtime.get("odr_auditor_model") or "").strip()
                or str(os.environ.get("ORKET_ODR_AUDITOR_MODEL") or "").strip()
                or selected_model
            )
            odr_auditor_provider = None
            try:
                odr_auditor_provider = self.model_client_node.create_provider(odr_auditor_model, data.env)
                odr_auditor_client = self.model_client_node.create_client(odr_auditor_provider)
                odr_result = await run_cards_odr_prebuild(
                    workspace=self.workspace_root,
                    issue=data.issue,
                    run_id=data.run_id,
                    selected_model=selected_model,
                    cards_runtime=cards_runtime,
                    model_client=client,
                    auditor_client=odr_auditor_client,
                    async_cards=self.async_cards,
                )
            except (RuntimeError, ValueError, TypeError, OSError, AttributeError):
                await self.close_provider_transport(provider)
                raise
            finally:
                if odr_auditor_provider is not None:
                    await self.close_provider_transport(odr_auditor_provider)
            cards_runtime = resolve_cards_runtime(
                issue=data.issue,
                builder_seat=runtime_builder_seat,
                reviewer_seat=runtime_reviewer_seat,
            )
            await provider.clear_context()
            if not bool(odr_result.get("odr_accepted")):
                await self.request_issue_transition(
                    issue=data.issue,
                    target_status=CardStatus.BLOCKED,
                    reason="odr_prebuild_failed",
                    metadata={
                        "run_id": data.run_id,
                        "odr_stop_reason": odr_result.get("odr_stop_reason"),
                        "odr_termination_reason": odr_result.get("odr_termination_reason"),
                        "odr_final_auditor_verdict": odr_result.get("odr_final_auditor_verdict"),
                        "execution_profile": cards_runtime.get("execution_profile"),
                    },
                )
                await self.close_provider_transport(provider)
                return TurnPreparationResult(stop_execution=True)

        prompt_service = OrchestratorPromptPreparationService(
            organization=self.organization,
            memory=self.memory,
            support_services=self.support_services,
            build_turn_context=self.build_turn_context,
            resolve_prompt_resolver_mode=self.resolve_prompt_resolver_mode,
            resolve_prompt_selection_policy=self.resolve_prompt_selection_policy,
            resolve_prompt_selection_strict=self.resolve_prompt_selection_strict,
            resolve_prompt_version_exact=self.resolve_prompt_version_exact,
            resolve_prompt_patch=self.resolve_prompt_patch,
            resolve_prompt_patch_label=self.resolve_prompt_patch_label,
            should_suppress_reference_context_for_cards_runtime=(
                self.should_suppress_reference_context_for_cards_runtime
            ),
            load_asset=self._load_asset,
        )
        context, system_prompt = await prompt_service.build(
            issue=data.issue,
            epic=data.epic,
            run_id=data.run_id,
            seat_name=seat_name,
            roles_to_load=roles_to_load,
            turn_status=turn_status,
            selected_model=selected_model,
            dependency_context=data.dependency_context,
            runtime_result=data.runtime_result,
            resume_mode=data.resume_mode,
            cards_runtime=cards_runtime,
            role_config=role_config,
            prompt_strategy_node=data.prompt_strategy_node,
        )
        return TurnPreparationResult(
            stop_execution=False,
            seat_name=seat_name,
            roles_to_load=roles_to_load,
            turn_status=turn_status,
            turn_index=turn_index,
            is_guard_turn=is_guard_turn,
            role_config=role_config,
            provider=provider,
            client=client,
            context=context,
            system_prompt=system_prompt,
        )
