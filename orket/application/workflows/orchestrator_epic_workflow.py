"""Ordered epic preflight and dispatch through phase-selected application effects."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from orket.application.services.card_dependency_service import CardDispatchSnapshot
from orket.application.services.decision_context_service import capture_backlog_inputs
from orket.application.services.epic_dispatch_batch import run_epic_dispatch_batch
from orket.application.services.loop_decision_service import recommend_exhaustion, recommend_no_candidate
from orket.application.services.orchestrator_team_replan import Emit
from orket.core.contracts.decision_inputs import LoopPolicyInputs, PlanningCardInput
from orket.core.domain.records import IssueRecord
from orket.decision_nodes.contracts import OrchestrationLoopPolicyNode
from orket.exceptions import ExecutionFailed
from orket.schema import EpicConfig, TeamConfig


def preflight_epic_team(
    epic: EpicConfig, team: TeamConfig, run_id: str, *,
    select_team: Callable[[], dict[str, object]], should_inject: Callable[[], bool],
    inject_reviewer: Callable[[], str], emit: Emit,
) -> None:
    small_policy = select_team()
    if small_policy["active"] and not small_policy["reviewer_seat"] and should_inject():
        injected_seat = inject_reviewer()
        emit(
            "team_policy_auto_injected_code_reviewer",
            {
                "run_id": run_id,
                "epic": epic.name,
                "injected_seat": injected_seat,
                "reason": "small_project_missing_code_reviewer",
            },
        )
        small_policy = select_team()
    if small_policy["active"] and not small_policy["reviewer_seat"]:
        available_seats = sorted((getattr(team, "seats", {}) or {}).keys())
        emit(
            "team_policy_preflight_failed",
            {
                "run_id": run_id,
                "epic": epic.name,
                "reason": "missing_code_reviewer_seat",
                "small_project_policy": small_policy,
                "available_seats": available_seats,
            },
        )
        raise ExecutionFailed(
            "Small-project policy preflight failed: missing code_reviewer seat. "
            f"Available seats={available_seats}. Add a seat with role 'code_reviewer' "
            "or increase small_project_issue_threshold to disable small-team mode for this epic."
        )
    emit(
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
    )


async def run_epic_loop(
    *, epic: EpicConfig, run_id: str, approval_resume_turns: dict[str, int] | None,
    loop_node: OrchestrationLoopPolicyNode, loop_inputs: Callable[[], LoopPolicyInputs],
    read_dispatch: Callable[[], Awaitable[CardDispatchSnapshot]],
    maybe_replan: Callable[[list[IssueRecord]], Awaitable[bool]],
    plan_dispatch: Callable[[CardDispatchSnapshot], list[IssueRecord]],
    propagate_blocks: Callable[[list[IssueRecord]], Awaitable[int]],
    dispatch_turn: Callable[[IssueRecord], Awaitable[None]],
    read_final_backlog: Callable[[], Awaitable[list[IssueRecord]]], emit: Emit,
) -> None:
    concurrency_limit = loop_node.concurrency_limit(loop_inputs())
    semaphore = asyncio.Semaphore(concurrency_limit)
    emit("orchestrator_hyper_loop_start", {"epic": epic.name, "run_id": run_id, "concurrency": concurrency_limit})
    iteration_count = 0
    max_iterations = loop_node.max_iterations(loop_inputs())
    while iteration_count < max_iterations:
        iteration_count += 1
        dispatch = await read_dispatch()
        backlog = list(dispatch.backlog)
        backlog_inputs = capture_backlog_inputs(backlog)
        if await maybe_replan(backlog):
            continue
        candidates = plan_dispatch(dispatch)
        if approval_resume_turns:
            candidates = [card for card in dispatch.eligible if card.id in approval_resume_turns]
            if {card.id for card in candidates} != set(approval_resume_turns):
                raise ExecutionFailed("E_EPIC_APPROVAL_CARD_NOT_DISPATCHABLE")
        if not candidates:
            if await _stop_without_candidates(
                backlog, backlog_inputs, dispatch, loop_node, run_id, epic, iteration_count,
                propagate_blocks=propagate_blocks, emit=emit,
            ):
                break
            continue
        emit("orchestrator_tick", {"run_id": run_id, "candidate_count": len(candidates), "iteration": iteration_count})

        async def semaphore_wrapper(issue_data: IssueRecord) -> None:
            async with semaphore:
                await dispatch_turn(issue_data)

        await run_epic_dispatch_batch(candidates, semaphore_wrapper)
    if iteration_count >= max_iterations:
        final_backlog = await read_final_backlog()
        should_raise = recommend_exhaustion(loop_node, iteration_count, max_iterations,
                                            capture_backlog_inputs(final_backlog))
        if should_raise:
            raise ExecutionFailed(f"Hyper-Loop exhausted iterations ({max_iterations})")


async def _stop_without_candidates(
    backlog: list[IssueRecord], backlog_inputs: tuple[PlanningCardInput, ...], dispatch: CardDispatchSnapshot,
    loop_node: OrchestrationLoopPolicyNode, run_id: str, epic: EpicConfig, iteration_count: int,
    *, propagate_blocks: Callable[[list[IssueRecord]], Awaitable[int]], emit: Emit,
) -> bool:
    propagated_count = await propagate_blocks(backlog)
    if propagated_count:
        return False
    outcome = recommend_no_candidate(loop_node, backlog_inputs)
    if outcome.is_done:
        # Loop termination is not authority for accepted build completion.
        emit("orchestrator_epic_stopped", {"epic": epic.name, "run_id": run_id})
        return True
    backlog_snapshot = [
        {
            "id": getattr(item, "id", "unknown"),
            "status": getattr(item.status, "value", str(item.status)) if hasattr(item, "status") else "unknown",
        }
        for item in backlog
    ]
    reason = outcome.reason or "No executable candidates while backlog incomplete."
    emit(
        "orchestrator_stalled",
        {
            "run_id": run_id,
            "epic": epic.name,
            "iteration": iteration_count,
            "reason": reason,
            "backlog": backlog_snapshot,
            "dependency_rejections": dispatch.dependency_rejections,
        },
    )
    raise ExecutionFailed(reason)
