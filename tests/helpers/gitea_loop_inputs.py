"""Controlled ready queue with actual Gitea HTTP clients and independent SQLite probes."""
import asyncio
import json
import time
from functools import partial

import aiosqlite

import orket.runtime.execution.gitea_state_loop as loop_module
from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.runtime.execution.execution_pipeline import ExecutionPipeline
from tests.application.test_execution_pipeline_cards_epic_control_plane import _write_epic_assets


def construction_inputs(root, *, environment=None, settings=None):
    selected = {
        'ORKET_STATE_BACKEND_MODE': 'gitea', 'ORKET_ENABLE_GITEA_STATE_PILOT': '1',
        'ORKET_GITEA_URL': 'http://127.0.0.1:1', 'ORKET_GITEA_TOKEN': 'unused-controlled-token',
        'ORKET_GITEA_OWNER': 'fixture-owner', 'ORKET_GITEA_REPO': 'fixture-repo',
    } if environment is None else environment
    return RuntimeConstructionInputs(root, selected, json.dumps({} if settings is None else settings), '{}')


def local_runner(root, monkeypatch, *, fetch_failure=False, runtime_inputs=None):
    created = []
    adapter_type = loop_module.GiteaStateAdapter
    adapter_factory = loop_module.create_gitea_state_adapter

    def capture_adapter(**values):
        adapter = adapter_factory(**values)
        created.append(adapter)
        return adapter

    async def empty_queue(_adapter, *, limit):
        assert limit == 5
        if fetch_failure:
            raise RuntimeError('controlled-fetch-failure')
        return []

    async def forbidden_work(_card):
        raise AssertionError('An empty ready queue must not execute a workload')

    monkeypatch.setattr(loop_module, 'create_gitea_state_adapter', capture_adapter)
    monkeypatch.setattr(adapter_type, 'fetch_ready_cards', empty_queue)
    runner = loop_module.GiteaStateLoopRunner(state_backend_mode='gitea', organization=None, run_card=forbidden_work,
        construction_inputs=construction_inputs(root),
        runtime_inputs=RuntimeInputService() if runtime_inputs is None else runtime_inputs)
    return runner, created, adapter_type


async def probe_database(root):
    database = root / 'response.sqlite3'
    async with aiosqlite.connect(database) as connection:
        await connection.execute('CREATE TABLE response_probe (value INTEGER)')
        await connection.commit()
    return database


async def assert_sqlite_response(database, record_property):
    async def read():
        async with aiosqlite.connect(database.as_uri() + '?mode=ro', uri=True) as connection:
            cursor = await connection.execute('SELECT COUNT(*) FROM response_probe')
            assert await cursor.fetchone() == (0,)

    started = time.perf_counter()
    await asyncio.wait_for(read(), 0.5)
    elapsed = time.perf_counter() - started
    record_property('responsive_sqlite_seconds', elapsed)
    assert elapsed < 0.5  # Existing D1 bound, declared before this campaign.


async def gitea_pipeline(root, *, inputs, clock):
    await run_owned_thread(partial(_write_epic_assets, root, 'gitea_epic'), label='gitea-fixture-assets')
    await AsyncFileTools(root).write_file('config/organization.json',
        json.dumps({'name': 'Gitea fixture', 'vision': 'Observe owned work', 'ethos': 'Retain truth'}))
    await AsyncFileTools(root).write_file('model/core/environments/standard.json',
        json.dumps({'name': 'standard', 'model': 'dummy-model'}))
    return await run_owned_thread(partial(ExecutionPipeline, workspace=root / 'workspace', config_root=root,
        construction_inputs=inputs, runtime_inputs=clock), label='gitea-fixture-pipeline')


class RecordingClock(RuntimeInputService):
    def __init__(self):
        self.utc_observations = []
        self.monotonic_observations = []

    def utc_now(self):
        observed = super().utc_now()
        self.utc_observations.append(observed.isoformat())
        return observed

    def monotonic_seconds(self):
        observed = super().monotonic_seconds()
        self.monotonic_observations.append(observed)
        return observed
