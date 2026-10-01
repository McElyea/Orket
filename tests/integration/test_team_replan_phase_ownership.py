"""Layer: integration. Real card/publication effects with controlled scheduler barriers; no provider."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.application.services.orchestrator_issue_control_plane_support import child_workload_run_id_for_issue_creation
from orket.core.contracts.logging_inputs import LoggingInputs
from orket.exceptions import ExecutionFailed
from orket.logging import bind_logging, log_event, prepare_logging
from orket.schema import CardStatus, IssueConfig, SeatConfig, TeamConfig
from tests.integration.test_orchestrator_scheduler_control_plane import _assert_scheduler_truth, _build_orchestrator

pytestmark = pytest.mark.integration


async def _schedule(orch, backlog, run_id, team):
    return await orch.team_replan.maybe_schedule(backlog, run_id, 'build-1', team, request_transition=lambda **fields: orch._request_issue_transition(**fields), cards=lambda: orch.async_cards, select_team=lambda current_epic, current_team: orch._resolve_small_project_team_policy(current_epic, current_team), child_publication=lambda: getattr(orch, 'scheduler_control_plane', None), emit=lambda event, fields: log_event(event, fields, orch.workspace))


async def _inputs(tmp_path):
    cards = AsyncCardRepository(tmp_path / "cards.sqlite3")
    trigger = IssueConfig(id="REQ-1", summary="Requirements changed", seat="requirements_analyst",
        status=CardStatus.READY, build_id="build-1", session_id="run-phase", params={"replan_requested": True})
    await cards.save(trigger.model_dump())
    orch = _build_orchestrator(tmp_path, cards)
    team = TeamConfig(name="core", seats={"coder": SeatConfig(name="Coder", roles=["coder"])})
    return orch, cards, trigger, team


def _child_run(issue_id, run_id="run-phase", count=1):
    return child_workload_run_id_for_issue_creation(session_id=run_id, child_issue_id=issue_id,
        relationship_class="team_replan", metadata={"active_build": "build-1", "seat_name": "coder",
            "trigger_issue_ids": ["REQ-1"], "replan_count": count})


@pytest.mark.asyncio
async def test_replan_observes_replaced_effect_owners_after_child_save(tmp_path, monkeypatch):
    with bind_logging(await prepare_logging(LoggingInputs(tmp_path))):
        from orket.core.domain import RunState

        orch, cards, trigger, team = await _inputs(tmp_path)
        replacement_root = tmp_path / "replacement"
        await asyncio.to_thread(replacement_root.mkdir)
        replacement_cards = AsyncCardRepository(replacement_root / "cards.sqlite3")
        await replacement_cards.save(trigger.model_dump())
        replacement = _build_orchestrator(replacement_root, replacement_cards)
        entered, release = asyncio.Event(), asyncio.Event()
        save = cards.save

        async def held_save(payload):
            await save(payload)
            if payload["id"].startswith("REPLAN-"):
                entered.set()
                await release.wait()

        monkeypatch.setattr(cards, "save", held_save)
        task = asyncio.create_task(_schedule(orch, [trigger], "run-phase", team))
        try:
            await asyncio.wait_for(entered.wait(), 5)
            assert (await cards.get_by_id("REPLAN-RUN-PH-1")).status == CardStatus.READY
            orch.async_cards = replacement_cards
            orch.scheduler_control_plane = replacement.scheduler_control_plane
            orch.workspace = replacement_root
            release.set()
            assert await asyncio.wait_for(task, 10) is True
            assert (await cards.get_by_id("REQ-1")).params["replan_requested"] is True
            assert (await replacement_cards.get_by_id("REQ-1")).params["replan_requested"] is False
            assert await replacement_cards.get_by_id("REPLAN-RUN-PH-1") is None
            assert await orch.control_plane_execution_repository.get_run_record(run_id=_child_run("REPLAN-RUN-PH-1")) is None
            await _assert_scheduler_truth(orch=replacement, run_id=_child_run("REPLAN-RUN-PH-1"),
                expected_issue_id="REPLAN-RUN-PH-1", expected_result="success", expected_run_state=RunState.COMPLETED)
        finally:
            release.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_replan_cancellation_retains_persisted_child_and_consumed_count(tmp_path, monkeypatch):
    with bind_logging(await prepare_logging(LoggingInputs(tmp_path))):
        orch, cards, trigger, team = await _inputs(tmp_path)
        entered, release = asyncio.Event(), asyncio.Event()
        save = cards.save

        async def held_save(payload):
            await save(payload)
            if payload["id"].startswith("REPLAN-"):
                entered.set()
                await release.wait()

        monkeypatch.setattr(cards, "save", held_save)
        task = asyncio.create_task(_schedule(orch, [trigger], "run-phase", team))
        try:
            await asyncio.wait_for(entered.wait(), 5)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 5)
            assert trigger.params["replan_requested"] is True
            assert (await cards.get_by_id("REQ-1")).params["replan_requested"] is True
            assert (await cards.get_by_id("REPLAN-RUN-PH-1")).status == CardStatus.READY
            assert await orch.control_plane_execution_repository.get_run_record(run_id=_child_run("REPLAN-RUN-PH-1")) is None
            monkeypatch.setattr(cards, "save", save)
            assert await _schedule(orch, [trigger], "run-phase", team) is True
            assert (await cards.get_by_id("REPLAN-RUN-PH-2")).params["replan_count"] == 2
            assert (await cards.get_by_id("REQ-1")).params["replan_requested"] is False
        finally:
            release.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_replan_publication_failure_propagates_original_error_after_child_save(tmp_path, monkeypatch):
    with bind_logging(await prepare_logging(LoggingInputs(tmp_path))):
        orch, cards, trigger, team = await _inputs(tmp_path)
        sentinel = RuntimeError("publication sentinel")
        publication = orch.scheduler_control_plane.publish_child_issue_creation
        observed = []

        async def fail_publication(**payload):
            observed.append(payload)
            assert (await cards.get_by_id(payload["issue_id"])).status == CardStatus.READY
            raise sentinel

        monkeypatch.setattr(orch.scheduler_control_plane, "publish_child_issue_creation", fail_publication)
        with pytest.raises(RuntimeError) as error:
            await _schedule(orch, [trigger], "run-phase", team)
        assert error.value is sentinel
        assert len(observed) == 1 and observed[0]["issue_id"] == "REPLAN-RUN-PH-1"
        assert trigger.params["replan_requested"] is True
        assert (await cards.get_by_id("REQ-1")).params["replan_requested"] is True
        assert await orch.control_plane_execution_repository.get_run_record(run_id=_child_run("REPLAN-RUN-PH-1")) is None
        monkeypatch.setattr(orch.scheduler_control_plane, "publish_child_issue_creation", publication)
        assert await _schedule(orch, [trigger], "run-phase", team) is True
        assert (await cards.get_by_id("REPLAN-RUN-PH-2")).params["replan_count"] == 2


@pytest.mark.asyncio
async def test_replan_limit_is_persistent_per_run_and_blocks_real_card(tmp_path):
    with bind_logging(await prepare_logging(LoggingInputs(tmp_path))):
        orch, cards, trigger, team = await _inputs(tmp_path)
        for count in (1, 2, 3):
            trigger.params["replan_requested"] = True
            assert await _schedule(orch, [trigger], "run-phase", team) is True
            assert (await cards.get_by_id(f"REPLAN-RUN-PH-{count}")).params["replan_count"] == count
        trigger.params["replan_requested"] = True
        with pytest.raises(ExecutionFailed, match="TEAM_REPLAN_LIMIT_EXCEEDED"):
            await _schedule(orch, [trigger], "run-phase", team)
        assert (await cards.get_by_id("REQ-1")).status == CardStatus.BLOCKED
        assert await cards.get_by_id("REPLAN-RUN-PH-4") is None
        assert await _schedule(orch, [trigger], "fresh-run", team) is True
        assert (await cards.get_by_id("REPLAN-FRESH--1")).params["replan_count"] == 1


@pytest.mark.asyncio
async def test_team_policy_observes_settings_before_current_organization(tmp_path, monkeypatch):
    with bind_logging(await prepare_logging(LoggingInputs(tmp_path))):
        monkeypatch.delenv("ORKET_SMALL_PROJECT_BUILDER_VARIANT", raising=False)
        orch, _cards, trigger, team = await _inputs(tmp_path)
        orch.org = SimpleNamespace(process_rules={"small_project_issue_threshold": 2})
        seen = []

        def load_settings():
            seen.append(orch.org.process_rules["small_project_issue_threshold"])
            orch.org = SimpleNamespace(process_rules={"small_project_issue_threshold": 9,
                "small_project_builder_variant": "architect"})
            return {"small_project_builder_variant": "coder"}

        monkeypatch.setattr(orch.support_services, "load_user_settings", load_settings)
        policy = orch._resolve_small_project_team_policy(SimpleNamespace(issues=[trigger]), team)
        assert seen == [2]
        assert policy["threshold"] == 2 and policy["variant"] == "architect"
        assert policy["active"] is True and policy["builder_role"] == "architect"
