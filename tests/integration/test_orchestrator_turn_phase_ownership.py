"""Integration: real cards/checkpoints with controlled preparation and dispatch barriers.

The outcome control supplies a provider and executor; it makes no inference or
whole TurnExecutor claim. Existing provider/turn integration guards remain required.
"""
from __future__ import annotations

import asyncio
import json
import threading

import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.adapters.storage.async_repositories import AsyncSnapshotRepository
from orket.application.services.orchestrator_issue_control_plane_support import run_id_for_dispatch
from orket.application.services.orchestrator_review_preflight_service import OrchestratorReviewPreflightService
from orket.application.workflows import orchestrator_ops
from orket.application.workflows.turn_executor import TurnResult
from orket.core.contracts.logging_inputs import LoggingInputs
from orket.core.domain import RunState
from orket.core.domain.execution import ExecutionTurn
from orket.decision_nodes.builtins import DefaultEvaluatorNode, DefaultRouterNode
from orket.logging import bind_logging, prepare_logging
from orket.schema import CardStatus, EnvironmentConfig, EpicConfig
from tests.helpers.model_selection import prepared_model_selection
from tests.integration.test_dispatch_input_admission import _dispatch_context
from tests.integration.test_epic_execution_phase_ownership import _settle, _wait_for_entry
from tests.integration.test_orchestrator_issue_control_plane import _Client, _dialect, _Loader, _Provider, _role

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _invoke(orch, issue, team, executor=None):
    with bind_logging(await prepare_logging(LoggingInputs(orch.workspace))):
        return await orch._execute_issue_turn(
            issue_data=issue, epic=EpicConfig(id="EPIC-1", name="Phase", team="test", environment="test"),
            team=team, env=EnvironmentConfig(name="test", model="test-model"), run_id="run", active_build="build",
            model_selection=prepared_model_selection(), executor=executor, toolbox=None, model_override="test-model",
        )


async def test_turn_preparation_selects_current_router_and_loader_after_preflight(tmp_path, monkeypatch):
    repo, issue, team, orch = await _dispatch_context(tmp_path, DefaultRouterNode())
    entered, release = asyncio.Event(), asyncio.Event()
    await AsyncFileTools(orch.workspace).write_file("role-observation.txt", "selected loader")
    run = OrchestratorReviewPreflightService.run
    sentinel = ValueError("selected loader refused after actual read")
    observations = []

    async def held_preflight(owner, **fields):
        result = await run(owner, **fields)
        assert not result.stop_execution
        entered.set()
        await release.wait()
        return result

    class Router(DefaultRouterNode):
        def route(self, inputs):
            observations.append(("route", inputs.issue_id))
            return super().route(inputs)

    class Loader:
        def load_asset(self, category, name, _model):
            with (orch.workspace / "role-observation.txt").open(encoding="utf-8") as stream:
                assert stream.read() == "selected loader"
            observations.append((category, name, threading.get_ident()))
            raise sentinel

    monkeypatch.setattr(OrchestratorReviewPreflightService, "run", held_preflight)
    task = asyncio.create_task(_invoke(orch, issue, team))
    try:
        await _wait_for_entry(task, entered)
        assert (await repo.get_by_id(issue.id)).status == CardStatus.READY
        orch.router_node, orch.loader = Router(), Loader()
        release.set()
        with pytest.raises(ValueError) as failure:
            await asyncio.wait_for(task, 10)
        assert failure.value is sentinel
        assert observations[0] == ("route", issue.id)
        assert observations[1][:2] == ("roles", "coder") and len(observations) == 2
        assert observations[1][2] != threading.get_ident()
        assert (await repo.get_by_id(issue.id)).status == CardStatus.IN_PROGRESS
        run_id = run_id_for_dispatch(session_id="run", issue_id=issue.id, seat_name="developer", turn_index=1)
        assert await orch.control_plane_execution_repository.get_run_record(run_id=run_id) is not None
    finally:
        await _settle(task, release)


class _PhysicalExecutor:
    def __init__(self, files):
        self.files = files

    async def execute_turn(self, issue, _role, _client, _toolbox, context, system_prompt=None):
        assert "Declared card acceptance:" in system_prompt
        await self.files.write_file("turn-effect.txt", "persisted before outcome")
        return TurnResult.succeeded(ExecutionTurn(role=context["role"], issue_id=issue.id,
            content="Controlled turn effect persisted.", timestamp=None))


class _SuppliedModels:
    def __init__(self):
        self.provider, self.client = _Provider(), _Client()

    def create_provider(self, _model, _options):
        return self.provider

    def create_client(self, provider):
        assert provider is self.provider
        return self.client


async def test_turn_outcome_selects_current_owners_and_final_close_after_dispatch(tmp_path, monkeypatch):
    repo, issue, team, orch = await _dispatch_context(tmp_path, DefaultRouterNode())
    files = AsyncFileTools(orch.workspace)
    orch.card_completion = None  # Supported observation-only turn; no accepted completion is requested.
    orch.loader = _Loader([_role(), _dialect()])
    orch.model_clients = models = _SuppliedModels()
    orch.snapshots = original_snapshots = AsyncSnapshotRepository(tmp_path / "old-snapshots.sqlite3")
    replacement_snapshots = AsyncSnapshotRepository(tmp_path / "new-snapshots.sqlite3")
    original_transcript = orch.transcript
    entered, release = asyncio.Event(), asyncio.Event()
    dispatch, close = orch._dispatch_turn, orchestrator_ops._close_provider_transport
    observed = []

    async def held_dispatch(**fields):
        result = await dispatch(**fields)
        entered.set()
        await release.wait()
        return result

    class Evaluator(DefaultEvaluatorNode):
        def evaluate_success(self, inputs):
            observed.append(("evaluate", inputs.turn.issue_id))
            return {}

    async def final_close(provider):
        observed.append(("close", provider))
        await close(provider)

    monkeypatch.setattr(orch, "_dispatch_turn", held_dispatch)
    task = asyncio.create_task(_invoke(orch, issue, team, _PhysicalExecutor(files)))
    try:
        await _wait_for_entry(task, entered)
        assert await files.read_file("turn-effect.txt") == "persisted before outcome"
        assert models.provider.close_calls == models.provider.clear_calls == 0
        orch.transcript = []
        orch.evaluator_node, orch.snapshots = Evaluator(), replacement_snapshots
        monkeypatch.setattr(orchestrator_ops, "_close_provider_transport", final_close)
        release.set()
        assert await asyncio.wait_for(task, 10) is None
        assert observed == [("evaluate", issue.id), ("close", models.provider)]
        assert original_transcript == [] and len(orch.transcript) == 1
        assert await original_snapshots.get("run") is None
        snapshot = await replacement_snapshots.get("run")
        assert json.loads(snapshot["log_history"])[0]["content"] == "Controlled turn effect persisted."
        assert models.provider.clear_calls == models.provider.close_calls == 1 and models.client.calls == 0
        assert (await repo.get_by_id(issue.id)).status == CardStatus.IN_PROGRESS
        run_id = run_id_for_dispatch(session_id="run", issue_id=issue.id, seat_name="developer", turn_index=1)
        record = await orch.control_plane_execution_repository.get_run_record(run_id=run_id)
        assert record.lifecycle_state is RunState.COMPLETED
    finally:
        await _settle(task, release)
