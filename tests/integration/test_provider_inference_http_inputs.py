"""Layer: integration. Real provider complete() routing with declared fixture responses."""
import asyncio
from functools import partial

import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.services.local_model_factory import create_local_model_provider
from orket.core.contracts.provider_runtime import ProviderRuntimeTarget
from tests.helpers.observed_http_server import observed_http_server
from tests.integration.test_provider_http_environment import _ambient_proxy

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
MODEL = 'fixture-qwen-network-policy'


def response_for(provider, marker):
    async def respond(request):
        assert request[0].startswith('POST ') and request[1]['model'] == MODEL
        assert any(message.get('role') == 'user' and 'Observe captured network routing.' in message.get('content', '')
                   for message in request[1]['messages'])
        message = {'role': 'assistant', 'content': marker}
        if provider == 'ollama':
            return 200, {'model': MODEL, 'message': message, 'done': True}
        return 200, {'model': MODEL, 'choices': [{'index': 0, 'message': message, 'finish_reason': 'stop'}]}
    return respond


@pytest.mark.parametrize('provider', ['openai_compat', 'ollama'])
@pytest.mark.parametrize('mode', ['empty', 'proxy', 'bypass', 'ambient'])
async def test_provider_complete_uses_captured_network_environment(monkeypatch, provider, mode):
    async with (
        observed_http_server(response_for(provider, 'origin')) as origin,
        observed_http_server(response_for(provider, 'supplied')) as supplied,
        observed_http_server(response_for(provider, 'ambient')) as ambient,
    ):
        _ambient_proxy(monkeypatch, ambient[0])
        environment = None if mode == 'ambient' else {}
        if mode in {'proxy', 'bypass'}:
            environment = {'HTTP_PROXY': supplied[0], 'NO_PROXY': '127.0.0.1' if mode == 'bypass' else ''}
        url = origin[0] + ('/v1' if provider == 'openai_compat' else '')
        target = ProviderRuntimeTarget(provider, provider, MODEL, MODEL, url, 'pinned', 'controlled-fixture',
                                       (MODEL,), (), (), False, False, 'OK')
        client = await run_owned_thread(partial(create_local_model_provider, MODEL, provider=provider,
            base_url=url, timeout=2, connect_timeout_seconds=1, runtime_target=target, environment=environment),
            label='fixture-inference-client-construction')
        transport = client.client if provider == 'openai_compat' else client.client._client
        try:
            result = await asyncio.wait_for(client.complete(
                [{'role': 'user', 'content': 'Observe captured network routing.'}],
                runtime_context={'local_prompting_mode': 'shadow', 'local_prompt_task_class': 'concise_text'}), 5)
            expected = 'ambient' if mode == 'ambient' else ('supplied' if mode == 'proxy' else 'origin')
            actual = dict(content=result.content, origin=len(origin[1]), supplied=len(supplied[1]), ambient=len(ambient[1]))
            assert actual == dict(content=expected, origin=int(expected == 'origin'),
                                  supplied=int(expected == 'supplied'), ambient=int(expected == 'ambient'))
            assert result.raw['model'] == MODEL and result.raw['provider_backend'] == provider
            assert result.raw['runtime_target']['inventory_source'] == 'controlled-fixture'
            selected = dict(origin=origin, supplied=supplied, ambient=ambient)[expected]
            path = '/v1/chat/completions' if provider == 'openai_compat' else '/api/chat'
            address = path if expected == 'origin' else origin[0] + path
            assert selected[1][0][0] == f'POST {address} HTTP/1.1'
        finally:
            await client.close()
            assert transport.is_closed


@pytest.mark.parametrize('provider', ['openai_compat', 'ollama'])
@pytest.mark.parametrize('mode', ['empty', 'captured', 'ambient'])
async def test_inference_outbound_authentication_uses_captured_credentials(monkeypatch, provider, mode):
    key = 'OLLAMA_API_KEY' if provider == 'ollama' else 'ORKET_LLM_OPENAI_API_KEY'
    monkeypatch.setenv(key, 'public-ambient-test-key')
    _ambient_proxy(monkeypatch, '')
    headers = []
    environment = None if mode == 'ambient' else ({key: 'public-captured-test-key'} if mode == 'captured' else {})
    async with observed_http_server(response_for(provider, 'authenticated'), request_headers=headers) as server:
        url = server[0] + ('/v1' if provider == 'openai_compat' else '')
        target = ProviderRuntimeTarget(provider, provider, MODEL, MODEL, url, 'pinned', 'controlled-fixture',
                                       (MODEL,), (), (), False, False, 'OK')
        client = await run_owned_thread(partial(create_local_model_provider, MODEL, provider=provider,
            base_url=url, timeout=2, connect_timeout_seconds=1, runtime_target=target, environment=environment),
            label='fixture-credential-client-construction')
        transport = client.client if provider == 'openai_compat' else client.client._client
        monkeypatch.setenv(key, 'public-later-test-key')
        try:
            result = await asyncio.wait_for(client.complete(
                [{'role': 'user', 'content': 'Observe captured network routing.'}],
                runtime_context={'local_prompting_mode': 'shadow', 'local_prompt_task_class': 'concise_text'}), 5)
            assert result.content == 'authenticated'
            expected = None if mode == 'empty' else 'Bearer public-' + mode + '-test-key'
            assert len(server[1]) == 1 and headers[0].get('authorization') == expected
        finally:
            await client.close()
            assert transport.is_closed
