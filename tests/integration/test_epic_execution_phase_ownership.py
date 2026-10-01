"""Integration: public epic loop, native cards and scheduler truth; no inference."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.application.services.orchestrator_issue_control_plane_support import scheduler_run_id_for_transition
from orket.application.services.orchestrator_team_replan import TeamReplanScheduler
from orket.application.workflows import orchestrator_ops
from orket.core.contracts.decision_inputs import LoopPolicyInputs
from orket.core.contracts.logging_inputs import LoggingInputs
from orket.core.domain import RunState
from orket.decision_nodes.builtins import DefaultOrchestrationLoopPolicyNode, DefaultPlannerNode
from orket.logging import bind_logging, prepare_logging
from orket.schema import CardStatus, EnvironmentConfig, EpicConfig, IssueConfig, SeatConfig, TeamConfig
from tests.integration.test_orchestrator_scheduler_control_plane import _assert_scheduler_truth, _build_orchestrator

pytestmark = pytest.mark.integration


async def _inputs(tmp_path, ids):
    cards = AsyncCardRepository(tmp_path / "cards.sqlite3")
    for card_id in ids:
        await cards.save(IssueConfig(id=card_id, summary=card_id, seat="coder", status=CardStatus.READY,
            build_id="build-1", session_id="run-phase").model_dump())
    orch = _build_orchestrator(tmp_path, cards)
    orch.loop_policy_node = DefaultOrchestrationLoopPolicyNode()
    orch.loop_inputs = LoopPolicyInputs(concurrency=1, max_iterations=1)
    epic = EpicConfig(id="EPIC-1", name="Phase proof", team="core", environment="dev")
    team = TeamConfig(name="core", seats={"coder": SeatConfig(name="Coder", roles=["coder"])})
    return orch, cards, epic, team


async def _execute(orch, epic, team, approvals):
    # Bind in the task that actually calls execute_epic; context inheritance is insufficient.
    with bind_logging(await prepare_logging(LoggingInputs(orch.workspace))):
        return await orch.execute_epic(active_build="build-1", run_id="run-phase", epic=epic, team=team,
            env=EnvironmentConfig(name="dev", model="test-model"), approval_resume_turns=approvals)


async def _block(orch, record):
    issue = IssueConfig.model_validate(record.model_dump())
    await orch._request_issue_transition(issue=issue, target_status=CardStatus.BLOCKED,
        reason="dependency_blocked", metadata={"run_id": "run-phase", "blocked_by": ["external"]})
    scheduler_run = scheduler_run_id_for_transition(session_id="run-phase", issue_id=issue.id,
        current_status=CardStatus.READY, target_status=CardStatus.BLOCKED, reason="dependency_blocked",
        metadata={"run_id": "run-phase", "blocked_by": ["external"], "wait_reason": "dependency"})
    await _assert_scheduler_truth(orch=orch, run_id=scheduler_run, expected_issue_id=issue.id,
        expected_result="blocked", expected_run_state=RunState.FAILED_TERMINAL)


async def _wait_for_entry(task, entered):
    waiter = asyncio.create_task(entered.wait())
    try:
        done, _ = await asyncio.wait((task, waiter), timeout=10, return_when=asyncio.FIRST_COMPLETED)
        if task in done:
            await task
            raise AssertionError("epic execution finished before its held phase")
        if waiter not in done:
            raise TimeoutError("epic execution remained pending without reaching its held phase")
        await waiter
    finally:
        if not waiter.done():
            waiter.cancel()
        await asyncio.gather(waiter, return_exceptions=True)


async def _settle(task, release):
    release.set()
    if not task.done():
        task.cancel()
    await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_public_epic_retains_selected_loop_node_and_reads_current_inputs(tmp_path, monkeypatch):
    orch, _, epic, team = await _inputs(tmp_path, [])
    entered, release = asyncio.Event(), asyncio.Event()
    load = orchestrator_ops.load_user_settings_async
    selected = orch.loop_policy_node
    observed = []

    async def held_settings():
        value = await load()
        entered.set()
        await release.wait()
        return value

    def record_limit(inputs):
        observed.append(inputs)
        return DefaultOrchestrationLoopPolicyNode.concurrency_limit(selected, inputs)

    def reject_late_selection(_inputs):
        raise AssertionError("loop node was rebound after the settings await")

    monkeypatch.setattr(orchestrator_ops, "load_user_settings_async", held_settings)
    monkeypatch.setattr(selected, "concurrency_limit", record_limit)
    task = asyncio.create_task(_execute(orch, epic, team, {}))
    try:
        await _wait_for_entry(task, entered)
        current = LoopPolicyInputs(concurrency=2, max_iterations=1)
        orch.loop_inputs = current
        orch.loop_policy_node = SimpleNamespace(concurrency_limit=reject_late_selection)
        release.set()
        assert await asyncio.wait_for(task, 10) is None
        assert observed == [current] and observed[0] is current
    finally:
        await _settle(task, release)


@pytest.mark.asyncio
async def test_public_epic_selects_current_effects_after_real_dispatch_read(tmp_path, monkeypatch):
    orch, original_cards, epic, team = await _inputs(tmp_path, ["A"])
    replacement_cards = AsyncCardRepository(tmp_path / "replacement.sqlite3")
    await replacement_cards.save((await original_cards.get_by_id("A")).model_dump())
    entered, release = asyncio.Event(), asyncio.Event()
    read = orchestrator_ops.read_card_dispatch_snapshot
    observed = []
    scheduler, planner = TeamReplanScheduler(), DefaultPlannerNode()

    async def held_read(**fields):
        snapshot = await read(**fields)
        assert fields["cards"] is original_cards
        entered.set()
        await release.wait()
        return snapshot

    async def replan(*args, **kwargs):
        observed.append("replan")
        return await scheduler.maybe_schedule(*args, **kwargs)

    def plan(inputs):
        observed.append("plan")
        return planner.plan(inputs)

    async def turn(issue, *_args, **_kwargs):
        observed.append("turn")
        await _block(orch, issue)

    monkeypatch.setattr(orchestrator_ops, "read_card_dispatch_snapshot", held_read)
    task = asyncio.create_task(_execute(orch, epic, team, {}))
    try:
        await _wait_for_entry(task, entered)
        orch.async_cards = replacement_cards
        orch.team_replan = SimpleNamespace(maybe_schedule=replan)
        orch.planner_node = SimpleNamespace(plan=plan)
        monkeypatch.setattr(orch, "_execute_issue_turn", turn)
        release.set()
        assert await asyncio.wait_for(task, 10) is None
        assert observed == ["replan", "plan", "turn"]
        assert (await original_cards.get_by_id("A")).status == CardStatus.READY
        assert (await replacement_cards.get_by_id("A")).status == CardStatus.BLOCKED
    finally:
        await _settle(task, release)


@pytest.mark.asyncio
async def test_public_epic_selects_turn_and_consumes_approval_only_after_semaphore(tmp_path, monkeypatch):
    orch, cards, epic, team = await _inputs(tmp_path, ["A", "B"])
    entered, release = asyncio.Event(), asyncio.Event()
    approvals = {"A": 7, "B": 9}
    original_values = dict(approvals)
    observed = []

    async def first(issue, *_args, approval_turn_index, **_kwargs):
        observed.append(("first", issue.id, approval_turn_index))
        await _block(orch, issue)
        entered.set()
        await release.wait()

    async def second(issue, *_args, approval_turn_index, **_kwargs):
        observed.append(("second", issue.id, approval_turn_index))
        await _block(orch, issue)

    monkeypatch.setattr(orch, "_execute_issue_turn", first)
    task = asyncio.create_task(_execute(orch, epic, team, approvals))
    try:
        await _wait_for_entry(task, entered)
        first_id = observed[0][1]
        remaining = next(card_id for card_id in original_values if card_id != first_id)
        assert observed == [("first", first_id, original_values[first_id])]
        assert approvals == {remaining: original_values[remaining]}
        assert (await cards.get_by_id(first_id)).status == CardStatus.BLOCKED
        assert (await cards.get_by_id(remaining)).status == CardStatus.READY
        approvals[remaining] = 11
        monkeypatch.setattr(orch, "_execute_issue_turn", second)
        release.set()
        assert await asyncio.wait_for(task, 10) is None
        assert observed[-1] == ("second", remaining, 11) and len(observed) == 2
        assert approvals == {}
        assert (await cards.get_by_id(remaining)).status == CardStatus.BLOCKED
    finally:
        await _settle(task, release)
