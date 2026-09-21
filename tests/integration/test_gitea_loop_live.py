"""Owned real Gitea and canonical card publication; controlled executor, no inference claim."""
import asyncio
import json
import os
from pathlib import Path

import httpx
import pytest

import orket.runtime.execution.gitea_state_loop as loop_module
from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.adapters.storage.gitea_state_models import decode_snapshot, parse_event_comment
from orket.application.services.runtime_result_projection import RuntimeOutcomeError
from tests.helpers.gitea_loop_inputs import RecordingClock, construction_inputs, gitea_pipeline
from tests.helpers.gitea_server import local_gitea
from tests.helpers.remaining_family_authority import records
from tests.integration.test_epic_completion_publication import accept_publication_card
from tests.integration.test_gitea_terminal_live import _assert_observation, _create_card

pytestmark = [pytest.mark.integration, pytest.mark.asyncio,
    pytest.mark.skipif(os.getenv('ORKET_RUN_GITEA_STATE_ACCEPTANCE') != '1',
        reason='Explicit owned localhost Gitea acceptance required')]


@pytest.mark.parametrize('outcome', ['success', 'unresolved-work'])
async def test_public_pipeline_loop_actual_gitea_and_card_publication(tmp_path, monkeypatch, outcome):
    files, clock, workers = AsyncFileTools(tmp_path), RecordingClock(), []
    worker_type = loop_module.GiteaStateWorker

    def observed_worker(**values):
        worker = worker_type(**values)
        workers.append(worker)
        return worker

    monkeypatch.setattr(loop_module, 'GiteaStateWorker', observed_worker)
    async with local_gitea() as server, httpx.AsyncClient(base_url=server.url,
            auth=(server.username, server.password)) as client:
        setup_adapter, issue_path, card_id = await _create_card(server, client)
        environment = dict(construction_inputs(tmp_path).environment, ORKET_GITEA_URL=server.url,
            ORKET_GITEA_TOKEN=setup_adapter._token.reveal(), ORKET_GITEA_OWNER=server.username,
            ORKET_GITEA_REPO='worker-proof', ORKET_DURABLE_ROOT='loop-state', ORKET_DISABLE_SANDBOX='1',
            ORKET_GITEA_ARTIFACT_EXPORT='0', ORKET_RUN_LEDGER_MODE='sqlite')
        await setup_adapter.close()
        pipeline = await gitea_pipeline(tmp_path, inputs=construction_inputs(tmp_path, environment=environment), clock=clock)

        async def controlled_executor(**_kwargs):
            await files.write_file('physical-work.txt', 'executed')
            if outcome == 'unresolved-work':
                raise RuntimeError('controlled executor failure after physical effect')
            await accept_publication_card(pipeline, pipeline.workspace)

        monkeypatch.setattr(pipeline.orchestrator, 'execute_epic', controlled_executor)
        try:
            await run_and_check_summary(pipeline, files, outcome)
            assert len(workers) == 1 and workers[0].adapter.http._client.is_closed
            if outcome == 'success':
                await _assert_observation(client, issue_path, workers[0], card_id, outcome, files)
                await assert_local_publication(pipeline, workers[0], clock)
            else:
                await assert_unresolved_work(pipeline, workers[0], client, issue_path, card_id, files)
            version = await client.get('/api/v1/version')
            version.raise_for_status()
            await files.write_file('server.txt', server.container_id + '\n' + version.json()['version'])
        finally:
            await pipeline.close()
    await files.write_file('teardown.txt', 'owned Gitea removal verified')


async def run_and_check_summary(pipeline, files, outcome):
    operation = pipeline.run_gitea_state_loop(worker_id='live-loop', max_iterations=1,
        max_duration_seconds=60, lease_seconds=60, renew_interval_seconds=30, summary_out='summary.json')
    if outcome == 'unresolved-work':
        with pytest.raises(RuntimeOutcomeError) as error:
            await operation
        assert error.value.result.observation == 'unresolved' and not error.value.result.succeeded
        assert 'controlled executor failure after physical effect' in error.value.result.reason
        assert not await asyncio.to_thread((pipeline.runtime_context.construction_inputs.invocation_root / 'summary.json').exists)
    else:
        result = await operation
        assert result['summary']['iterations'] == result['summary']['consumed_count'] == 1
        assert json.loads(await files.read_file('summary.json')) == result['summary']


async def assert_local_publication(pipeline, worker, clock):
    db = Path(pipeline.orchestrator.control_plane_execution_repository.db_path)
    assert Path(worker.control_plane_execution_service.execution_repository.db_path) == db
    rows = await records(db)
    assert len(rows['control_plane_runs']) == len(rows['final_truth_records']) == 2
    assert {row['result_class'] for row in rows['final_truth_records']} == {'success'}
    gitea_run, = [row for row in rows['control_plane_runs'] if row['workload_id'] == worker.control_plane_execution_service.WORKLOAD.workload_id]
    configuration = await worker.control_plane_execution_service.publication.repository.get_resolved_configuration_snapshot(
        snapshot_id=gitea_run['configuration_snapshot_id'])
    assert gitea_run['creation_timestamp'] == configuration.configuration_payload['lease_observation']['lease']['acquired_at']
    observed = [row['creation_timestamp'] for row in rows['control_plane_runs'] if row is not gitea_run]
    observed += [row['end_timestamp'] for row in rows['control_plane_attempts']]
    assert all(stamp in clock.utc_observations for stamp in observed), (observed, clock.utc_observations)
    assert len(set(observed)) > 1 and len(clock.monotonic_observations) == 3
    assert await asyncio.to_thread(db.is_file)


async def assert_unresolved_work(pipeline, worker, client, issue_path, card_id, files):
    response = await client.get(issue_path)
    response.raise_for_status()
    remote = decode_snapshot(response.json()['body'])
    response = await client.get(issue_path + '/comments')
    response.raise_for_status()
    events = [parse_event_comment(row['body']) for row in response.json() if row['body'].startswith('[ORKET_EVENT_V1]')]
    assert remote.state == 'in_progress' and remote.lease.owner_id == 'live-loop'
    assert not any(event.event_type == 'release_or_fail' for event in events)
    rows = await records(Path(pipeline.orchestrator.control_plane_execution_repository.db_path))
    assert len(rows['control_plane_runs']) == 2 and rows['final_truth_records'] == []
    assert all(row['end_timestamp'] is None for row in rows['control_plane_attempts'])
    lease = await worker.control_plane_execution_service.publication.repository.get_latest_lease_record(
        lease_id=f'gitea-card-lease:{card_id}')
    assert lease.status.value == 'lease_active'
    assert await files.read_file('physical-work.txt') == 'executed'
    await files.write_file('remote-unresolved.txt', remote.model_dump_json())
