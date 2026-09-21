"""Actual organization discovery, card acceptance, publication and required cleanup."""
import asyncio
import time

import aiosqlite
import pytest

import orket.organization_loop as loop_module
from orket.application.services.runtime_result_projection import RuntimeOutcomeError
from orket.settings import set_runtime_settings_context
from tests.integration.test_epic_completion_publication import accept_publication_card
from tests.integration.test_organization_loop_ownership import seed_organization
from tests.integration.test_public_runtime_owned_cleanup import cleanup_factory

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('legacy', [False, True])
async def test_organization_create_retains_inputs_before_worker(test_root, monkeypatch, legacy):
    await asyncio.to_thread(seed_organization, test_root)
    if legacy:
        await asyncio.to_thread((test_root / 'config/organization.json').rename, test_root / 'model/organization.json')
    rotated = test_root / 'rotated'
    await asyncio.to_thread(rotated.mkdir)
    monkeypatch.chdir(test_root)
    monkeypatch.setenv('ORKET_DURABLE_ROOT', 'selected-state')
    set_runtime_settings_context(user_settings={'selected': 'original'}, user_preferences={})
    entered, release = asyncio.Event(), asyncio.Event()
    worker = loop_module.run_owned_thread

    async def held(operation, *, label):
        entered.set()
        await release.wait()
        return await worker(operation, label=label)

    monkeypatch.setattr(loop_module, 'run_owned_thread', held)
    task = asyncio.create_task(loop_module.OrganizationLoop.create())
    try:
        await asyncio.wait_for(entered.wait(), 5)
        monkeypatch.chdir(rotated)
        monkeypatch.setenv('ORKET_DURABLE_ROOT', 'rotated-state')
        set_runtime_settings_context(user_settings={'selected': 'rotated'}, user_preferences={})
        release.set()
        owner = await asyncio.wait_for(task, 5)
        assert owner.project_root == test_root and owner.workspace == test_root / 'workspace/default'
        assert owner.construction_inputs.environment['ORKET_DURABLE_ROOT'] == 'selected-state'
        assert owner.construction_inputs.user_settings() == {'selected': 'original'}
        assert owner.org_path == test_root / ('model/organization.json' if legacy else 'config/organization.json')
        owner.org.departments.clear()
        assert (await asyncio.to_thread(owner._find_next_critical_card))['id'] == 'ISSUE-1'
        assert await asyncio.to_thread(lambda: list(rotated.iterdir())) == []
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize('accept', [False, True])
async def test_organization_dispatch_keeps_real_terminal_truth(test_root, db_path, monkeypatch, accept):
    await asyncio.to_thread(seed_organization, test_root)
    monkeypatch.chdir(test_root)
    owner = await loop_module.OrganizationLoop.create()
    factory, runtimes, results = loop_module.ExecutionPipeline, [], []

    def construct(*args, **kwargs):
        runtime = factory(*args, **kwargs, db_path=db_path)
        runtimes.append(runtime)
        run_card = runtime.run_card

        async def workload(**_kwargs):
            if accept:
                await accept_publication_card(runtime, runtime.workspace)

        async def observed(*args, **kwargs):
            try:
                result = await run_card(*args, **kwargs)
                results.append(result)
                return result
            finally:
                owner.running = False

        runtime.orchestrator.execute_epic, runtime.run_card = workload, observed
        return runtime

    monkeypatch.setattr(loop_module, 'ExecutionPipeline', construct)
    try:
        if accept:
            await asyncio.wait_for(owner.run_forever(), 15)
        else:
            with pytest.raises(RuntimeOutcomeError) as failed:
                await asyncio.wait_for(owner.run_forever(), 15)
            assert failed.value.result is results[0]
        assert len(runtimes) == len(results) == 1 and results[0].succeeded is accept
        assert runtimes[0]._closed and not owner.running
        async with aiosqlite.connect(db_path) as connection:
            ledger, = await (await connection.execute('SELECT status FROM run_ledger')).fetchall()
            assert (ledger[0] == 'done') is accept
            exists = await (await connection.execute("SELECT name FROM sqlite_master WHERE name='success_ledger'")).fetchone()
            count = (await (await connection.execute('SELECT COUNT(*) FROM success_ledger')).fetchone())[0] if exists else 0
            assert count == int(accept)
    finally:
        for runtime in runtimes:
            await runtime.close()


@pytest.mark.parametrize('fail', [False, True])
async def test_organization_joins_required_cleanup(test_root, db_path, monkeypatch, record_property, fail):
    await asyncio.to_thread(seed_organization, test_root)
    monkeypatch.chdir(test_root)
    owner = await loop_module.OrganizationLoop.create()
    state, construct = cleanup_factory(test_root, db_path, fail)
    monkeypatch.setattr(loop_module, 'ExecutionPipeline', construct)
    task = asyncio.create_task(owner.run_forever())
    try:
        await asyncio.wait_for(state.entered.wait(), 15)
        assert state.result.succeeded
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
        with pytest.raises(aiosqlite.OperationalError if fail else asyncio.CancelledError):
            await asyncio.wait_for(task, 5)
        assert state.owner._closed and state.closed and not owner.running
    finally:
        state.release.set()
        await asyncio.gather(task, return_exceptions=True)
        if state.owner is not None and not state.owner._closed:
            await state.owner.close()
