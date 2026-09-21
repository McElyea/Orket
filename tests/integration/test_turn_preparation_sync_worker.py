"""A synchronous asset adapter must run in an owned worker during real card dispatch."""
import asyncio
import threading
from time import perf_counter
from types import SimpleNamespace

import aiosqlite
import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.decision_nodes.builtins import DefaultRouterNode
from orket.schema import CardStatus, EnvironmentConfig
from tests.integration.test_dispatch_input_admission import _dispatch_context

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_sync_asset_adapter_keeps_event_loop_responsive_and_owns_failure(tmp_path, record_property):
    await AsyncFileTools(tmp_path).write_file('role.json', '{"name":"coder"}')
    repo, issue, team, orchestrator = await _dispatch_context(tmp_path, DefaultRouterNode())
    loop = asyncio.get_running_loop()
    entered, release, finished = asyncio.Event(), threading.Event(), threading.Event()
    handles = []
    # A bounded native release prevents a broken on-loop implementation from hanging the probe.
    timer = threading.Timer(0.8, release.set)

    class SyncLoader:
        def load_asset(self, category, name, model_type):
            try:
                with (tmp_path / 'role.json').open('rb') as stream:
                    handles.append(stream)
                    assert stream.read() == b'{"name":"coder"}'
                    timer.start()
                    loop.call_soon_threadsafe(entered.set)
                    assert release.wait(5), 'sync asset worker was not released'
                    raise ValueError('sync asset worker failure')
            finally:
                finished.set()

    orchestrator.loader = SyncLoader()
    started = perf_counter()
    operation = asyncio.create_task(orchestrator._execute_issue_turn(issue, SimpleNamespace(params={}), team,
        EnvironmentConfig(name='test', model='fixture'), 'run', 'build', None, None, None))
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        async with aiosqlite.connect(tmp_path / 'responsive.sqlite3') as connection:
            assert (await (await connection.execute('SELECT 42')).fetchone())[0] == 42
        elapsed = perf_counter() - started
        record_property('responsive_sqlite_seconds', elapsed)
        assert elapsed < 0.5
        operation.cancel()
        await asyncio.sleep(0)
        operation.cancel()
        done, _ = await asyncio.wait({operation}, timeout=0.05)
        assert not done and not handles[0].closed
    finally:
        release.set()
        timer.cancel()
        if timer.ident is not None:
            await asyncio.to_thread(timer.join, 5)
        results = await asyncio.gather(operation, return_exceptions=True)
    assert isinstance(results[0], ValueError) and str(results[0]) == 'sync asset worker failure'
    assert handles[0].closed and finished.is_set() and not timer.is_alive()
    assert (await repo.get_by_id(issue.id)).status == CardStatus.IN_PROGRESS
