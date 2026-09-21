"""Real cards and trusted extension publication with explicitly selected UTC inputs."""
import asyncio
from functools import partial
from pathlib import Path

import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.services.cards_epic_control_plane_service import CardsEpicControlPlaneService
from orket.application.services.extension_catalog_commands import prepare_extension_manager
from orket.application.services.review_run_control_plane_service import build_review_run_control_plane_service
from orket.extensions.manager import ExtensionManager
from orket.runtime.execution.execution_pipeline import ExecutionPipeline
from tests.application.test_execution_pipeline_cards_epic_control_plane import _write_epic_assets
from tests.helpers.protocol_ledger_clock import ProtocolLedgerClock
from tests.helpers.remaining_family_authority import (
    database_for,
    records,
    repeat_closeout,
    retained_request,
    review_flow,
)
from tests.integration.test_epic_completion_publication import accept_publication_card
from tests.runtime.test_extension_manager import _init_sdk_extension_repo, _init_test_extension_repo

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class RecordingInputs(ProtocolLedgerClock):
    def __init__(self):
        super().__init__()
        self.observations = []
        self.unavailable = False

    def utc_now(self):
        if self.unavailable:
            raise ValueError('selected-clock-unavailable')
        observed = super().utc_now()
        self.observations.append(observed.isoformat())
        return observed


def assert_selected_clock(rows, clock):
    assert len(rows['control_plane_runs']) == len(rows['control_plane_attempts']) == 1
    assert len(rows['effect_journal_entries']) >= 2 and len(rows['final_truth_records']) == 1
    observed = [rows['control_plane_runs'][0]['creation_timestamp'], rows['control_plane_attempts'][0]['end_timestamp']]
    observed.extend(entry['publication_timestamp'] for entry in rows['effect_journal_entries'])
    assert all(value in clock.observations for value in observed), (observed, clock.observations)
    assert len(set(observed)) > 1, 'fresh publication observations must not reuse one admission timestamp'
    assert rows['final_truth_records'][0]['result_class'] == 'success'


def unavailable_clock():
    raise ValueError('selected-clock-unavailable')


async def assert_retained_retry(family, folder, before):
    owner, request = await retained_request(family, folder, utc_now=unavailable_clock)
    await repeat_closeout(family, owner, request)
    assert await records(database_for(family, folder)) == before


async def cards_pipeline(test_root, workspace, db_path, clock, monkeypatch):
    await asyncio.to_thread(_write_epic_assets, test_root, 'clock_epic')
    pipeline = await run_owned_thread(partial(ExecutionPipeline, workspace=workspace, config_root=test_root,
        db_path=db_path, runtime_inputs=clock), label='clock-pipeline-construction')

    async def complete_card(**_kwargs):
        await accept_publication_card(pipeline, workspace)

    monkeypatch.setattr(pipeline.orchestrator, 'execute_epic', complete_card)
    return pipeline


async def test_cards_pipeline_clock_reaches_parent_and_transaction_closeout(test_root, workspace, db_path, monkeypatch):
    clock = RecordingInputs()
    pipeline = await cards_pipeline(test_root, workspace, db_path, clock, monkeypatch)
    try:
        result = await pipeline.run_epic('clock_epic', session_id='clock-session', build_id='clock-build')
        assert result.succeeded
        rows = await records(Path(pipeline.orchestrator.control_plane_execution_repository.db_path))
        assert_selected_clock(rows, clock)
        selected = pipeline.cards_epic_control_plane
        retry = CardsEpicControlPlaneService(execution_repository=selected.execution_repository,
            publication=selected.publication, transactions=selected.transactions, utc_now=unavailable_clock)
        await retry.finalize_execution(run_id=rows['control_plane_runs'][0]['run_id'], session_status='done')
        assert await records(Path(pipeline.orchestrator.control_plane_execution_repository.db_path)) == rows
    finally:
        await pipeline.close()


