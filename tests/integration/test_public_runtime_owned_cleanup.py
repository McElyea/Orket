"""Public orchestration retains actual publication and SQLite cleanup through interruption."""
from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import aiosqlite
import pytest

import orket.runtime.execution.execution_pipeline as pipeline_module
from tests.application.test_execution_pipeline_cards_epic_control_plane import _write_epic_assets
from tests.integration.test_epic_completion_publication import accept_publication_card

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def cleanup_factory(test_root, db_path, fail):
    state = SimpleNamespace(entered=asyncio.Event(), release=asyncio.Event(), closed=False, owner=None, result=None)
    original = pipeline_module.ExecutionPipeline

    def construct(*args, **kwargs):
        kwargs.update(config_root=test_root, db_path=db_path)
        owner = original(*args, **kwargs)
        state.owner = owner
        original_close, original_run = owner.close, owner.run_card

        async def workload(**_kwargs):
            await accept_publication_card(owner, owner.workspace)

        async def run_card(*args, **kwargs):
            state.result = await original_run(*args, **kwargs)
            return state.result

        async def close():
            await original_close()
            try:
                async with aiosqlite.connect(db_path) as connection:
                    await connection.execute('BEGIN')
                    assert await (await connection.execute('SELECT 42')).fetchone() == (42,)
                    state.entered.set()
                    await state.release.wait()
                    if fail:
                        await connection.execute('SELECT * FROM absent_cleanup_probe_table')
            finally:
                state.closed = True

        owner.orchestrator.execute_epic, owner.run_card, owner.close = workload, run_card, close
        return owner

    return state, construct


@pytest.mark.parametrize('fail', [False, True])
async def test_public_runtime_joins_cleanup_before_reporting_interruption(
    test_root, workspace, db_path, monkeypatch, record_property, fail,
):
    await asyncio.to_thread(_write_epic_assets, test_root, 'publication_epic')
    state, construct = cleanup_factory(test_root, db_path, fail)
    monkeypatch.setattr(pipeline_module, 'ExecutionPipeline', construct)
    task = asyncio.create_task(pipeline_module.orchestrate_card('publication_epic', workspace,
        session_id='owned-close', build_id='owned-build'))
    try:
        await asyncio.wait_for(state.entered.wait(), 15)
        assert state.result.succeeded and state.result.observation == 'published'
        started = time.perf_counter()
        async with aiosqlite.connect(db_path) as connection:
            assert await (await connection.execute('SELECT COUNT(*) FROM success_ledger')).fetchone() == (1,)
        elapsed = time.perf_counter() - started
        record_property('responsive_sqlite_seconds', elapsed)
        assert elapsed < .5
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(.02)
        assert not task.done() and not state.closed
        state.release.set()
        expected = aiosqlite.OperationalError if fail else asyncio.CancelledError
        with pytest.raises(expected):
            await asyncio.wait_for(task, 5)
        assert state.owner._closed and state.closed
    finally:
        state.release.set()
        await asyncio.gather(task, return_exceptions=True)
        if state.owner is not None and not state.owner._closed:
            await state.owner.close()
