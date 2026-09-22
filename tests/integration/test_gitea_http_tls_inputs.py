"""Layer: integration. Verified Gitea TLS and captured native network configuration."""
import asyncio
import base64

import httpx
import pytest

from orket.adapters.storage.gitea_state_errors import GiteaAdapterNetworkError
from orket.application.services import gitea_state_adapter_factory, gitea_webhook_runtime
from tests.helpers.gitea_http_observation import create_gitea_owner, http_client, observe_request
from tests.helpers.observed_http_server import observed_http_server
from tests.integration.test_gitea_http_input_capture import response_for
from tests.integration.test_provider_http_environment import _ambient_proxy
from tests.integration.test_provider_http_tls_inputs import FIXTURES, server_context

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('kind', ['state', 'webhook'])
@pytest.mark.parametrize('mode', ['file', 'directory', 'file-precedence', 'empty', 'wrong-file', 'missing-file'])
async def test_gitea_tls_requires_captured_trust(tmp_path, monkeypatch, kind, mode):
    context = await asyncio.to_thread(server_context)
    ambient_log = tmp_path / 'ambient-keys.log'
    _ambient_proxy(monkeypatch, 'http://127.0.0.1:1')
    monkeypatch.setenv('SSL_CERT_FILE', str(FIXTURES / 'ca.pem'))
    monkeypatch.setenv('SSLKEYLOGFILE', str(ambient_log))
    environments = {
        'file': {'SSL_CERT_FILE': 'ca.pem'}, 'directory': {'SSL_CERT_DIR': 'trust-directory'},
        'file-precedence': {'SSL_CERT_FILE': 'ca.pem', 'SSL_CERT_DIR': 'missing-directory'},
        'empty': {}, 'wrong-file': {'SSL_CERT_FILE': 'unrelated-ca.pem'},
        'missing-file': {'SSL_CERT_FILE': 'missing.pem'},
    }
    environment = dict(environments[mode], ORKET_DURABLE_ROOT=str(tmp_path / 'durable'))
    async with observed_http_server(response_for(kind, 'verified'), ssl_context=context) as server:
        call = create_gitea_owner(kind, tmp_path, server[0], environment=environment, cwd=FIXTURES)
        if mode == 'missing-file':
            with pytest.raises(FileNotFoundError):
                await call
        else:
            owner = await call
            try:
                if mode in {'empty', 'wrong-file'}:
                    expected = GiteaAdapterNetworkError if kind == 'state' else httpx.ConnectError
                    with pytest.raises(expected):
                        await observe_request(owner)
                else:
                    assert await observe_request(owner) == ([] if kind == 'state' else {'version': 'verified'})
                    assert len(server[1]) == 1
            finally:
                await owner.close()
                assert http_client(owner).is_closed
        if mode in {'empty', 'wrong-file', 'missing-file'}:
            assert server[1] == []
    assert not await asyncio.to_thread(ambient_log.exists)


@pytest.mark.parametrize('kind', ['state', 'webhook'])
@pytest.mark.parametrize('source', ['mapping', 'ambient'])
async def test_gitea_capture_precedes_native_dispatch(tmp_path, monkeypatch, kind, source):
    context = await asyncio.to_thread(server_context)
    entered, release = asyncio.Event(), asyncio.Event()
    module = gitea_state_adapter_factory if kind == 'state' else gitea_webhook_runtime
    original = module.create_runtime_owner

    async def held(operation, **options):
        entered.set()
        await asyncio.wait_for(release.wait(), 5)
        return await original(operation, **options)

    monkeypatch.setattr(module, 'create_runtime_owner', held)
    headers = []
    async with observed_http_server(response_for(kind, 'captured'), ssl_context=context,
                                    request_headers=headers) as proxy:
        keylog = tmp_path / 'captured-keys.log'
        supplied = {'HTTP_PROXY': proxy[0].replace('https://', 'https://proxy-user:public-proxy-password@'),
            'NO_PROXY': '', 'SSL_CERT_FILE': 'ca.pem', 'SSLKEYLOGFILE': str(keylog),
            'ORKET_DURABLE_ROOT': str(tmp_path / 'durable')}
        _ambient_proxy(monkeypatch, '')
        if source == 'ambient':
            for name, value in supplied.items():
                monkeypatch.setenv(name, value)
        monkeypatch.chdir(FIXTURES)
        operation = asyncio.create_task(create_gitea_owner(kind, tmp_path, 'http://unresolved-gitea.invalid',
            environment=supplied if source == 'mapping' else None))
        owner = None
        try:
            await asyncio.wait_for(entered.wait(), 5)
            supplied.clear()
            monkeypatch.chdir(tmp_path)
            monkeypatch.setenv('SSL_CERT_FILE', 'missing.pem')
            monkeypatch.setenv('HTTP_PROXY', 'http://127.0.0.1:1')
            release.set()
            owner = await asyncio.wait_for(asyncio.shield(operation), 5)
            assert await observe_request(owner) == ([] if kind == 'state' else {'version': 'captured'})
            assert len(proxy[1]) == 1
            expected = base64.b64encode(b'proxy-user:public-proxy-password').decode()
            assert headers[0]['proxy-authorization'] == 'Basic ' + expected
            authorization = ('token public-token' if kind == 'state' else
                             'Basic ' + base64.b64encode(b'fixture-user:public-password').decode())
            assert headers[0]['authorization'] == authorization
            assert 'CLIENT_TRAFFIC_SECRET' in await asyncio.to_thread(keylog.read_text)
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(operation, return_exceptions=True), 5)
            if owner is not None:
                await owner.close()
                assert http_client(owner).is_closed


async def test_webhook_builder_freezes_storage_and_http_configuration_together(tmp_path, monkeypatch):
    entered, release = asyncio.Event(), asyncio.Event()
    original = gitea_webhook_runtime.create_runtime_owner

    async def held(operation, **options):
        entered.set()
        await asyncio.wait_for(release.wait(), 5)
        return await original(operation, **options)

    monkeypatch.setattr(gitea_webhook_runtime, 'create_runtime_owner', held)
    supplied = {'ORKET_DURABLE_ROOT': str(tmp_path / 'captured')}
    async with observed_http_server(response_for('webhook', 'captured')) as server:
        operation = asyncio.create_task(create_gitea_owner('webhook', tmp_path, server[0],
            environment=supplied, cwd=tmp_path))
        owner = None
        try:
            await asyncio.wait_for(entered.wait(), 5)
            supplied['ORKET_DURABLE_ROOT'] = str(tmp_path / 'changed')
            supplied['HTTP_PROXY'] = 'http://127.0.0.1:1'
            release.set()
            owner = await asyncio.wait_for(asyncio.shield(operation), 5)
            assert await observe_request(owner) == {'version': 'captured'} and len(server[1]) == 1
            assert owner._review_db_path == str(tmp_path / 'captured/db/orket_persistence.db')
            assert owner.configuration.environment == {'ORKET_DURABLE_ROOT': str(tmp_path / 'captured')}
            assert not await asyncio.to_thread((tmp_path / 'changed').exists)
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(operation, return_exceptions=True), 5)
            if owner is not None:
                await owner.close()
                assert http_client(owner).is_closed
