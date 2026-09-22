"""Layer: integration. Actual Gitea composition and HTTP routing with controlled local servers."""
import asyncio
import base64
import os
from functools import partial
from urllib.parse import parse_qs, urlsplit

import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.gitea_http_client import GiteaHTTPClient
from orket.application.services.gitea_webhook_runtime import build_webhook_runtime
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.application.services.webhook_configuration import capture_webhook_configuration
from orket.runtime.execution.gitea_state_loop import GiteaStateLoopRunner
from tests.helpers.observed_http_server import observed_http_server
from tests.integration.test_provider_http_environment import _ambient_proxy

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def captured_environment(kind, mode, root, origin, supplied):
    environment = dict(os.environ) if mode == 'ambient' else {}
    environment.update(ORKET_DISABLE_SANDBOX='1', ORKET_DURABLE_ROOT=str(root / 'durable'))
    if mode in {'proxy', 'bypass'}:
        environment.update(HTTP_PROXY=supplied, NO_PROXY='127.0.0.1' if mode == 'bypass' else '')
    if kind == 'state':
        environment.update(ORKET_STATE_BACKEND_MODE='gitea', ORKET_ENABLE_GITEA_STATE_PILOT='1',
            ORKET_GITEA_URL=origin, ORKET_GITEA_TOKEN='public-test-token',
            ORKET_GITEA_OWNER='fixture-owner', ORKET_GITEA_REPO='fixture-repo')
    else:
        environment.update(ORKET_STATE_BACKEND_MODE='local', GITEA_URL=origin, GITEA_ADMIN_USER='Orket',
            GITEA_ADMIN_PASSWORD='public-test-password', GITEA_WEBHOOK_SECRET='public-test-secret',
            ORKET_GITEA_ALLOW_INSECURE='1')
    return environment


def response_for(kind, marker):
    async def respond(_request):
        return 200, [] if kind == 'state' else {'version': marker}
    return respond


async def observe_state_loop(root, environment, monkeypatch):
    clients, original = [], GiteaHTTPClient.__init__
    def observe(client, *args, **options):
        original(client, *args, **options)
        clients.append(client)
    async def forbidden_work(_card):
        raise AssertionError('Controlled empty ready queue must not execute a workload')
    monkeypatch.setattr(GiteaHTTPClient, '__init__', observe)
    inputs = RuntimeConstructionInputs(root, environment, '{}', '{}')
    runner = GiteaStateLoopRunner(state_backend_mode='gitea', organization=None,
        run_card=forbidden_work, construction_inputs=inputs)
    result = await asyncio.wait_for(runner.run(worker_id='network-observer', max_idle_streak=1), 5)
    assert result['summary']['stop_reason'] == 'max_idle_streak'
    assert len(clients) == 1 and clients[0]._client.is_closed
    return None


async def observe_webhook_request(root, environment):
    configuration = await run_owned_thread(partial(capture_webhook_configuration, root,
        environment=environment), label='fixture-webhook-configuration')
    handler = await build_webhook_runtime(configuration)
    observed = []
    async def request():
        response = await handler.client.get(handler.gitea_url + '/api/v1/version')
        response.raise_for_status()
        observed.append(response.json())
    try:
        await asyncio.wait_for(handler.run_request(request), 5)
    finally:
        await handler.close()
    assert handler.closed and handler.client.is_closed and len(observed) == 1
    return observed[0]


@pytest.mark.parametrize('kind', ['state', 'webhook'])
@pytest.mark.parametrize('mode', ['empty', 'proxy', 'bypass', 'ambient'])
async def test_gitea_composition_uses_captured_http_inputs(tmp_path, monkeypatch, kind, mode):
    headers = dict(origin=[], supplied=[], ambient=[])
    async with (
        observed_http_server(response_for(kind, 'origin'), request_headers=headers['origin']) as origin,
        observed_http_server(response_for(kind, 'supplied'), request_headers=headers['supplied']) as supplied,
        observed_http_server(response_for(kind, 'ambient'), request_headers=headers['ambient']) as ambient,
    ):
        _ambient_proxy(monkeypatch, ambient[0])
        for name in ('SSL_CERT_FILE', 'SSL_CERT_DIR', 'SSLKEYLOGFILE'):
            monkeypatch.delenv(name, raising=False)
        environment = captured_environment(kind, mode, tmp_path, origin[0], supplied[0])
        observed = (await observe_state_loop(tmp_path, environment, monkeypatch) if kind == 'state'
                    else await observe_webhook_request(tmp_path, environment))
        expected = 'ambient' if mode == 'ambient' else ('supplied' if mode == 'proxy' else 'origin')
        assert dict(origin=len(origin[1]), supplied=len(supplied[1]), ambient=len(ambient[1])) == dict(
            origin=int(expected == 'origin'), supplied=int(expected == 'supplied'), ambient=int(expected == 'ambient'))
        selected = dict(origin=origin, supplied=supplied, ambient=ambient)[expected]
        method, target, protocol = selected[1][0][0].split()
        parsed = urlsplit(target)
        assert method == 'GET' and protocol == 'HTTP/1.1' and selected[1][0][1] is None
        assert parsed.netloc == ('' if expected == 'origin' else urlsplit(origin[0]).netloc)
        if kind == 'state':
            assert parsed.path == '/api/v1/repos/fixture-owner/fixture-repo/issues'
            assert parse_qs(parsed.query) == {'state': ['open'], 'labels': ['status/ready'], 'limit': ['5']}
            assert headers[expected][0]['authorization'] == 'token public-test-token'
        else:
            assert parsed.path == '/api/v1/version' and observed == {'version': expected}
            encoded = base64.b64encode(b'Orket:public-test-password').decode()
            assert headers[expected][0]['authorization'] == 'Basic ' + encoded
