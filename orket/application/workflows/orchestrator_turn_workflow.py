"""Ordered turn phases over existing service owners and phase-selected effects."""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from orket.application.services.orchestrator_review_preflight_service import OrchestratorReviewPreflightService
from orket.application.services.orchestrator_team_replan import Emit
from orket.application.services.orchestrator_turn_preparation_service import (
    OrchestratorTurnPreparationService,
    TurnPreparationInput,
    TurnPreparationResult,
)
from orket.application.services.orchestrator_turn_success_handler import OrchestratorTurnSuccessHandler
from orket.application.workflows.turn_executor import TurnResult
from orket.schema import CardStatus, EnvironmentConfig, EpicConfig, IssueConfig, TeamConfig


async def run_issue_turn_phases(
    *, issue: IssueConfig, run_id: str, is_review_turn: bool, cards_runtime: dict[str, object],
    build_preflight: Callable[[], OrchestratorReviewPreflightService],
    build_preparation: Callable[[], OrchestratorTurnPreparationService],
    preparation_input: Callable[[object], TurnPreparationInput],
    execute_prepared: Callable[[TurnPreparationResult], Awaitable[None]],
) -> None:
    preflight = build_preflight()
    preflight_result = await preflight.run(
        issue=issue, run_id=run_id, is_review_turn=is_review_turn, cards_runtime=cards_runtime,
    )
    runtime_result = preflight_result.runtime_result
    if preflight_result.stop_execution:
        return
    preparation_service = build_preparation()
    preparation = await preparation_service.prepare(data=preparation_input(runtime_result))
    if preparation.stop_execution:
        return
    await execute_prepared(preparation)


async def run_prepared_issue_turn(
    preparation: TurnPreparationResult, *, issue: IssueConfig, epic: EpicConfig, team: TeamConfig,
    env: EnvironmentConfig, run_id: str, active_build: str, is_review_turn: bool,
    prepare_card: Callable[[dict[str, object], str, int], Awaitable[str]], emit: Emit,
    dispatch: Callable[[object, object, dict[str, object], str], Awaitable[TurnResult]],
    build_success_handler: Callable[[], OrchestratorTurnSuccessHandler],
    handle_failure: Callable[[TurnResult, list[str], int], Awaitable[None]],
    close_provider: Callable[[object], Awaitable[None]],
) -> None:
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
        system_desc += await prepare_card(context, seat_name, turn_index)
        emit("orchestrator_dispatch", {"run_id": run_id, "seat": seat_name, "issue_id": issue.id, "status": issue.status.value})
        result = await dispatch(role_config, client, context, system_desc)
        if result.success:
            success_handler = build_success_handler()
            await success_handler.handle(
                issue=issue, result=result, provider=provider, run_id=run_id, seat_name=seat_name,
                roles_to_load=roles_to_load, turn_index=turn_index, turn_status=turn_status,
                is_guard_turn=is_guard_turn, is_review_turn=is_review_turn, epic=epic, team=team,
                env=env, active_build=active_build, context=context,
            )
        else:
            await handle_failure(result, roles_to_load, turn_index)
    finally:
        await close_provider(provider)