async def extension_manager(tmp_path, family, clock, construction):
    source = tmp_path / 'extension-source'
    await asyncio.to_thread(source.mkdir)
    await run_owned_thread(partial(_init_sdk_extension_repo if family == 'sdk' else _init_test_extension_repo, source),
        label='clock-extension-fixture')
    values = dict(project_root=tmp_path, catalog_path=tmp_path / 'extensions_catalog.json', utc_now=clock.utc_now_iso)
    manager = (await prepare_extension_manager(**values) if construction == 'async'
        else await run_owned_thread(partial(ExtensionManager, **values), label='clock-extension-construction'))
    await manager.install_from_repo(str(source))
    return manager


async def run_extension(manager, tmp_path, family):
    return await manager.run_workload(workload_id='sdk_v1' if family == 'sdk' else 'mystery_v1',
        input_config={'seed': 321, 'mode': 'basic'}, workspace=tmp_path / 'workspace/default', department='core')


@pytest.mark.parametrize('family', ['legacy', 'sdk'])
@pytest.mark.parametrize('construction', ['direct', 'async'])
async def test_extension_manager_clock_reaches_workload_and_transaction_closeout(tmp_path, family, construction):
    clock = RecordingInputs()
    manager = await extension_manager(tmp_path, family, clock, construction)
    await run_extension(manager, tmp_path, family)
    rows = await records(database_for(family, tmp_path))
    assert_selected_clock(rows, clock)
    await assert_retained_retry(family, tmp_path, rows)


async def test_review_clock_reaches_creation_and_transaction_closeout(tmp_path):
    clock = RecordingInputs()
    owner = await run_owned_thread(partial(build_review_run_control_plane_service,
        database_for('review', tmp_path), utc_now=clock.utc_now_iso), label='clock-review-construction')
    await run_owned_thread(partial(review_flow, tmp_path, control_plane_service=owner), label='clock-review-execution')
    rows = await records(database_for('review', tmp_path))
    assert_selected_clock(rows, clock)
    await assert_retained_retry('review', tmp_path, rows)


@pytest.mark.parametrize('family', ['cards', 'review', 'legacy', 'sdk'])
async def test_closeout_clock_failure_retains_unfinished_authority(test_root, workspace, db_path, monkeypatch, family):
    clock = RecordingInputs()
    pipeline = None
    if family == 'cards':
        pipeline = await cards_pipeline(test_root, workspace, db_path, clock, monkeypatch)
        owner = pipeline.cards_epic_control_plane
        database = Path(pipeline.orchestrator.control_plane_execution_repository.db_path)
        run = partial(pipeline.run_epic, 'clock_epic', session_id='failed-clock-session', build_id='failed-clock-build')
    elif family == 'review':
        database = database_for(family, test_root)
        owner = await run_owned_thread(partial(build_review_run_control_plane_service, database,
            utc_now=clock.utc_now_iso), label='failed-clock-review-construction')
        run = partial(run_owned_thread, partial(review_flow, test_root, control_plane_service=owner),
            label='failed-clock-review-execution')
    else:
        manager = await extension_manager(test_root, family, clock, 'async')
        owner, database = manager.workload_executor.control_plane, database_for(family, test_root)
        run = partial(run_extension, manager, test_root, family)
    method = 'finalize_completed' if family == 'review' else 'finalize_execution'
    finalize = getattr(owner, method)
    boundaries = []

    async def fail_clock_at_closeout(**values):
        boundaries.append(values)
        clock.unavailable = True
        return await finalize(**values)

    monkeypatch.setattr(owner, method, fail_clock_at_closeout)
    try:
        if family == 'cards':
            result = await run()
            assert not result.succeeded and result.observation == 'unresolved'
            assert 'selected-clock-unavailable' in result.reason
        else:
            with pytest.raises(ValueError, match='selected-clock-unavailable'):
                await run()
        assert boundaries
        if family in {'legacy', 'sdk'}:
            assert boundaries[0]['outcome'].value == 'success'
        elif family == 'cards':
            assert boundaries[0]['session_status'] == 'done'
        rows = await records(database)
        assert len(rows['control_plane_runs']) == len(rows['control_plane_attempts']) == 1
        assert rows['control_plane_runs'][0]['lifecycle_state'] == 'executing'
        assert rows['control_plane_attempts'][0]['end_timestamp'] is None
        assert rows['final_truth_records'] == []
        assert len(rows['effect_journal_entries']) == 1
    finally:
        if pipeline is not None:
            await pipeline.close()
