"""Layer: integration. Real inference HTTP/TLS, outbound credentials and capture timing."""
import asyncio
import base64

import pytest

from orket.application.services import local_model_factory as factory
from orket.exceptions import ModelConnectionError, ModelProviderError
from tests.helpers.observed_http_server import observed_http_server
from tests.helpers.provider_inference_observation import create_observed_provider, http_transport, observe_completion
from tests.integration.test_provider_http_environment import _ambient_proxy
from tests.integration.test_provider_http_tls_inputs import FIXTURES, server_context
from tests.integration.test_provider_inference_http_inputs import response_for

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('provider', ['openai_compat', 'ollama'])
@pytest.mark.parametrize('mode', ['file', 'directory', 'file-precedence', 'empty', 'wrong-file', 'missing-file'])
async def test_inference_tls_preserves_verification_and_captured_trust(tmp_path, monkeypatch, provider, mode):
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
    async with observed_http_server(response_for(provider, 'verified'), ssl_context=context) as server:
        call = create_observed_provider(provider, server[0], environment=environments[mode], cwd=FIXTURES)
        if mode == 'missing-file':
            with pytest.raises(FileNotFoundError):
                await call
        else:
            client = await call
            transport = http_transport(client)
            try:
                if mode in {'empty', 'wrong-file'}:
                    with pytest.raises(ModelConnectionError):
                        await observe_completion(client)
                else:
                    assert (await observe_completion(client)).content == 'verified'
                    assert len(server[1]) == 1
            finally:
                await client.close()
                assert transport.is_closed
        if mode in {'empty', 'wrong-file', 'missing-file'}:
            assert server[1] == []
    assert not await asyncio.to_thread(ambient_log.exists)


@pytest.mark.parametrize('provider', ['openai_compat', 'ollama'])
@pytest.mark.parametrize('source', ['mapping', 'ambient'])
async def test_async_factory_freezes_trust_proxy_auth_and_cwd_before_dispatch(tmp_path, monkeypatch, provider, source):
    context = await asyncio.to_thread(server_context)
    entered, release = asyncio.Event(), asyncio.Event()
    original = factory.create_runtime_owner

    async def held(operation, **options):
        entered.set()
        await asyncio.wait_for(release.wait(), 5)
        return await original(operation, **options)

    monkeypatch.setattr(factory, 'create_runtime_owner', held)
    headers = []
    async with observed_http_server(response_for(provider, 'captured'), ssl_context=context,
                                    request_headers=headers) as proxy:
        proxy_url = proxy[0].replace('https://', 'https://fixture-user:fixture-pass@')
        key = 'OLLAMA_API_KEY' if provider == 'ollama' else 'ORKET_LLM_OPENAI_API_KEY'
        keylog = tmp_path / 'captured-keys.log'
        supplied = {'HTTP_PROXY': proxy_url, 'SSL_CERT_FILE': 'ca.pem', 'SSLKEYLOGFILE': str(keylog),
                    key: 'public-captured-test-key', 'NO_PROXY': ''}
        _ambient_proxy(monkeypatch, '')
        if source == 'ambient':
            for name, value in supplied.items():
                monkeypatch.setenv(name, value)
        monkeypatch.chdir(FIXTURES)
        operation = asyncio.create_task(create_observed_provider(provider, 'http://unresolved-inference.invalid',
            environment=supplied if source == 'mapping' else None))
        client = None
        try:
            await asyncio.wait_for(entered.wait(), 5)
            supplied.clear()
            monkeypatch.chdir(tmp_path)
            monkeypatch.setenv('SSL_CERT_FILE', 'missing.pem')
            monkeypatch.setenv(key, 'public-later-test-key')
            monkeypatch.setenv('HTTP_PROXY', 'http://127.0.0.1:1')
            release.set()
            client = await asyncio.wait_for(asyncio.shield(operation), 5)
            assert (await observe_completion(client)).content == 'captured'
            assert len(proxy[1]) == 1
            assert headers[0]['authorization'] == 'Bearer public-captured-test-key'
            expected = base64.b64encode(b'fixture-user:fixture-pass').decode()
            assert headers[0]['proxy-authorization'] == 'Basic ' + expected
            assert 'CLIENT_TRAFFIC_SECRET' in await asyncio.to_thread(keylog.read_text)
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(operation, return_exceptions=True), 5)
            if client is not None:
                await client.close()
                assert http_transport(client).is_closed


@pytest.mark.parametrize('provider', ['openai_compat', 'ollama'])
async def test_inference_backend_redirect_behavior_is_preserved(provider):
    async def redirect(request):
        return 307, {'redirect': True}

    async with observed_http_server(response_for(provider, 'redirected')) as destination:
        path = '/api/chat' if provider == 'ollama' else '/v1/chat/completions'
        async with observed_http_server(redirect, response_headers=[('Location', destination[0] + path)]) as source:
            client = await create_observed_provider(provider, source[0], environment={})
            try:
                if provider == 'ollama':
                    assert (await observe_completion(client)).content == 'redirected'
                    assert len(destination[1]) == 1
                else:
                    with pytest.raises(ModelProviderError):
                        await observe_completion(client)
                    assert not destination[1]
                assert len(source[1]) == 1
            finally:
                await client.close()
                assert http_transport(client).is_closed
