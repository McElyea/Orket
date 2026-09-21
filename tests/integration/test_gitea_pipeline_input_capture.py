"""Actual pipeline/client/files/SQLite with a controlled empty remote ready queue."""
import asyncio
import json
from pathlib import Path

import pytest

import orket.runtime.execution.gitea_state_loop as loop_module
from orket.adapters.storage.async_file_tools import AsyncFileTools
from tests.helpers.gitea_loop_inputs import RecordingClock, construction_inputs, gitea_pipeline, local_runner

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_pipeline_retains_selection_across_initialization(tmp_path, monkeypatch):
    original, rotated = tmp_path / 'original', tmp_path / 'rotated'
    await asyncio.to_thread(original.mkdir)
    await asyncio.to_thread(rotated.mkdir)
    monkeypatch.chdir(original)
    _, clients, _ = local_runner(original, monkeypatch)
    environment = dict(construction_inputs(original).environment, ORKET_DURABLE_ROOT='selected-state',
        ORKET_DISABLE_SANDBOX='1', ORKET_RUN_LEDGER_MODE='sqlite')
    clock = RecordingClock()
    pipeline = await gitea_pipeline(original, inputs=construction_inputs(original, environment=environment), clock=clock)
    pipeline.org.process_rules['gitea_worker_max_iterations'] = 3
    entered, release = asyncio.Event(), asyncio.Event()
    initialize = pipeline.initialize
    workers = []
    worker_type = loop_module.GiteaStateWorker

    def capture_worker(**kwargs):
        worker = worker_type(**kwargs)
        workers.append(worker)
        return worker

    async def held_initialize():
        entered.set()
        await release.wait()
        await initialize()

    monkeypatch.setattr(loop_module, 'GiteaStateWorker', capture_worker)
    monkeypatch.setattr(pipeline, 'initialize', held_initialize)
    operation = asyncio.create_task(pipeline.run_gitea_state_loop(worker_id='capture-worker',
        max_idle_streak=1, summary_out=Path('summary.json')))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        monkeypatch.chdir(rotated)
        monkeypatch.setenv('ORKET_GITEA_WORKER_MAX_ITERATIONS', '99')
        monkeypatch.setenv('ORKET_DURABLE_ROOT', 'rotated-state')
        monkeypatch.setenv('ORKET_ENABLE_GITEA_STATE_PILOT', '0')
        pipeline.org.process_rules['gitea_worker_max_iterations'] = 71
        release.set()
        result = await asyncio.wait_for(operation, 10)
        assert result['max_iterations'] == 3 and result['summary']['iterations'] == 1
        assert json.loads(await AsyncFileTools(original).read_file('summary.json')) == result['summary']
        assert len(workers) == len(clients) == 1 and clients[0].http._client.is_closed
        repository = workers[0].control_plane_execution_service.execution_repository
        assert Path(repository.db_path) == Path(pipeline.orchestrator.control_plane_execution_repository.db_path)
        assert Path(repository.db_path).is_relative_to(original / 'selected-state')
        assert len(clock.monotonic_observations) == 3
        assert await pipeline.async_cards.get_by_id('ISSUE-1') is None
        assert await asyncio.to_thread(lambda: list(rotated.iterdir())) == []
    finally:
        release.set()
        await asyncio.gather(operation, return_exceptions=True)
        await pipeline.close()


async def test_coordinator_uses_selected_monotonic_deadline(tmp_path, monkeypatch):
    clock = RecordingClock()
    observations = iter([100.0, 100.0, 101.0, 101.25])
    monkeypatch.setattr(clock, 'monotonic_seconds', lambda: next(observations))
    runner, clients, _ = local_runner(tmp_path, monkeypatch, runtime_inputs=clock)
    result = await runner.run(worker_id='selected-deadline', max_idle_streak=10, max_duration_seconds=0.5)
    assert result['summary'] == {'iterations': 1, 'consumed_count': 0, 'idle_count': 1,
        'stop_reason': 'max_duration_seconds', 'elapsed_ms': 1250}
    assert len(clients) == 1 and clients[0].http._client.is_closed
