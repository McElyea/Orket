"""Prepared runtime constructors retain selected paths, settings and parent ports."""
from __future__ import annotations

import asyncio
from pathlib import Path

import aiosqlite
import pytest

import orket.application.services.runtime_result_lifetime as lifetime_module
import orket.runtime.execution.execution_pipeline as pipeline_module
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.settings import set_runtime_settings_context
from tests.application.test_execution_pipeline_cards_epic_control_plane import _write_epic_assets
from tests.integration.test_epic_completion_publication import accept_publication_card

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_public_runtime_keeps_inputs_across_worker_admission(test_root, monkeypatch):
    original, rotated = test_root, test_root / 'rotated'
    await asyncio.to_thread(rotated.mkdir)
    await asyncio.to_thread(_write_epic_assets, original, 'publication_epic')
    monkeypatch.chdir(original)
    monkeypatch.setenv('ORKET_DURABLE_ROOT', 'selected-state')
    monkeypatch.setenv('ORKET_RUN_LEDGER_MODE', 'sqlite')
    set_runtime_settings_context(user_settings={'selected': {'value': 'original'}}, user_preferences={'theme': 'original'})
    entered, release, owners = asyncio.Event(), asyncio.Event(), []
    worker, factory = lifetime_module.run_owned_thread, pipeline_module.ExecutionPipeline

    async def held_worker(operation, *, label):
        entered.set()
        await release.wait()
        return await worker(operation, label=label)

    def construct(*args, **kwargs):
        owner = factory(*args, **kwargs)
        owners.append(owner)

        async def workload(**_kwargs):
            await accept_publication_card(owner, owner.workspace)

        owner.orchestrator.execute_epic = workload
        return owner

    monkeypatch.setattr(lifetime_module, 'run_owned_thread', held_worker)
    monkeypatch.setattr(pipeline_module, 'ExecutionPipeline', construct)
    task = asyncio.create_task(pipeline_module.orchestrate_card('publication_epic', Path('workspace'),
        session_id='captured-factory', build_id='captured-build'))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        monkeypatch.chdir(rotated)
        monkeypatch.setenv('ORKET_DURABLE_ROOT', 'rotated-state')
        monkeypatch.setenv('ORKET_RUN_LEDGER_MODE', 'protocol')
        set_runtime_settings_context(user_settings={'selected': {'value': 'rotated'}}, user_preferences={})
        release.set()
        result = await asyncio.wait_for(task, 15)
        assert result.succeeded and len(owners) == 1 and owners[0]._closed
        owner = owners[0]
        assert owner.workspace == original / 'workspace' and owner.config_root == original
        assert Path(owner.db_path) == original / 'selected-state/db/orket_persistence.db'
        assert owner.run_ledger_mode == 'sqlite' and owner.user_settings == {'selected': {'value': 'original'}}
        assert owner.runtime_context.construction_inputs.user_preferences() == {'theme': 'original'}
        async with aiosqlite.connect(Path(owner.db_path).as_uri() + '?mode=ro', uri=True) as connection:
            assert await (await connection.execute('SELECT COUNT(*) FROM success_ledger')).fetchone() == (1,)
        assert await asyncio.to_thread(lambda: list(rotated.iterdir())) == []
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        for owner in owners:
            await owner.close()


@pytest.mark.parametrize('explicit', [False, True])
async def test_prepared_collection_factory_detaches_parent_fields(test_root, workspace, db_path, monkeypatch, explicit):
    await asyncio.to_thread(_write_epic_assets, test_root, 'publication_epic')
    rotated = test_root / 'rotated'
    await asyncio.to_thread(rotated.mkdir)
    monkeypatch.chdir(test_root)
    monkeypatch.setenv('ORKET_DURABLE_ROOT', 'selected-state')
    inputs = RuntimeConstructionInputs.capture()
    parent = await asyncio.to_thread(pipeline_module.ExecutionPipeline, workspace,
        config_root=test_root, db_path=db_path, construction_inputs=inputs if explicit else None)
    child = None
    selected_clock, selected_nodes = parent.runtime_inputs, parent.decision_nodes
    selected_inputs = parent.runtime_context.construction_inputs
    try:
        construct = await parent.pipeline_wiring_service.prepare_sub_pipeline(
            parent_pipeline=parent, epic_workspace=workspace / 'member', department='core')
        parent.db_path, parent.config_root = str(workspace / 'wrong.sqlite3'), workspace / 'wrong'
        parent.runtime_inputs, parent.decision_nodes = RuntimeInputService(), None
        parent.runtime_context.construction_inputs = None
        monkeypatch.chdir(rotated)
        monkeypatch.setenv('ORKET_DURABLE_ROOT', 'rotated-state')
        monkeypatch.setenv('ORKET_RUN_LEDGER_MODE', 'protocol')
        child = await lifetime_module.create_runtime_owner(construct, label='prepared-collection-probe')
        await child.initialize()
        assert child.db_path == db_path and child.config_root == test_root
        assert child.runtime_inputs is selected_clock and child.decision_nodes is selected_nodes
        assert child.runtime_context.construction_inputs is not None and child.run_ledger_mode == 'sqlite'
        assert child.runtime_context.construction_inputs is selected_inputs
        assert child.orchestrator.decision_environment['ORKET_DURABLE_ROOT'] == 'selected-state'
        assert child.webhook_db.db_path.is_relative_to(test_root / 'selected-state')
        assert Path(child.sandbox_orchestrator.lifecycle_repository.db_path).is_relative_to(test_root / 'selected-state')
        assert await child.async_cards.get_by_id('not-admitted') is None
        assert await asyncio.to_thread(Path(db_path).is_file)
        assert await asyncio.to_thread(lambda: list(rotated.iterdir())) == []
    finally:
        if child is not None:
            await child.close()
        await parent.close()
    assert parent._closed and child._closed
