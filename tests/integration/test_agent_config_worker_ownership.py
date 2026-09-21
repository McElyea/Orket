"""Public Agent.run retains its actual asset worker through repeated interruption."""
import asyncio
import threading
from time import perf_counter

import aiosqlite
import pytest

from orket.agents.agent import Agent
from tests.integration.test_remaining_runtime_input_capture import write_assets

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class UncalledProvider:
    model = 'probe-model'

    async def complete(self, messages):
        raise AssertionError('Interrupted configuration must not reach the provider')


@pytest.mark.parametrize('interrupt', ['cancel', 'timeout', 'timeout_then_cancel'])
@pytest.mark.parametrize('worker_fails', [False, True])
async def test_agent_waits_for_asset_worker_before_reporting_interruption(
    tmp_path, monkeypatch, record_property, interrupt, worker_fails,
):
    await write_assets(tmp_path)
    agent = Agent('probe', 'observe', {}, UncalledProvider(), config_root=tmp_path, environment={})
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    handles = []
    original = agent._ensure_configs_loaded

    def held():
        try:
            original()
            with (tmp_path / 'model/core/roles/probe.json').open('rb') as stream:
                handles.append(stream)
                assert stream.read(1) == b'{'
                entered.set()
                assert release.wait(5), 'asset worker was not released'
                if worker_fails:
                    raise ValueError('asset worker failure')
        finally:
            finished.set()

    async def invoke():
        async with asyncio.timeout(0.05 if interrupt.startswith('timeout') else None):
            return await agent.run({'description': 'original'}, {}, tmp_path)

    monkeypatch.setattr(agent, '_ensure_configs_loaded', held)
    operation = asyncio.create_task(invoke())
    try:
        assert await asyncio.to_thread(entered.wait, 5), 'asset worker did not open its file'
        started = perf_counter()
        async with aiosqlite.connect(tmp_path / 'responsive.sqlite3') as connection:
            assert (await (await connection.execute('SELECT 42')).fetchone())[0] == 42
        elapsed = perf_counter() - started
        record_property('responsive_sqlite_seconds', elapsed)
        assert elapsed < 0.5
        if interrupt == 'cancel':
            operation.cancel()
        done, _ = await asyncio.wait({operation}, timeout=0.1)
        assert not done, 'Caller returned while its admitted asset worker still held a native file'
        if interrupt != 'timeout':
            operation.cancel()
        await asyncio.sleep(0)
        assert not operation.done() and not handles[0].closed
    finally:
        release.set()
        assert await asyncio.to_thread(finished.wait, 5), 'asset worker did not finish'
        results = await asyncio.gather(operation, return_exceptions=True)
    expected = ValueError if worker_fails else TimeoutError if interrupt == 'timeout' else asyncio.CancelledError
    assert isinstance(results[0], expected), results
    assert handles[0].closed and finished.is_set()
