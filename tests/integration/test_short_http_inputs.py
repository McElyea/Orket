"""Layer: integration. Actual network routing, TLS, request snapshots and admission."""
import asyncio
import base64
import threading
from urllib.parse import parse_qs, urlsplit

import pytest

from orket.application.services import owned_http_request_service as module
from orket.application.services.outward_connector_service import OutwardConnectorService
from orket.application.services.owned_http_request_service import OwnedHttpRequestService
from tests.helpers.gitea_http_observation import observe_resources
from tests.helpers.observed_http_server import observed_http_server
from tests.integration.test_provider_http_environment import _ambient_proxy
from tests.integration.test_provider_http_tls_inputs import FIXTURES, server_context
from tests.integration.test_short_http_ownership import assert_success, clean_network, composed_request, response

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('kind', ['get', 'post'])
async def test_builtin_http_observes_operator_network_changes_between_requests(tmp_path, monkeypatch, kind):
    clean_network(monkeypatch)
    async with (observed_http_server(response) as first, observed_http_server(response) as second,
                composed_request(kind, tmp_path, 'http://127.0.0.1:1') as invoke):
        _ambient_proxy(monkeypatch, first[0])
        assert_success(kind, await invoke())
        _ambient_proxy(monkeypatch, second[0])
        assert_success(kind, await invoke())
        assert len(first[1]) == len(second[1]) == 1
        assert first[1][0] == second[1][0]


@pytest.mark.parametrize('source', ['mapping', 'ambient'])
async def test_short_http_captures_network_body_query_headers_before_native_wait(tmp_path, monkeypatch, source):
    clean_network(monkeypatch)
    entered, release = threading.Event(), threading.Event()
    original = module._construct

    def held(**options):
        entered.set()
        assert release.wait(5), 'Request native construction did not release'
        return original(**options)

    context = await asyncio.to_thread(server_context)
    headers = []
    async with observed_http_server(response, ssl_context=context, request_headers=headers) as proxy:
        environment = {'HTTP_PROXY': proxy[0].replace('https://', 'https://proxy-user:public-password@'),
                       'NO_PROXY': '', 'SSL_CERT_FILE': 'ca.pem'}
        monkeypatch.chdir(FIXTURES)
        if source == 'ambient':
            for name, value in environment.items():
                monkeypatch.setenv(name, value)
        requester = OwnedHttpRequestService(environment=environment if source == 'mapping' else None)
        body, query, extra = {'nested': ['captured']}, {'q': ['original']}, {'X-Fixture': 'original'}
        monkeypatch.setattr(module, '_construct', held)
        task = asyncio.create_task(requester.request('POST', 'http://unresolved-request.invalid/fixture',
            timeout_s=2, json=body, params=query, headers=extra, auth=('fixture', 'public-secret')))
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            environment.clear()
            monkeypatch.setenv('HTTP_PROXY', 'http://127.0.0.1:1')
            monkeypatch.setenv('SSL_CERT_FILE', 'missing.pem')
            monkeypatch.chdir(tmp_path)
            body['nested'].append('changed')
            query['q'].append('changed')
            extra['X-Fixture'] = 'changed'
            release.set()
            assert (await asyncio.wait_for(asyncio.shield(task), 5)).status_code == 200
            assert len(proxy[1]) == 1 and proxy[1][0][1] == {'nested': ['captured']}
            target = urlsplit(proxy[1][0][0].split()[1])
            assert target.netloc == 'unresolved-request.invalid' and parse_qs(target.query) == {'q': ['original']}
            assert headers[0]['x-fixture'] == 'original'
            assert headers[0]['authorization'] == 'Basic ' + base64.b64encode(b'fixture:public-secret').decode()
            assert headers[0]['proxy-authorization'] == 'Basic ' + base64.b64encode(b'proxy-user:public-password').decode()
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)


@pytest.mark.parametrize('kind', ['export', 'get', 'post'])
@pytest.mark.parametrize('trusted', [True, False], ids=['trusted', 'untrusted'])
async def test_short_http_actual_tls_preserves_trust_and_authentication(tmp_path, monkeypatch, kind, trusted):
    clean_network(monkeypatch)
    context = await asyncio.to_thread(server_context)
    environment = {'SSL_CERT_FILE': str(FIXTURES / ('ca.pem' if trusted else 'unrelated-ca.pem'))}
    monkeypatch.setenv('SSL_CERT_FILE', environment['SSL_CERT_FILE'])
    headers = []
    async with (observed_http_server(response, ssl_context=context, request_headers=headers) as server,
                composed_request(kind, tmp_path, server[0], environment) as invoke):
        resources, closed = observe_resources(monkeypatch)
        if trusted:
            assert_success(kind, await invoke())
            assert len(server[1]) == 1
            if kind == 'export':
                expected = 'Basic ' + base64.b64encode(b'fixture-user:public-password').decode()
                assert headers[0]['authorization'] == expected
            else:
                assert 'authorization' not in headers[0]
        elif kind == 'export':
            with pytest.raises(RuntimeError, match='E_GITEA_EXPORT_HTTP_UNAVAILABLE'):
                await invoke()
        else:
            event, result = await invoke()
            assert event['outcome'] == 'failed' and not result['ok']
            assert 'CERTIFICATE_VERIFY_FAILED' in result['error']
        if not trusted:
            assert not server[1]
        assert len(resources) == 2 and all(resource in closed for resource in resources)
        assert resources[-1].is_closed


@pytest.mark.parametrize('kind', ['get', 'post'])
async def test_builtin_http_denied_host_never_constructs_or_sends(tmp_path, monkeypatch, kind):
    clean_network(monkeypatch)
    service = await OutwardConnectorService.for_workspace(tmp_path, http_allowlist=('example.invalid',))
    resources, closed = observe_resources(monkeypatch)
    async with observed_http_server(response) as server:
        arguments = {'url': server[0]}
        if kind == 'post':
            arguments['body'] = {}
        event, result = await service.invoke_with_result('http_' + kind, arguments)
        assert event['outcome'] == 'failed' and not result['ok']
        assert result['error'] == 'HTTP host is not allowlisted: 127.0.0.1'
        assert not server[1] and resources == closed == []
