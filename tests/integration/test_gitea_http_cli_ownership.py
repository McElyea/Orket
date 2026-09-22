"""Layer: integration. Both Gitea CLI implementations use actual HTTP and SQLite owners."""
import asyncio
import threading

import pytest

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.adapters.storage.gitea_state_models import CardSnapshot, encode_snapshot
from orket.core.domain.records import IssueRecord
from scripts.gitea import reconcile_state_backends as reconciliation
from scripts.gitea import run_gitea_state_worker_coordinator as coordinator
from tests.application.test_run_gitea_state_worker_coordinator_script import _args
from tests.helpers.gitea_http_observation import observe_resources
from tests.helpers.observed_http_server import observed_http_server
from tests.integration.test_gitea_http_input_capture import captured_environment
from tests.integration.test_gitea_http_ownership import interrupt
from tests.integration.test_provider_http_environment import _ambient_proxy

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def prepare(root, monkeypatch, address):
    monkeypatch.chdir(root)
    _ambient_proxy(monkeypatch, '')
    for name in ('SSL_CERT_FILE', 'SSL_CERT_DIR', 'SSLKEYLOGFILE'):
        monkeypatch.delenv(name, raising=False)
    for name, value in captured_environment('state', 'empty', root, address, '').items():
        monkeypatch.setenv(name, value)
    database = root / 'durable/db/orket_persistence.db'
    await asyncio.to_thread(database.parent.mkdir, parents=True)
    await AsyncCardRepository(database).save(IssueRecord(id='1', seat='fixture', summary='Reconciliation fixture'))
    return database


def response(kind):
    return [] if kind == 'coordinator' else {
        'number': 1, 'body': encode_snapshot(CardSnapshot(card_id='1', state='ready', version=3))}


def invocation(kind, args, card_ids):
    return coordinator._run_loop(args) if kind == 'coordinator' else reconciliation._run(card_ids)


@pytest.mark.parametrize('kind', ['coordinator', 'reconciliation'])
async def test_gitea_scripts_freeze_inputs_and_close_actual_clients(tmp_path, monkeypatch, kind):
    entered, release = threading.Event(), threading.Event()
    module = coordinator if kind == 'coordinator' else reconciliation
    original = module.create_gitea_state_adapter
    resources, closed = observe_resources(monkeypatch)
    options = []

    def held(**values):
        options.append(values)
        entered.set()
        assert release.wait(5), 'CLI construction escaped its native owner'
        return original(**values)

    monkeypatch.setattr(module, 'create_gitea_state_adapter', held)

    async def respond(_request):
        return 200, response(kind)

    async with observed_http_server(respond) as server:
        database = await prepare(tmp_path, monkeypatch, server[0])
        args, card_ids = _args(worker_id='captured-worker', max_idle_streak=1), ['1']
        task = asyncio.create_task(invocation(kind, args, card_ids))
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            args.worker_id, args.fetch_limit = 'changed-worker', 99
            card_ids.append('2')
            monkeypatch.setenv('ORKET_GITEA_URL', 'http://127.0.0.1:1')
            monkeypatch.setenv('ORKET_DURABLE_ROOT', str(tmp_path / 'changed'))
            monkeypatch.setenv('HTTP_PROXY', 'http://127.0.0.1:1')
            monkeypatch.chdir(tmp_path.parent)
            release.set()
            result = await asyncio.wait_for(asyncio.shield(task), 5)
            if kind == 'coordinator':
                assert result['worker_id'] == 'captured-worker' and result['fetch_limit'] == 5
                assert result['summary']['stop_reason'] == 'max_idle_streak'
            else:
                assert result['ok'] and result['checked_count'] == 1 and result['rows'][0]['gitea_version'] == 3
            assert options[0]['cwd'] == tmp_path and options[0]['base_url'] == server[0]
            assert len(server[1]) == 1 and server[1][0][0].startswith('GET ')
            assert (await AsyncCardRepository(database).get_by_id('1')).status.value == 'ready'
            assert not await asyncio.to_thread((tmp_path / 'changed').exists)
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        assert len(resources) == 2 and all(item in closed for item in resources) and resources[-1].is_closed


@pytest.mark.parametrize('kind', ['coordinator', 'reconciliation'])
@pytest.mark.parametrize('mode', ['partial-failure', 'cancel', 'repeated', 'timeout'])
async def test_gitea_scripts_close_after_partial_composition_and_request_interruption(tmp_path, monkeypatch, kind, mode):
    arrived, release = asyncio.Event(), asyncio.Event()
    resources, closed = observe_resources(monkeypatch)

    async def respond(_request):
        arrived.set()
        await asyncio.wait_for(release.wait(), 5)
        # No successful response is expected after interruption. The server
        # requires real peer EOF and retains its handler through socket close.
        return None

    if mode == 'partial-failure':
        def failed(**_options):
            raise OSError('controlled CLI composition failure after HTTP construction')

        monkeypatch.setattr(coordinator if kind == 'coordinator' else reconciliation,
                            'GiteaStateWorker' if kind == 'coordinator' else 'StateReconciliationService', failed)
    timeout = asyncio.timeout(None)
    async with observed_http_server(respond, allow_disconnect=True) as server:
        await prepare(tmp_path, monkeypatch, server[0])

        async def invoke():
            async with timeout:
                return await invocation(kind, _args(worker_id='interrupted-worker', max_idle_streak=1), ['1'])

        task = asyncio.create_task(invoke())
        try:
            if mode != 'partial-failure':
                await asyncio.wait_for(arrived.wait(), 5)
                # The real request may finish cancelling immediately; keep cleanup
                # held to prove the caller remains alive until its actual close.
                transport = resources[-1]
                original = transport.aclose
                async def held_close():
                    await asyncio.wait_for(release.wait(), 5)
                    await original()
                monkeypatch.setattr(transport, 'aclose', held_close)
                await interrupt(task, mode, timeout)
            release.set()
            expected = OSError if mode == 'partial-failure' else (
                TimeoutError if mode == 'timeout' else asyncio.CancelledError)
            with pytest.raises(expected):
                await asyncio.wait_for(asyncio.shield(task), 5)
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        assert len(server[1]) == int(mode != 'partial-failure')
        assert len(resources) == 2 and all(item in closed for item in resources) and resources[-1].is_closed
