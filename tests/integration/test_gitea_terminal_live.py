"""Actual localhost Gitea, worker, SQLite and physical work with verified teardown."""
import os

import httpx
import pytest

from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.adapters.storage.gitea_state_adapter import GiteaStateAdapter
from orket.adapters.storage.gitea_state_models import (
    CardSnapshot,
    decode_snapshot,
    encode_snapshot,
    parse_event_comment,
)
from orket.application.services.gitea_state_control_plane_checkpoint_service import (
    build_gitea_state_control_plane_checkpoint_service,
)
from orket.application.services.gitea_state_control_plane_execution_service import (
    build_gitea_state_control_plane_execution_service,
)
from orket.application.services.gitea_state_control_plane_lease_service import (
    build_gitea_state_control_plane_lease_service,
)
from orket.application.services.gitea_state_control_plane_reservation_service import (
    build_gitea_state_control_plane_reservation_service,
)
from orket.application.services.gitea_state_worker import GiteaStateWorker, LeaseExpiredError
from tests.helpers.gitea_server import local_gitea
from tests.integration.test_governed_agent_terminal_history import logical_state

pytestmark = [pytest.mark.integration, pytest.mark.asyncio,
              pytest.mark.skipif(os.getenv('ORKET_RUN_GITEA_STATE_ACCEPTANCE') != '1',
                                 reason='Explicit owned localhost Gitea acceptance required')]


async def _create_card(server, client):
    response = await client.post('/api/v1/user/repos', json={'name': 'worker-proof', 'auto_init': True})
    response.raise_for_status()
    path = f'/api/v1/repos/{server.username}/worker-proof'
    response = await client.post(path+'/labels', json={'name': 'status/ready', 'color': '00aa00'})
    response.raise_for_status()
    label = response.json()['id']
    response = await client.post(path+'/issues', json={'title': 'Owned worker acceptance', 'labels': [label],
        'body': encode_snapshot(CardSnapshot(card_id='ISSUE-1', state='ready'))})
    response.raise_for_status()
    number = str(response.json()['number'])
    response = await client.post(f'/api/v1/users/{server.username}/tokens',
                                 json={'name': 'worker-proof', 'scopes': ['all']})
    response.raise_for_status()
    adapter = GiteaStateAdapter(base_url=server.url, owner=server.username, repo='worker-proof', token=response.json()['sha1'])
    return adapter, path+'/issues/'+number, number


@pytest.mark.parametrize('outcome', ['success', 'work-failure', 'lease-expiry', 'local-write-failure'])
# Layer: integration
async def test_actual_gitea_closeout_matches_local_terminal_authority(tmp_path, monkeypatch, outcome):
    db, files = tmp_path/'control_plane.sqlite3', AsyncFileTools(tmp_path)
    async with local_gitea() as server, httpx.AsyncClient(base_url=server.url, auth=(server.username, server.password)) as client:
        version = await client.get('/api/v1/version')
        version.raise_for_status()
        await files.write_file('server.txt', server.container_id + '\n' + version.json()['version'])
        adapter, issue_path, card_id = await _create_card(server, client)
        worker = GiteaStateWorker(adapter=adapter, worker_id='worker-a', renew_interval_seconds=30,
            control_plane_execution_service=build_gitea_state_control_plane_execution_service(db),
            control_plane_lease_service=build_gitea_state_control_plane_lease_service(db),
            control_plane_checkpoint_service=build_gitea_state_control_plane_checkpoint_service(db),
            control_plane_reservation_service=build_gitea_state_control_plane_reservation_service(db))
        before = None
        original = AsyncControlPlaneRecordRepository.save_resource_record

        async def interrupted(repository, *, record):
            result = await original(repository, record=record)
            if before is not None and outcome == 'local-write-failure':
                raise OSError('interrupted local resource publication')
            return result

        async def work(_):
            nonlocal before
            await files.write_file('physical-work.txt', 'executed')
            before = await logical_state(db)
            if outcome == 'work-failure':
                raise RuntimeError('actual work failed after physical effect')
            if outcome == 'lease-expiry':
                raise LeaseExpiredError()
            return {'ok': True}

        monkeypatch.setattr(AsyncControlPlaneRecordRepository, 'save_resource_record', interrupted)
        try:
            if outcome == 'local-write-failure':
                with pytest.raises(OSError, match='interrupted local resource'):
                    await worker.run_once(work_fn=work)
                assert await logical_state(db) == before
            else:
                assert await worker.run_once(work_fn=work)
            await _assert_observation(client, issue_path, worker, card_id, outcome, files)
        finally:
            await adapter.close()
    await files.write_file('teardown.txt', 'owned Gitea removal verified')


async def _assert_observation(client, path, worker, card_id, outcome, files):
    response = await client.get(path)
    response.raise_for_status()
    remote = decode_snapshot(response.json()['body'])
    response = await client.get(path+'/comments')
    response.raise_for_status()
    events = [parse_event_comment(row['body']) for row in response.json() if row['body'].startswith('[ORKET_EVENT_V1]')]
    releases = [event for event in events if event.event_type == 'release_or_fail']
    assert len(releases) == 1 and remote.lease.owner_id is None
    assert remote.state == ('blocked' if outcome in {'work-failure', 'lease-expiry'} else 'code_review')
    await files.write_file('remote-snapshot.txt', encode_snapshot(remote))
    await files.write_file('remote-release.txt', releases[0].model_dump_json())
    service = worker.control_plane_execution_service
    run_id = service.run_id_for(card_id=card_id, lease_epoch=remote.lease.epoch)
    truth = await service.publication.repository.get_final_truth(run_id=run_id)
    lease = await service.publication.repository.get_latest_lease_record(lease_id=f'gitea-card-lease:{card_id}')
    if outcome == 'local-write-failure':
        assert truth is None and lease.status.value == 'lease_active'
    else:
        assert truth.result_class.value == {'work-failure': 'failed', 'lease-expiry': 'blocked'}.get(outcome, 'success')
        assert lease.status.value == 'lease_released'
    assert await files.read_file('physical-work.txt') == 'executed'
